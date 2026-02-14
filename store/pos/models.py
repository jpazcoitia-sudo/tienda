from datetime import datetime
from unicodedata import category
from django.db import models
from django.utils import timezone
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from inventory.models import *

class Sales(models.Model):
    """
    Modelo de Venta con soporte para lista de precios mayorista/minorista.
    """
    TIPO_LISTA_CHOICES = [
        ('minorista', 'Minorista'),
        ('mayorista', 'Mayorista'),
    ]

    code = models.CharField(max_length=100)
    sub_total = models.FloatField(default=0)
    grand_total = models.FloatField(default=0)
    tax_amount = models.FloatField(default=0)
    tax = models.FloatField(default=0)
    tendered_amount = models.FloatField(default=0)
    amount_change = models.FloatField(default=0)
    forma_pago = models.CharField(
        max_length=20,
        choices=[
            ('efectivo', 'Efectivo'),
            ('banco', 'Banco/Transferencia')
        ],
        default='efectivo',
        verbose_name='Forma de Pago'
    )
    date_added = models.DateTimeField(default=timezone.now)
    date_updated = models.DateTimeField(auto_now=True)

    # CAMBIO: Ahora cliente es ForeignKey a la tabla Cliente
    # null=True permite ventas sin cliente (venta a mostrador)
    # blank=True permite que el campo sea opcional en formularios
    # on_delete=models.SET_NULL: si se elimina el cliente, la venta se mantiene pero sin referencia
    cliente = models.ForeignKey(
        'customers.Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Cliente',
        related_name='ventas'
    )

    # Tipo de lista de precios usada en esta venta
    tipo_lista = models.CharField(
        max_length=10,
        choices=TIPO_LISTA_CHOICES,
        default='minorista',
        verbose_name='Lista de Precios'
    )  

    def __str__(self):
        return self.code
    
    def get_nombre_cliente(self):
        """
        Retorna el nombre del cliente o 'Cliente General' si no hay cliente.
        """
        if self.cliente:
            return self.cliente.name
        return "Cliente General"

        
class salesItems(models.Model):
    """
    Item de venta con precio y costo historico.

    Guarda el precio y costo al momento de la venta para calcular
    ganancias historicas correctamente.
    """
    sale = models.ForeignKey(Sales, on_delete=models.CASCADE)
    product = models.ForeignKey(Products, on_delete=models.CASCADE)
    price = models.FloatField(default=0)  # Precio al momento de la venta
    costo_unitario = models.FloatField(default=0)  # Costo al momento de la venta
    qty = models.IntegerField(default=0)
    total = models.FloatField(default=0)

    def save(self, *args, **kwargs):
        """Guarda el item guardando el costo historico del producto."""
        # Guardar costo unitario si no esta establecido
        if self.costo_unitario == 0 and self.product:
            self.costo_unitario = float(self.product.cost)

        print(f"Guardando SalesItem: Producto: {self.product.name}, Cantidad: {self.qty}, Precio: {self.price}, Costo: {self.costo_unitario}")
        super().save(*args, **kwargs)
        self.update_product_quantity()

    def update_product_quantity(self):
        """Actualiza la cantidad del producto despues de la venta."""
        self.product.update_quantity_on_sale(self.qty)

    def delete(self, *args, **kwargs):
        """Restaura la cantidad del producto al eliminar el item."""
        print(f"Eliminando SalesItem: Producto: {self.product.name}, Cantidad: {self.qty}")
        self.product.increase_quantity(self.qty)
        super().delete(*args, **kwargs)

    @property
    def ganancia(self):
        """Calcula la ganancia de este item (precio - costo) * cantidad."""
        return (self.price - self.costo_unitario) * self.qty

    @property
    def ganancia_unitaria(self):
        """Calcula la ganancia por unidad."""
        return self.price - self.costo_unitario
