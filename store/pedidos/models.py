from django.db import models
from django.urls import reverse
from django.utils import timezone
from customers.models import Cliente
from inventory.models import Products

class Pedido(models.Model):
    """
    Modelo para gestionar pedidos de clientes.
    Los pedidos NO afectan el stock hasta que se convierten en venta.
    """
    
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('facturado', 'Facturado'),
        ('cancelado', 'Cancelado'),
    ]
    
    TIPO_LISTA_CHOICES = [
        ('minorista', 'Minorista'),
        ('mayorista', 'Mayorista'),
    ]
    
    # Información del pedido
    code = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Código de Pedido'
    )
    
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,  # No permitir eliminar cliente si tiene pedidos
        verbose_name='Cliente',
        related_name='pedidos'
    )
    
    # Precios y totales
    tipo_lista = models.CharField(
        max_length=10,
        choices=TIPO_LISTA_CHOICES,
        default='minorista',
        verbose_name='Lista de Precios'
    )
    
    sub_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='Subtotal'
    )
    
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='Total'
    )
    
    # Estado y fechas
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente',
        verbose_name='Estado'
    )
    
    fecha_pedido = models.DateTimeField(
        default=timezone.now,
        verbose_name='Fecha de Pedido'
    )
    
    fecha_entrega_estimada = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha de Entrega Estimada'
    )
    
    fecha_entrega_real = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Entrega Real'
    )
    
    # Notas
    notas = models.TextField(
        blank=True,
        null=True,
        verbose_name='Notas del Pedido',
        help_text='Observaciones o comentarios sobre el pedido'
    )
    
    # Metadata
    date_updated = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización'
    )
    
    # Referencia a venta (si se convirtió)
    venta = models.ForeignKey(
        'pos.Sales',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Venta Asociada',
        related_name='pedido_origen'
    )
    
    class Meta:
        verbose_name = 'Pedido'
        verbose_name_plural = 'Pedidos'
        ordering = ['-fecha_pedido']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['cliente']),
            models.Index(fields=['estado']),
            models.Index(fields=['fecha_entrega_estimada']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.cliente.name}"
    
    def get_absolute_url(self):
        return reverse('pedidos:pedido_detail', kwargs={'pk': self.pk})
    
    def get_estado_badge_class(self):
        """Retorna clase CSS de badge según estado"""
        badge_classes = {
            'pendiente': 'warning',
            'facturado': 'success',
            'cancelado': 'danger',
        }
        return badge_classes.get(self.estado, 'secondary')
    
    def puede_editarse(self):
        """Un pedido solo puede editarse si está pendiente"""
        return self.estado == 'pendiente'
    
    def puede_convertirse_a_venta(self):
        """Un pedido puede convertirse a venta si está pendiente"""
        return self.estado == 'pendiente' and self.venta is None
    
    def puede_cancelarse(self):
        """Un pedido puede cancelarse si no ha sido facturado"""
        return self.estado not in ['facturado', 'cancelado']
    
    def calcular_totales(self):
        """Calcula y actualiza los totales del pedido"""
        items = self.items.all()
        self.sub_total = sum(item.total for item in items)
        self.total = self.sub_total
        self.save()
    
    def stock_disponible(self):
        """
        Verifica si hay stock suficiente para todos los items del pedido.
        Retorna (True/False, lista_de_items_sin_stock)
        """
        items_sin_stock = []
        for item in self.items.all():
            if item.product.quantity < item.cantidad:
                items_sin_stock.append({
                    'producto': item.product.name,
                    'solicitado': item.cantidad,
                    'disponible': item.product.quantity
                })
        
        return (len(items_sin_stock) == 0, items_sin_stock)


class PedidoItem(models.Model):
    """
    Item individual de un pedido.
    """
    
    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Pedido'
    )
    
    product = models.ForeignKey(
        Products,
        on_delete=models.PROTECT,
        verbose_name='Producto'
    )
    
    cantidad = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Cantidad'
    )
    
    precio_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Precio Unitario',
        help_text='Precio al momento de tomar el pedido'
    )
    
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Total'
    )
    
    class Meta:
        verbose_name = 'Item de Pedido'
        verbose_name_plural = 'Items de Pedido'
        unique_together = ['pedido', 'product']
    
    def __str__(self):
        return f"{self.product.name} x {self.cantidad}"
    
    def save(self, *args, **kwargs):
        """Calcula el total antes de guardar"""
        self.total = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)
        
        # Actualizar totales del pedido
        self.pedido.calcular_totales()
