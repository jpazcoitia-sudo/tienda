from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal
from .models import Caja, MovimientoCaja, CierreCaja
import datetime


class TransferenciaForm(forms.Form):
    """Formulario para transferir dinero entre Caja y Banco"""
    
    DIRECCION_CHOICES = [
        ('caja_banco', '💵 Caja → 🏦 Banco (Depositar)'),
        ('banco_caja', '🏦 Banco → 💵 Caja (Retirar del Banco)'),
    ]
    
    direccion = forms.ChoiceField(
        choices=DIRECCION_CHOICES,
        widget=forms.RadioSelect,
        label='Dirección de la Transferencia'
    )
    
    monto = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01'
        }),
        label='Monto a Transferir'
    )
    
    concepto = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Ej: Depósito diario, Extracción para gastos, etc.'
        }),
        label='Concepto (Opcional)'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Obtener saldos actuales para mostrar
        self.caja = Caja.get_instance()
    
    def clean(self):
        cleaned_data = super().clean()
        direccion = cleaned_data.get('direccion')
        monto = cleaned_data.get('monto')
        
        if direccion and monto:
            caja = Caja.get_instance()
            
            if direccion == 'caja_banco':
                # Verificar que hay suficiente efectivo en caja
                if monto > caja.saldo_efectivo:
                    raise ValidationError(
                        f'No hay suficiente efectivo en caja. '
                        f'Disponible: AR$ {caja.saldo_efectivo}'
                    )
            else:  # banco_caja
                # Verificar que hay suficiente en banco
                if monto > caja.saldo_banco:
                    raise ValidationError(
                        f'No hay suficiente saldo en banco. '
                        f'Disponible: AR$ {caja.saldo_banco}'
                    )
        
        return cleaned_data


class RetiroForm(forms.Form):
    """Formulario para registrar retiros de efectivo o banco"""
    
    ORIGEN_CHOICES = [
        ('efectivo', '💵 Caja (Efectivo)'),
        ('banco', '🏦 Banco'),
    ]
    
    origen = forms.ChoiceField(
        choices=ORIGEN_CHOICES,
        widget=forms.RadioSelect,
        label='Retirar de'
    )
    
    monto = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01'
        }),
        label='Monto del Retiro'
    )
    
    concepto = forms.CharField(
        max_length=500,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Ej: Pago a proveedor particular, Gastos personales, etc.'
        }),
        label='Concepto del Retiro'
    )
    
    def clean(self):
        cleaned_data = super().clean()
        origen = cleaned_data.get('origen')
        monto = cleaned_data.get('monto')
        
        if origen and monto:
            caja = Caja.get_instance()
            
            if origen == 'efectivo':
                if monto > caja.saldo_efectivo:
                    raise ValidationError(
                        f'No hay suficiente efectivo en caja. '
                        f'Disponible: AR$ {caja.saldo_efectivo}'
                    )
            else:  # banco
                if monto > caja.saldo_banco:
                    raise ValidationError(
                        f'No hay suficiente saldo en banco. '
                        f'Disponible: AR$ {caja.saldo_banco}'
                    )
        
        return cleaned_data


class GastoForm(forms.Form):
    """Formulario para registrar gastos/egresos"""
    
    PAGAR_CON_CHOICES = [
        ('efectivo', '💵 Efectivo (Caja)'),
        ('banco', '🏦 Banco'),
    ]
    
    pagar_con = forms.ChoiceField(
        choices=PAGAR_CON_CHOICES,
        widget=forms.RadioSelect,
        label='Pagar con'
    )
    
    monto = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01'
        }),
        label='Monto del Gasto'
    )
    
    concepto = forms.CharField(
        max_length=500,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Ej: Pago de servicios, Reparación equipo, Alquiler, etc.'
        }),
        label='Concepto del Gasto'
    )
    
    def clean(self):
        cleaned_data = super().clean()
        pagar_con = cleaned_data.get('pagar_con')
        monto = cleaned_data.get('monto')
        
        if pagar_con and monto:
            caja = Caja.get_instance()
            
            if pagar_con == 'efectivo':
                if monto > caja.saldo_efectivo:
                    raise ValidationError(
                        f'No hay suficiente efectivo en caja. '
                        f'Disponible: AR$ {caja.saldo_efectivo}'
                    )
            else:  # banco
                if monto > caja.saldo_banco:
                    raise ValidationError(
                        f'No hay suficiente saldo en banco. '
                        f'Disponible: AR$ {caja.saldo_banco}'
                    )
        
        return cleaned_data


