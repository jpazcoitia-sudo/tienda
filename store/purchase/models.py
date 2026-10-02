from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.db.models import Sum, F
from inventory.models import Products
from django.db import transaction
from django.db import models, transaction
from decimal import Decimal
from django.core.exceptions import ValidationError

def aplicar_diferencia_stock(cantidades_antes, cantidades_despues):
    """
    Ajusta el stock de cada producto por la DIFERENCIA entre lo que una compra
    sumaba antes y lo que suma ahora:   stock = stock + (despues - antes)

    - Editar una compra:  antes = renglones viejos, despues = renglones nuevos.
    - Borrar una compra:  antes = sus renglones,    despues = {} (nada).

    Se usa F() para que la cuenta la haga la base de datos sobre el valor actual.
    El stock nunca queda negativo y se actualiza el estado (activo/inactivo).
    """
    ids = set(cantidades_antes) | set(cantidades_despues)
    for product_id in ids:
        diferencia = cantidades_despues.get(product_id, Decimal('0')) - cantidades_antes.get(product_id, Decimal('0'))
        if diferencia:
            Products.objects.filter(pk=product_id).update(quantity=F('quantity') + diferencia)

    for producto in Products.objects.filter(pk__in=ids):
        if producto.quantity < 0:
            producto.quantity = Decimal('0')
            producto.save(update_fields=['quantity'])
        producto.update_status()


class Supplier(models.Model):
    name = models.CharField(max_length=100)
    contact_info = models.TextField(blank=True)
    date_added = models.DateTimeField(default=timezone.now, editable=False)
    date_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


# NUEVO: Modelo Purchase (cabecera de la compra)
class Purchase(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True)
    numero_comprobante = models.CharField(max_length=50, blank=True, null=True, verbose_name="Número de Comprobante")
    total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    subtotal_productos = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Subtotal sin impuestos")
    iva_monto = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="IVA")
    perc_monto = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Percepción IVA")
    date_added = models.DateTimeField(default=timezone.now)
    date_updated = models.DateTimeField(auto_now=True)
    
    # NUEVO: Campos de pago
    forma_pago = models.CharField(
        max_length=20,
        choices=[
            ('efectivo', 'Efectivo'),
            ('banco', 'Banco/Transferencia')
        ],
        default='efectivo',
        verbose_name='Forma de Pago'
    )
    
    pagado = models.BooleanField(
        default=False,
        verbose_name='Pagado',
        help_text='Indica si la compra ya fue pagada'
    )
    
    fecha_pago = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Pago'
    )
    
    def __str__(self):
        return f"Compra #{self.id} - {self.supplier} - {self.date_added.strftime('%d/%m/%Y')}"
    
    class Meta:
        ordering = ['-date_added']

    def cantidades_por_producto(self):
        """Devuelve {id_producto: cantidad total} sumando los renglones de esta compra."""
        cantidades = {}
        for item in self.items.all():
            if item.product_id:
                cantidades[item.product_id] = cantidades.get(item.product_id, Decimal('0')) + item.qty
        return cantidades

    def guardar_renglones(self, renglones, iva_monto=Decimal('0'), perc_monto=Decimal('0')):
        """
        Guarda (o reemplaza) los renglones de la compra. Lo usan CREAR y EDITAR,
        asi las dos pantallas hacen exactamente lo mismo.

        renglones: lista de (producto, costo_de_factura, cantidad)
                   El costo es el de la factura, SIN IVA ni percepcion.

        Que hace:
          1. Reparte IVA + percepcion entre los renglones, en proporcion a su importe.
             costo final = costo de factura + parte del impuesto que le toca.
          2. Guarda en cada renglon el costo final (cost) y el de factura (costo_neto).
          3. Actualiza los totales de la compra (subtotal, IVA, percepcion, total).
          4. Ajusta el stock por la DIFERENCIA con lo que la compra tenia antes
             (en una compra nueva, antes no tenia nada).
          5. Actualiza el costo de cada producto (promedio ponderado dentro de la compra).

        Llamar dentro de transaction.atomic().
        """
        iva_monto = Decimal(iva_monto or 0)
        perc_monto = Decimal(perc_monto or 0)
        if iva_monto < 0 or perc_monto < 0:
            raise ValidationError("El IVA y la percepcion no pueden ser negativos.")

        for _producto, costo_neto, qty in renglones:
            if qty <= 0:
                raise ValidationError("La cantidad debe ser mayor a cero.")
            if costo_neto <= 0:
                raise ValidationError("El costo debe ser mayor a cero.")

        cantidades_antes = self.cantidades_por_producto()

        # Borrado masivo y bulk_create NO llaman a delete()/save() del modelo:
        # no tocan el stock. El stock se ajusta una sola vez, mas abajo.
        self.items.all().delete()

        subtotal = sum((costo * qty for _p, costo, qty in renglones), Decimal('0'))
        total_impuestos = iva_monto + perc_monto
        total = Decimal('0')
        nuevos = []
        for producto, costo_neto, qty in renglones:
            linea = costo_neto * qty
            proporcion = linea / subtotal if subtotal > 0 else Decimal('0')
            impuesto_linea = total_impuestos * proporcion
            costo_final = costo_neto + (impuesto_linea / qty)
            costo_guardado = costo_final.quantize(Decimal('0.0001'))
            nuevos.append(PurchaseProduct(
                purchase=self,
                supplier=self.supplier,
                product=producto,
                cost=costo_guardado,
                costo_neto=costo_neto,
                qty=qty,
                total=costo_guardado * qty,
            ))
            total += costo_final * qty
        PurchaseProduct.objects.bulk_create(nuevos)

        self.total = total
        self.subtotal_productos = subtotal
        self.iva_monto = iva_monto
        self.perc_monto = perc_monto
        self.save()

        aplicar_diferencia_stock(cantidades_antes, self.cantidades_por_producto())

        # Costo de cada producto = promedio ponderado de sus renglones EN ESTA compra.
        acumulado = {}
        for item in self.items.select_related('product'):
            if not item.product:
                continue
            d = acumulado.setdefault(item.product_id, {'cq': Decimal('0'), 'q': Decimal('0'), 'prod': item.product})
            d['cq'] += item.cost * item.qty
            d['q'] += item.qty
        for d in acumulado.values():
            if d['q'] > 0:
                d['prod'].update_cost((d['cq'] / d['q']).quantize(Decimal('0.0001')))

    def delete(self, *args, **kwargs):
        """
        Al borrar una compra hay que devolver el stock que habia sumado.
        OJO: el borrado en cascada de los renglones NO llama a PurchaseProduct.delete(),
        por eso el stock se ajusta aca.
        """
        with transaction.atomic():
            aplicar_diferencia_stock(self.cantidades_por_producto(), {})
            return super().delete(*args, **kwargs)
    
    # NUEVO: Métodos de pago
    def marcar_como_pagado(self, forma_pago='efectivo'):
        """Marca la compra como pagada"""
        self.pagado = True
        self.forma_pago = forma_pago
        self.fecha_pago = timezone.now()
        self.save()
        return True
    
    def get_estado_pago(self):
        """Retorna el estado de pago formateado"""
        if self.pagado:
            return f"✅ Pagado ({self.get_forma_pago_display()})"
        return "⏳ Pendiente de Pago"
    
    def get_estado_pago_badge_class(self):
        """Retorna clase CSS según estado de pago"""
        return 'success' if self.pagado else 'warning'


