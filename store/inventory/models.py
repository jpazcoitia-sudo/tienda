import unicodedata
from datetime import datetime

from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import models, transaction
from django.db.models import F
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone


from decimal import Decimal
class Category(models.Model):
    name = models.TextField()
    description = models.TextField()
    status = models.IntegerField(default=1) 
    date_added = models.DateTimeField(default=timezone.now) 
    date_updated = models.DateTimeField(auto_now=True) 

    def __str__(self):
        return self.name
    
    def check_and_update_status(self):
        if self.pk:  
            if self.products_set.filter(status=1).count() == 0:
                self.status = 0
            else:
                self.status = 1
            
            Category.objects.filter(pk=self.pk).update(status=self.status)
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.check_and_update_status() 
        

class ProductosVisibles(models.Manager):
    """
    Manager por defecto de Products: devuelve solo los productos NO eliminados.

    Asi, todos los listados, buscadores y selectores del sistema dejan de mostrar
    un producto eliminado sin tener que acordarse de filtrarlo en cada pantalla.
    Para ver tambien los eliminados (historial, admin, restaurar) usar Products.todos.
    """
    def get_queryset(self):
        return super().get_queryset().filter(eliminado=False)


class Products(models.Model):
    """
    Modelo de Producto con sistema de precios mayorista/minorista.

    Los precios se calculan automaticamente basandose en el costo y los margenes:
    - precio_mayorista = costo * (1 + margen_mayorista / 100)
    - precio_minorista = costo * (1 + margen_minorista / 100)
    """
    STATUS_INACTIVE = 0
    STATUS_ACTIVE = 1
    STATUS_CHOICES = [
        (STATUS_INACTIVE, 'Inactivo'),
        (STATUS_ACTIVE, 'Activo'),
    ]

    TIPO_VENTA_UNIDAD = 'unidad'
    TIPO_VENTA_FRACCIONABLE = 'fraccionable'
    TIPO_VENTA_CHOICES = [
        (TIPO_VENTA_UNIDAD, 'Unidad'),
        (TIPO_VENTA_FRACCIONABLE, 'Fraccionable'),
    ]

    CODIGO_TIPO_EXTERNO = 'externo'
    CODIGO_TIPO_INTERNO = 'interno'
    CODIGO_TIPO_CHOICES = [
        (CODIGO_TIPO_EXTERNO, 'Externo (fabricante)'),
        (CODIGO_TIPO_INTERNO, 'Interno (generado)'),
    ]

    code = models.CharField(max_length=100, unique=True)
    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True)
    name = models.CharField(max_length=255)
    marca = models.CharField(max_length=100, blank=True, null=True, verbose_name='Marca')
    description = models.TextField(blank=True)

    # Costo base del producto
    cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Costo'
    )

    # Margenes de ganancia (en porcentaje)
    margen_mayorista = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('20.00'),
        verbose_name='Margen Mayorista (%)'
    )
    margen_minorista = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('35.00'),
        verbose_name='Margen Minorista (%)'
    )

    # Precios calculados automaticamente (no editables directamente)
    precio_mayorista = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Precio Mayorista'
    )
    precio_minorista = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Precio Minorista'
    )

    status = models.IntegerField(choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    date_added = models.DateTimeField(default=timezone.now)
    date_updated = models.DateTimeField(auto_now=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    punto_pedido = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='Punto de Pedido',
        help_text='Avisar cuando el stock llegue a este valor (0 = sin alerta)'
    )

    tipo_venta = models.CharField(
        max_length=20,
        choices=TIPO_VENTA_CHOICES,
        default=TIPO_VENTA_UNIDAD,
        verbose_name='Tipo de Venta',
        help_text='Unidad: agrega 1 al escanear. Fraccionable: pide cantidad.'
    )

    codigo_barras = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        unique=True,
        verbose_name='Código de Barras'
    )

    codigo_tipo = models.CharField(
        max_length=10,
        choices=CODIGO_TIPO_CHOICES,
        default=CODIGO_TIPO_EXTERNO,
        verbose_name='Tipo de Código',
        help_text='Externo: viene del fabricante. Interno: generado por el sistema.'
    )

    plu = models.PositiveIntegerField(
        blank=True,
        null=True,
        unique=True,
        verbose_name='PLU',
        help_text='Número PLU para balanza (asignado automáticamente al marcar como fraccionable)'
    )

    producto_origen = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fraccionados',
        verbose_name='Producto Origen',
        help_text='Para fraccionables: producto del cual proviene (actualiza costo automáticamente)'
    )

    # --- Borrado logico -------------------------------------------------
    # "Eliminar" un producto NO lo borra de la base: lo oculta. Asi las ventas,
    # compras y pedidos viejos conservan su detalle. Estados del producto:
    #   Activo    -> se vende
    #   Inactivo  -> sin stock, pero se puede volver a comprar (lo maneja update_status)
    #   Eliminado -> no va mas (duplicado, error de carga, discontinuado): no aparece
    #                en ningun listado ni buscador, solo en el historial.
    eliminado = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='Eliminado',
        help_text='Oculto en todo el sistema. Se conserva solo para el historial de ventas y compras.'
    )
    fecha_eliminado = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de eliminación')

    # El PRIMER manager es el que Django usa por defecto (listados, formularios, admin).
    objects = ProductosVisibles()   # solo productos no eliminados
    todos = models.Manager()        # todos, incluidos los eliminados

    class Meta:
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['name']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return self.name

    def eliminar(self):
        """
        Borrado logico: oculta el producto y libera su codigo de barras y su PLU
        (para poder asignarselos a otro producto). No toca ventas ni compras.
        """
        self.eliminado = True
        self.fecha_eliminado = timezone.now()
        self.codigo_barras = None
        self.plu = None
        self.status = self.STATUS_INACTIVE
        self.save(update_fields=['eliminado', 'fecha_eliminado', 'codigo_barras', 'plu', 'status'])

    def restaurar(self):
        """Deshace el borrado logico. El codigo de barras y el PLU hay que volver a asignarlos."""
        self.eliminado = False
        self.fecha_eliminado = None
        self.save(update_fields=['eliminado', 'fecha_eliminado'])
        self.update_status()

    # ------------------------------------------------------------------
    # STOCK. Regla (decision del 02/10/2026):
    #   - El stock PUEDE quedar negativo. Una venta nunca se frena por falta de stock:
    #     se descuenta siempre. Un negativo es la senal de que hay que ajustar
    #     (falta cargar una compra o hacer un conteo).
    #   - El stock NO decide si el producto esta activo: con stock 0 se sigue vendiendo.
    #   - Todos los movimientos pasan por _mover_stock, que le pide la cuenta a la base
    #     con F(): asi dos ventas al mismo tiempo no se pisan entre si.
    # ------------------------------------------------------------------
    def _mover_stock(self, diferencia):
        """Suma (o resta, si es negativa) una cantidad al stock. Devuelve el stock nuevo."""
        diferencia = Decimal(str(diferencia))
        Products.todos.filter(pk=self.pk).update(quantity=F('quantity') + diferencia)
        self.refresh_from_db(fields=['quantity'])
        return self.quantity

    def update_quantity_on_sale(self, quantity_sold):
        """Descuenta lo vendido. Siempre descuenta, aunque el stock no alcance."""
        self._mover_stock(-Decimal(str(quantity_sold)))
        return True

    def increase_quantity(self, quantity_added):
        self._mover_stock(quantity_added)

    def decrease_quantity(self, quantity_removed):
        self._mover_stock(-Decimal(str(quantity_removed)))

    def update_quantity_on_purchase(self, quantity_difference):
        self._mover_stock(quantity_difference)

    def update_cost(self, new_cost):
        """Actualiza el costo y recalcula los precios."""
        self.cost = new_cost
        self.calcular_precios()
        self.save(update_fields=['cost', 'precio_mayorista', 'precio_minorista'])
        self.update_status()

        # Si este producto es origen de fraccionados, actualizar su costo también
        for fraccionado in self.fraccionados.all():
            fraccionado.cost = new_cost
            fraccionado.calcular_precios()
            fraccionado.save(update_fields=['cost', 'precio_mayorista', 'precio_minorista'])
            fraccionado.update_status()

    def calcular_precios(self):
        """
        Calcula los precios mayorista y minorista basandose en el costo y margenes.

        Formula: precio = costo * (1 + margen / 100)
        """
        if self.cost > Decimal('0'):
            self.precio_mayorista = self.cost * (1 + self.margen_mayorista / Decimal('100'))
            self.precio_minorista = self.cost * (1 + self.margen_minorista / Decimal('100'))
            # Redondear a 2 decimales
            self.precio_mayorista = self.precio_mayorista.quantize(Decimal('0.01'))
            self.precio_minorista = self.precio_minorista.quantize(Decimal('0.01'))
        else:
            self.precio_mayorista = Decimal('0.00')
            self.precio_minorista = Decimal('0.00')

    def get_precio(self, tipo_lista='minorista'):
        """
        Obtiene el precio segun el tipo de lista.

        Args:
            tipo_lista: 'mayorista' o 'minorista' (default: 'minorista')

        Returns:
            Decimal: Precio correspondiente al tipo de lista
        """
        if tipo_lista == 'mayorista':
            return self.precio_mayorista
        return self.precio_minorista

    def clean(self):
        """Validaciones del modelo."""
        super().clean()
        # El codigo interno tambien debe ser unico contra los productos eliminados
        # (siguen en la base). La validacion automatica de Django solo mira los visibles.
        if self.code and Products.todos.filter(code=self.code, eliminado=True).exclude(pk=self.pk).exists():
            raise ValidationError({'code': "Ese código ya lo usó un producto eliminado. Elegí otro."})
        if self.cost < Decimal('0'):
            raise ValidationError({'cost': "El costo no puede ser negativo."})
        if self.margen_mayorista < Decimal('0'):
            raise ValidationError({'margen_mayorista': "El margen mayorista no puede ser negativo."})
        if self.margen_minorista < Decimal('0'):
            raise ValidationError({'margen_minorista': "El margen minorista no puede ser negativo."})

    def save(self, *args, **kwargs):
        """Guarda el producto calculando los precios automaticamente."""
        # Solo validar si no es una actualizacion parcial de campos especificos
        update_fields = kwargs.get('update_fields')
        if update_fields is None or 'cost' in update_fields or 'margen_mayorista' in update_fields or 'margen_minorista' in update_fields:
            self.calcular_precios()

        # Validar solo en creacion o actualizacion completa
        if update_fields is None:
            self.full_clean()

        super().save(*args, **kwargs)

        # Actualizar status solo si no es una actualizacion de status
        if update_fields is None or 'status' not in update_fields:
            self.update_status()

    def update_status(self):
        """
        Actualiza el estado del producto:
          Activo   = tiene costo y precio (se puede vender).
          Inactivo = le falta el costo o el precio.
        El stock NO interviene (desde el 02/10/2026): un producto con stock 0 o
        negativo sigue activo y se puede vender; el punto de venta avisa con un cartel.
        """
        # Un producto eliminado no cambia de estado (queda inactivo y oculto)
        if self.eliminado:
            return
        if self.cost > Decimal('0') and self.precio_minorista > Decimal('0'):
            nuevo = self.STATUS_ACTIVE
        else:
            nuevo = self.STATUS_INACTIVE
        if self.status != nuevo:
            self.status = nuevo
            self.save(update_fields=['status'])

    def update_cost_after_deletion(self, cost_removed):
        self.cost = self.calculate_new_cost_after_deletion(cost_removed)
        self.save(update_fields=['cost'])
        self.update_status()
    
    def calculate_new_cost_after_deletion(self, cost_removed):
        return max(self.cost - cost_removed, Decimal('0'))
    
    @property
    def last_purchase(self):
        return self.purchaseproduct_set.order_by('-date_added').first()

    @property
    def last_purchase_cost(self):
        last_purchase = self.last_purchase
        return last_purchase.cost if last_purchase else Decimal('0')

    @property
    def last_purchase_quantity(self):
        last_purchase = self.last_purchase
        return last_purchase.quantity if last_purchase else 0

    @property
    def profit_margin_mayorista(self):
        """Retorna el margen de ganancia mayorista como decimal (ej: 0.20 = 20%)."""
        return self.margen_mayorista / Decimal('100')

    @property
    def profit_margin_minorista(self):
        """Retorna el margen de ganancia minorista como decimal (ej: 0.35 = 35%)."""
        return self.margen_minorista / Decimal('100')

    @property
    def ganancia_mayorista(self):
        """Retorna la ganancia por unidad en precio mayorista."""
        return self.precio_mayorista - self.cost

    @property
    def ganancia_minorista(self):
        """Retorna la ganancia por unidad en precio minorista."""
        return self.precio_minorista - self.cost


