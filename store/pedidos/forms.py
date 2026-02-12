from django import forms
from django.core.exceptions import ValidationError
from .models import Pedido, PedidoItem
from customers.models import Cliente
from inventory.models import Products
import datetime


class PedidoForm(forms.ModelForm):
    """
    Formulario para crear/editar pedidos.
    """
    
    class Meta:
        model = Pedido
        fields = [
            'cliente',
            'tipo_lista',
            'fecha_entrega_estimada',
            'notas',
            'estado'
        ]
        widgets = {
            'cliente': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'tipo_lista': forms.Select(attrs={
                'class': 'form-select'
            }),
            'fecha_entrega_estimada': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'notas': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Observaciones sobre el pedido (opcional)'
            }),
            'estado': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrar solo clientes activos
        self.fields['cliente'].queryset = Cliente.objects.filter(activo=True).order_by('name')
        
        # Si es creación, solo pendiente
        if not self.instance.pk:
            self.fields['estado'].choices = [('pendiente', 'Pendiente')]
            self.fields['estado'].initial = 'pendiente'
    
    def clean_fecha_entrega_estimada(self):
        """Validar que la fecha de entrega no sea en el pasado"""
        fecha = self.cleaned_data.get('fecha_entrega_estimada')
        if fecha and fecha < datetime.date.today():
            raise ValidationError('La fecha de entrega no puede ser en el pasado.')
        return fecha


class PedidoSearchForm(forms.Form):
    """
    Formulario para buscar y filtrar pedidos.
    """
    
    ESTADO_CHOICES = [
        ('', 'Todos'),
        ('pendiente', 'Pendiente'),
        ('facturado', 'Facturado'),
        ('cancelado', 'Cancelado'),
    ]
    
    buscar = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar por código o cliente...'
        })
    )
    
    estado = forms.ChoiceField(
        required=False,
        choices=ESTADO_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    cliente = forms.ModelChoiceField(
        required=False,
        queryset=Cliente.objects.filter(activo=True).order_by('name'),
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        empty_label='Todos los clientes'
    )
    
    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )


class CambiarEstadoPedidoForm(forms.Form):
    """
    Formulario para cambiar el estado de un pedido.
    """
    
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('facturado', 'Facturado'),
        ('cancelado', 'Cancelado'),
    ]
    
    nuevo_estado = forms.ChoiceField(
        choices=ESTADO_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Nuevo Estado'
    )
    
    notas = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Agregar nota sobre el cambio de estado (opcional)'
        }),
        label='Notas'
    )
