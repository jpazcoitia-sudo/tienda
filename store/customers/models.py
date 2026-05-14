from django.db import models
from django.urls import reverse

class Cliente(models.Model):
    """
    Modelo para gestionar clientes de la tienda.
    Permite registrar clientes y asociarlos a ventas específicas.
    """
    
    TIPO_CLIENTE_CHOICES = [
        ('minorista', 'Minorista'),
        ('mayorista', 'Mayorista'),
    ]
    
    # Información básica
    name = models.CharField(
        max_length=200,
        verbose_name='Nombre Completo',
        help_text='Nombre completo del cliente'
    )
    
    dni = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='DNI/CUIT',
        help_text='Documento de identidad único'
    )
    
    # Información de contacto
    phone = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name='Teléfono',
        help_text='Número de contacto'
    )
    
    email = models.EmailField(
        blank=True,
        null=True,
        verbose_name='Email',
        help_text='Correo electrónico'
    )
    
    address = models.TextField(
        blank=True,
        null=True,
        verbose_name='Dirección',
        help_text='Dirección completa del cliente'
    )
    
    # Tipo de cliente (define lista de precios por defecto)
    tipo_cliente = models.CharField(
        max_length=20,
        choices=TIPO_CLIENTE_CHOICES,
        default='minorista',
        verbose_name='Tipo de Cliente',
        help_text='Define la lista de precios a aplicar'
    )
    
    # Estado y notas
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo',
        help_text='Cliente activo en el sistema'
    )
    
    notas = models.TextField(
        blank=True,
        null=True,
        verbose_name='Notas',
        help_text='Observaciones o comentarios sobre el cliente'
    )
    
    # Metadata
    date_added = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Registro'
    )
    
    date_updated = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización'
    )
    
    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['-date_added']
        indexes = [
            models.Index(fields=['dni']),
            models.Index(fields=['name']),
            models.Index(fields=['activo']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.dni})"
    
    def get_absolute_url(self):
        return reverse('customers:customer_detail', kwargs={'pk': self.pk})
    
    def get_tipo_cliente_display_badge(self):
        """Retorna clase CSS para badge según tipo de cliente"""
        if self.tipo_cliente == 'mayorista':
            return 'success'  # Verde
        return 'primary'  # Azul
    
    def get_total_ventas(self):
        """Calcula el total de ventas realizadas a este cliente"""
        from pos.models import Sales
        ventas = Sales.objects.filter(cliente=self)
        total = sum([venta.grand_total for venta in ventas if venta.grand_total])
        return total
    
    def get_cantidad_ventas(self):
        """Retorna la cantidad de ventas realizadas a este cliente"""
        from pos.models import Sales
        return Sales.objects.filter(cliente=self).count()
    
    def get_ultima_venta(self):
        """Retorna la fecha de la última venta"""
        from pos.models import Sales
        ultima = Sales.objects.filter(cliente=self).order_by('-date_added').first()
        return ultima.date_added if ultima else None
    
    def get_saldo_cuenta_corriente(self):
        """Retorna el saldo actual de la cuenta corriente (negativo = debe)"""
        movimientos = self.movimientos_cuenta.all()
        saldo = 0
        for m in movimientos:
            if m.tipo == 'pago':
                saldo += m.monto
            else:  # venta
                saldo -= m.monto
        return saldo

class MovimientoCuentaCorriente(models.Model):
    
    TIPO_CHOICES = [
        ('venta', 'Venta'),
        ('pago', 'Pago'),
    ]
    
    FORMA_PAGO_CHOICES = [
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia'),
    ]
    
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='movimientos_cuenta',
        verbose_name='Cliente'
    )
    
    tipo = models.CharField(
        max_length=10,
        choices=TIPO_CHOICES,
        verbose_name='Tipo'
    )
    
    monto = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        verbose_name='Monto'
    )
    
    forma_pago = models.CharField(
        max_length=20,
        choices=FORMA_PAGO_CHOICES,
        blank=True,
        null=True,
        verbose_name='Forma de Pago'
    )
    
    venta = models.ForeignKey(
        'pos.Sales',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimiento_cuenta',
        verbose_name='Venta'
    )
    
    notas = models.TextField(
        blank=True,
        null=True,
        verbose_name='Notas'
    )
    
    fecha = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha'
    )

    class Meta:
        verbose_name = 'Movimiento Cuenta Corriente'
        verbose_name_plural = 'Movimientos Cuenta Corriente'
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.cliente.name} - {self.tipo} - ${self.monto}"