# ======================================================================
# CONTEO DE STOCK (inventario fisico) — desde el 02/10/2026
# ======================================================================
class ConteoStock(models.Model):
    """
    Un conteo fisico de la mercaderia. Mientras esta abierto se van cargando
    los productos contados; al cerrarlo queda como registro historico.
    Solo puede haber un conteo abierto a la vez.
    """
    fecha_inicio = models.DateTimeField(default=timezone.now)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    iniciado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name='+')
    cerrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='+')
    nota = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        ordering = ['-fecha_inicio']
        verbose_name = 'Conteo de stock'
        verbose_name_plural = 'Conteos de stock'

    def __str__(self):
        return f"Conteo del {self.fecha_inicio:%d/%m/%Y}"

    @property
    def abierto(self):
        return self.fecha_cierre is None

    @classmethod
    def el_abierto(cls):
        """Devuelve el conteo abierto, o None si no hay."""
        return cls.objects.filter(fecha_cierre__isnull=True).first()

    def cargar(self, producto, contado, usuario=None, automatico=False):
        """
        Anota lo contado de UN producto y pone ese valor como stock del sistema.

        - No toca costos, precios ni caja: solo el stock.
        - Guarda cuanto decia el sistema antes, para poder ver la diferencia.
        - Si el producto ya estaba cargado en este conteo, corrige el valor
          (se conserva el "stock del sistema" de la primera vez).
        Devuelve el renglon.
        """
        if not self.abierto:
            raise ValidationError("El conteo ya está cerrado.")
        contado = Decimal(str(contado)).quantize(Decimal('0.01'))
        if contado < 0:
            raise ValidationError("La cantidad contada no puede ser negativa.")

        with transaction.atomic():
            # select_for_update: nadie mas cambia este producto hasta terminar
            producto = Products.todos.select_for_update().get(pk=producto.pk)
            renglon = ConteoStockRenglon.objects.filter(conteo=self, product=producto).first()
            if renglon is None:
                renglon = ConteoStockRenglon(conteo=self, product=producto, stock_sistema=producto.quantity)
            renglon.contado = contado
            renglon.usuario = usuario
            renglon.fecha = timezone.now()
            renglon.automatico = automatico
            renglon.save()
            Products.todos.filter(pk=producto.pk).update(quantity=contado)
            producto.refresh_from_db(fields=['quantity'])
            producto.update_status()
        return renglon

    def productos_sin_contar(self):
        """Productos visibles que todavia no se cargaron en este conteo."""
        return Products.objects.exclude(pk__in=self.renglones.values('product_id')).order_by('name')

    def cerrar(self, usuario=None, poner_en_cero_los_no_contados=False):
        """
        Cierra el conteo. Si se pide, los productos que nadie conto quedan en stock 0
        (y anotados en el conteo como puestos en cero automaticamente).
        Devuelve cuantos productos se pusieron en cero.
        """
        if not self.abierto:
            raise ValidationError("El conteo ya está cerrado.")
        en_cero = 0
        with transaction.atomic():
            if poner_en_cero_los_no_contados:
                for producto in self.productos_sin_contar():
                    self.cargar(producto, Decimal('0'), usuario=usuario, automatico=True)
                    en_cero += 1
            self.fecha_cierre = timezone.now()
            self.cerrado_por = usuario
            self.save(update_fields=['fecha_cierre', 'cerrado_por'])
        return en_cero


class ConteoStockRenglon(models.Model):
    """Un producto dentro de un conteo: cuanto decia el sistema y cuanto se conto."""
    conteo = models.ForeignKey(ConteoStock, on_delete=models.CASCADE, related_name='renglones')
    # PROTECT: un producto con conteos no se borra de la base (para eso esta el borrado logico)
    product = models.ForeignKey(Products, on_delete=models.PROTECT, related_name='conteos')
    stock_sistema = models.DecimalField(max_digits=10, decimal_places=2,
                                        verbose_name='Stock que decía el sistema')
    contado = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Contado')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                null=True, blank=True, related_name='+')
    fecha = models.DateTimeField(default=timezone.now)
    automatico = models.BooleanField(default=False,
                                     verbose_name='Puesto en cero al cerrar (no se contó)')

    class Meta:
        unique_together = [('conteo', 'product')]
        ordering = ['product__name']
        verbose_name = 'Renglón de conteo'
        verbose_name_plural = 'Renglones de conteo'

    def __str__(self):
        return f"{self.product.name}: {self.contado}"

    @property
    def diferencia(self):
        """Contado menos sistema: positivo = habia de mas en la realidad (sobrante)."""
        return self.contado - self.stock_sistema
