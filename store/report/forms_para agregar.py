"""
Formularios para generación de lista de precios
"""
from django import forms
from inventory.models import Category


class ListaPreciosForm(forms.Form):
    """Formulario para filtrar lista de precios"""
    
    TIPO_LISTA_CHOICES = [
        ('minorista', 'Precios Minoristas'),
        ('mayorista', 'Precios Mayoristas'),
    ]
    
    STOCK_CHOICES = [
        ('con_stock', 'Solo productos con stock'),
        ('todos', 'Todos los productos'),
    ]
    
    tipo_lista = forms.ChoiceField(
        choices=TIPO_LISTA_CHOICES,
        initial='minorista',
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Tipo de Lista'
    )
    
    stock = forms.ChoiceField(
        choices=STOCK_CHOICES,
        initial='con_stock',
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Productos'
    )
    
    categorias = forms.ModelMultipleChoiceField(
        queryset=Category.objects.filter(status=1).order_by('name'),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Categorías (dejar vacío para todas)'
    )
    
    # Datos de contacto
    nombre_contacto = forms.CharField(
        max_length=100,
        initial='Tu Negocio',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Nombre del Contacto'
    )
    
    telefono_contacto = forms.CharField(
        max_length=50,
        initial='',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '123-456789'}),
        label='Teléfono de Contacto'
    )
