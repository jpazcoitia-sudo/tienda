from django.contrib import admin
from .models import Caja, MovimientoCaja, CierreCaja


@admin.register(Caja)
class CajaAdmin(admin.ModelAdmin):
    """Admin para visualizar el estado de Caja (solo lectura)"""
    
    list_display = [
        'saldo_efectivo',
        'saldo_banco',
        'total_disponible',
        'ultima_actualizacion'
    ]
    
    readonly_fields = [
        'saldo_efectivo',
        'saldo_banco',
        'ultima_actualizacion'
    ]
    
    def has_add_permission(self, request):
        """No permitir crear nuevas cajas"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """No permitir eliminar la caja"""
        return False


@admin.register(MovimientoCaja)
class MovimientoCajaAdmin(admin.ModelAdmin):
    """Admin para gestionar movimientos de caja"""
    
    list_display = [
        'fecha',
        'tipo',
        'concepto_resumido',
        'monto_formateado',
        'afecta_efectivo',
        'afecta_banco',
        'usuario'
    ]
    
    list_filter = [
        'tipo',
        'afecta_efectivo',
        'afecta_banco',
        'es_ingreso',
        'fecha'
    ]
    
    search_fields = [
        'concepto',
        'venta__code',
        'compra__code'
    ]
    
    readonly_fields = [
        'fecha',
        'creado',
        'usuario'
    ]
    
    fieldsets = (
        ('Información del Movimiento', {
            'fields': ('tipo', 'monto', 'concepto', 'fecha')
        }),
        ('Afectación', {
            'fields': ('afecta_efectivo', 'afecta_banco', 'es_ingreso')
        }),
        ('Relaciones', {
            'fields': ('venta', 'compra', 'usuario'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('creado',),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'fecha'
    
    def concepto_resumido(self, obj):
        """Muestra concepto truncado"""
        if len(obj.concepto) > 50:
            return obj.concepto[:50] + '...'
        return obj.concepto
    concepto_resumido.short_description = 'Concepto'
    
    def monto_formateado(self, obj):
        """Muestra monto con formato"""
        signo = '+' if obj.es_ingreso else '-'
        return f"{signo} AR$ {obj.monto:,.2f}"
    monto_formateado.short_description = 'Monto'
    
    def has_delete_permission(self, request, obj=None):
        """Solo superusuarios pueden eliminar movimientos"""
        return request.user.is_superuser


@admin.register(CierreCaja)
class CierreCajaAdmin(admin.ModelAdmin):
    """Admin para gestionar cierres de caja"""
    
    list_display = [
        'fecha',
        'saldo_esperado_efectivo',
        'saldo_real_efectivo',
        'diferencia_efectivo',
        'cerrado_por',
        'fecha_hora_cierre'
    ]
    
    list_filter = [
        'fecha',
        'cerrado_por'
    ]
    
    readonly_fields = [
        'fecha_hora_cierre',
        'diferencia_efectivo'
    ]
    
    fieldsets = (
        ('Información del Cierre', {
            'fields': ('fecha', 'cerrado_por', 'fecha_hora_cierre')
        }),
        ('Saldos Iniciales', {
            'fields': ('saldo_inicial_efectivo', 'saldo_inicial_banco')
        }),
        ('Movimientos del Día - Efectivo', {
            'fields': (
                'total_ventas_efectivo',
                'total_compras_efectivo',
                'total_retiros_efectivo',
                'total_gastos_efectivo',
                'total_transferencias_salida',
                'total_transferencias_entrada'
            )
        }),
        ('Movimientos del Día - Banco', {
            'fields': (
                'total_ventas_banco',
                'total_compras_banco',
                'total_retiros_banco',
                'total_gastos_banco'
            ),
            'classes': ('collapse',)
        }),
        ('Saldos Esperados', {
            'fields': ('saldo_esperado_efectivo', 'saldo_esperado_banco')
        }),
        ('Conteo Real', {
            'fields': ('saldo_real_efectivo', 'diferencia_efectivo')
        }),
        ('Notas', {
            'fields': ('notas',)
        }),
    )
    
    date_hierarchy = 'fecha'
    
    def has_delete_permission(self, request, obj=None):
        """Solo superusuarios pueden eliminar cierres"""
        return request.user.is_superuser
