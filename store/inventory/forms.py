from django import forms
from django.core.exceptions import ValidationError
import unicodedata
from .models import Category, Products


class CategoryForm(forms.ModelForm):
    def clean_name(self):
        name = self.cleaned_data.get('name')
        
        # Normalizar el nombre ingresado (eliminar acentos)
        normalized_name = ''.join(c for c in unicodedata.normalize('NFD', name)
                                if unicodedata.category(c) != 'Mn')
        
        # Buscar categorías existentes con nombres similares
        existing_categories = Category.objects.exclude(id=self.instance.id)
        
        for category in existing_categories:
            category_normalized = ''.join(c for c in unicodedata.normalize('NFD', category.name)
                                        if unicodedata.category(c) != 'Mn')
            if category_normalized.lower() == normalized_name.lower():
                raise ValidationError(f"Ya existe una categoría similar: {category.name}")
        
        return name

    class Meta:
        model = Category
        fields = ['name', 'description', 'status']
        

class ProductsForm(forms.ModelForm):
    class Meta:
        model = Products
        fields = ['code', 'category', 'name', 'description',
            'cost', 'margen_mayorista', 'margen_minorista',
            'punto_pedido', 'tipo_venta', 'codigo_barras',
            'codigo_tipo', 'producto_origen', 'status']
        labels = {
            'code': 'Código',
            'category': 'Categoría',
            'name': 'Nombre del Producto',
            'description': 'Descripción',
            'cost': 'Costo (AR$)',
            'margen_mayorista': 'Margen Mayorista (%)',
            'margen_minorista': 'Margen Minorista (%)',
            'status': 'Estado',
            'punto_pedido': 'Punto de Pedido',
            'tipo_venta': 'Tipo de Venta',
            'codigo_barras': 'Código de Barras',
            'codigo_tipo': 'Tipo de Código',
            'producto_origen': 'Producto Origen',
        }
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Se asigna automaticamente',
                'readonly': 'readonly',
            }),
            'category': forms.Select(attrs={
                'class': 'form-control',
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Vino Dulce',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese información general Etc.',
                'rows': 3,
            }),
            'cost': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Costo del producto (AR$)',
                'step': '0.01',
            }),
            'margen_mayorista': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 20 para 20%',
                'step': '0.01',
            }),
            'margen_minorista': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 35 para 35%',
                'step': '0.01',
            }),
            'status': forms.Select(attrs={
                'class': 'form-control',
            }),
            'punto_pedido': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 5 (0 = sin alerta)',
                'step': '0.01',
            }),
            'tipo_venta': forms.Select(attrs={
                'class': 'form-control',
            }),
            'codigo_barras': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Escanear o ingresar código',
            }),
            'codigo_tipo': forms.Select(attrs={
                'class': 'form-control',
            }),
            'producto_origen': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_producto_origen',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['producto_origen'].queryset = Products.objects.exclude(
            tipo_venta='fraccionable'
        ).order_by('name')
        # El codigo interno es opcional: si se deja vacio, el sistema asigna el proximo correlativo
        self.fields['code'].required = False
