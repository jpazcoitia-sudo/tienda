import unicodedata
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import models
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

    code = models.CharField(max_length=100, unique=True)
    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True)
    name = models.CharField(max_length=255)
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
    quantity = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['name']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return self.name

    def update_quantity_on_sale(self, quantity_sold):
        quantity_sold = int(quantity_sold)
        if self.quantity >= quantity_sold:
            self.quantity -= quantity_sold
            self.save(update_fields=['quantity'])
            return True
        return False

    def increase_quantity(self, quantity_added):
        self.quantity += quantity_added
        self.save(update_fields=['quantity'])
        self.update_status()
    # 1last copy
    def decrease_quantity(self, quantity_removed):
        self.quantity -= quantity_removed
        if self.quantity < 0:
            self.quantity = 0
        self.save(update_fields=['quantity'])
        self.update_status()
        
    def update_quantity_on_purchase(self, quantity_difference):
        self.quantity += quantity_difference
        if self.quantity < 0:
            self.quantity = 0
        self.save(update_fields=['quantity'])
        self.update_status()

    def update_cost(self, new_cost):
        """Actualiza el costo y recalcula los precios."""
        self.cost = new_cost
        self.calcular_precios()
        self.save(update_fields=['cost', 'precio_mayorista', 'precio_minorista'])
        self.update_status()

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
        """Actualiza el estado del producto basandose en cantidad, costo y precio."""
        if self.quantity > 0 and self.cost > Decimal('0') and self.precio_minorista > Decimal('0'):
            if self.status != self.STATUS_ACTIVE:
                self.status = self.STATUS_ACTIVE
                self.save(update_fields=['status'])
        else:
            if self.status != self.STATUS_INACTIVE:
                self.status = self.STATUS_INACTIVE
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