class AjusteManualForm(forms.Form):
    """Formulario para ajustes manuales de saldos"""
    
    CUENTA_CHOICES = [
        ('efectivo', '💵 Efectivo (Caja)'),
        ('banco', '🏦 Banco'),
    ]
    
    TIPO_AJUSTE_CHOICES = [
        ('incremento', '➕ Incrementar Saldo'),
        ('decremento', '➖ Decrementar Saldo'),
    ]
    
    cuenta = forms.ChoiceField(
        choices=CUENTA_CHOICES,
        widget=forms.RadioSelect,
        label='Cuenta a Ajustar'
    )
    
    tipo_ajuste = forms.ChoiceField(
        choices=TIPO_AJUSTE_CHOICES,
        widget=forms.RadioSelect,
        label='Tipo de Ajuste'
    )
    
    monto = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01'
        }),
        label='Monto del Ajuste'
    )
    
    concepto = forms.CharField(
        max_length=500,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Explique el motivo del ajuste (requerido para auditoría)'
        }),
        label='Motivo del Ajuste (Obligatorio)'
    )
    
    def clean(self):
        cleaned_data = super().clean()
        cuenta = cleaned_data.get('cuenta')
        tipo_ajuste = cleaned_data.get('tipo_ajuste')
        monto = cleaned_data.get('monto')
        
        # Si es decremento, verificar que hay suficiente saldo
        if cuenta and tipo_ajuste == 'decremento' and monto:
            caja = Caja.get_instance()
            
            if cuenta == 'efectivo':
                if monto > caja.saldo_efectivo:
                    raise ValidationError(
                        f'No se puede decrementar más del saldo actual. '
                        f'Disponible: AR$ {caja.saldo_efectivo}'
                    )
            else:  # banco
                if monto > caja.saldo_banco:
                    raise ValidationError(
                        f'No se puede decrementar más del saldo actual. '
                        f'Disponible: AR$ {caja.saldo_banco}'
                    )
        
        return cleaned_data


class CierreCajaForm(forms.ModelForm):
    """Formulario para el cierre de caja diario"""
    
    class Meta:
        model = CierreCaja
        fields = ['fecha', 'saldo_real_efectivo', 'notas']
        widgets = {
            'fecha': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'saldo_real_efectivo': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'notas': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Observaciones sobre el cierre (opcional)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Establecer fecha de hoy por defecto
        if not self.instance.pk:
            self.fields['fecha'].initial = datetime.date.today()
    
    def clean_fecha(self):
        """Validar que no exista ya un cierre para esta fecha"""
        fecha = self.cleaned_data['fecha']
        
        if not self.instance.pk:  # Solo validar en creación
            if CierreCaja.objects.filter(fecha=fecha).exists():
                raise ValidationError(
                    f'Ya existe un cierre de caja para la fecha {fecha.strftime("%d/%m/%Y")}'
                )
        
        return fecha


class FiltroMovimientosForm(forms.Form):
    """Formulario para filtrar movimientos de caja"""
    
    TIPO_CHOICES = [('', 'Todos los tipos')] + MovimientoCaja.TIPO_CHOICES
    
    tipo = forms.ChoiceField(
        choices=TIPO_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Tipo de Movimiento'
    )
    
    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label='Desde'
    )
    
    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label='Hasta'
    )
    
    cuenta = forms.ChoiceField(
        choices=[
            ('', 'Todas las cuentas'),
            ('efectivo', 'Solo Efectivo'),
            ('banco', 'Solo Banco'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Cuenta'
    )
