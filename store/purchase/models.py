from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.db.models import Sum
from inventory.models import Products
from django.db import transaction
from django.db import models, transaction
from decimal import Decimal
from django.core.exceptions import ValidationError

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
    qty = models.DecimalField(max_digits=10, decimal_places=0, default=0)
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
                self.product.update_cost_after_deletion(self.cost)
            super().delete(*args, **kwargs)
            
    def __str__(self):
        return f"{self.product} de {self.supplier} - {self.qty} @ {self.cost} cada uno"
