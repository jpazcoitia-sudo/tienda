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
            
    def __str__(self):
        return f"{self.product} de {self.supplier} - {self.qty} @ {self.cost} cada uno"