# MODIFICADO: PurchaseProduct ahora es el detalle de cada compra
class PurchaseProduct(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='items', null=True, blank=True)  # Nueva relación
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True)
    product = models.ForeignKey(Products, on_delete=models.SET_NULL, null=True)
    cost = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    # Costo de la factura, antes de sumarle la parte de IVA/percepcion.
    # (cost = costo final, con el impuesto repartido adentro)
    costo_neto = models.DecimalField(max_digits=18, decimal_places=8, null=True, blank=True,
                                     verbose_name='Costo de factura (sin impuestos)')
    qty = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=18, decimal_places=8, editable=False, default=0)
    date_added = models.DateTimeField(default=timezone.now)
    date_updated = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.qty <= 0:
            raise ValidationError("The quantity must be greater than zero.")
        if self.cost <= 0:
            raise ValidationError("The cost must be greater than zero.")

    def save(self, *args, **kwargs):
        self.clean()
        self.total = self.cost * self.qty
        
        with transaction.atomic():
            
            if self.pk:
            
                previous_instance = PurchaseProduct.objects.get(pk=self.pk)
                quantity_difference = self.qty - previous_instance.qty
            else:
                quantity_difference = self.qty
            super().save(*args, **kwargs)

            # Actualizar el producto asociado
            if self.product:
                self.product.update_quantity_on_purchase(quantity_difference)
                self.product.update_cost(self.cost)
                
                
    def delete(self, *args, **kwargs):
        with transaction.atomic():
            if self.product:
                # Actualizar el producto asociado antes de eliminar la compra
                self.product.decrease_quantity(self.qty)
                # No se toca el costo: restarle el costo del renglon lo dejaba en $0.
            super().delete(*args, **kwargs)
            
    def get_costo_neto(self):
        """Costo de factura del renglon. Si no esta guardado (dato viejo), usa el costo final."""
        return self.costo_neto if self.costo_neto is not None else self.cost

    def __str__(self):
        return f"{self.product} de {self.supplier} - {self.qty} @ {self.cost} cada uno"
