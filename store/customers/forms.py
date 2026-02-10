from django import forms
from .models import Cliente

class ClienteForm(forms.ModelForm):
    """
    Formulario para crear y editar clientes.
    """
    
    class Meta:
        model = Cliente
        fields = [
            'name',
            'dni',
            'phone',
            'email',
            'address',
            'tipo_cliente',
            'activo',
            'notas',
        ]
        
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Juan Pérez'
            }),
            'dni': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 12345678 o 20-12345678-9'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: +54 9 11 1234-5678'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: cliente@ejemplo.com'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Dirección completa del cliente'
            }),
            'tipo_cliente': forms.Select(attrs={
                'class': 'form-select'
            }),
            'activo': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'notas': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Observaciones o comentarios sobre el cliente'
            }),
        }
        
        labels = {
            'name': 'Nombre Completo',
            'dni': 'DNI/CUIT',
            'phone': 'Teléfono',
            'email': 'Email',
            'address': 'Dirección',
            'tipo_cliente': 'Tipo de Cliente',
            'activo': 'Cliente Activo',
            'notas': 'Notas',
        }
        
        help_texts = {
            'dni': 'Documento único del cliente (sin puntos ni guiones)',
            'tipo_cliente': 'Mayorista: aplica precios mayoristas por defecto',
            'activo': 'Desmarcar para desactivar el cliente sin eliminarlo',
        }
    
    def clean_dni(self):
        """
        Valida que el DNI no esté duplicado (excepto en edición del mismo cliente)
        """
        dni = self.cleaned_data.get('dni')
        
        # Remover espacios y guiones para validación
        dni_limpio = dni.replace(' ', '').replace('-', '')
        
        # Verificar si ya existe otro cliente con ese DNI
        qs = Cliente.objects.filter(dni=dni_limpio)
        
        # Si estamos editando, excluir el cliente actual
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        
        if qs.exists():
            raise forms.ValidationError(
                f'Ya existe un cliente registrado con el DNI/CUIT: {dni}'
            )
        
        return dni_limpio
    
    def clean_phone(self):
        """
        Limpia el formato del teléfono
        """
        phone = self.cleaned_data.get('phone')
        if phone:
            # Remover caracteres no numéricos excepto + y espacios
            return phone.strip()
        return phone
    
    def clean_email(self):
        """
        Valida y normaliza el email
        """
        email = self.cleaned_data.get('email')
        if email:
            return email.lower().strip()
        return email


class ClienteSearchForm(forms.Form):
    """
    Formulario para buscar clientes.
    """
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar por nombre, DNI, teléfono...'
        }),
        label='Buscar'
    )
    
    tipo_cliente = forms.ChoiceField(
        required=False,
        choices=[('', 'Todos')] + Cliente.TIPO_CLIENTE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Tipo'
    )
    
    activo = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'Todos'),
            ('true', 'Activos'),
            ('false', 'Inactivos')
        ],
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Estado'
    )
