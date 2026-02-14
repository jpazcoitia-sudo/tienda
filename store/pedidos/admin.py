from django.contrib import admin
from .models import Pedido, PedidoItem


class PedidoItemInline(admin.TabularInline):
    """Inline para items de pedido en el admin de Django"""
    model = PedidoItem
    extra = 1
    fields = ['product', 'cantidad', 'precio_unitario', 'total']
    readonly_fields = ['total']


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    """Configuración del admin para Pedidos"""
    
    list_display = [
        'code',
        'cliente',
        'estado',
        'total',
        'fecha_pedido',
        'fecha_entrega_estimada',
        'venta'
    ]
    
    list_filter = [
        'estado',
        'tipo_lista',
        'fecha_pedido',
        'fecha_entrega_estimada'
    ]
    
    search_fields = [
        'code',
        'cliente__name',
        'cliente__dni',
        'notas'
    ]
    
    readonly_fields = [
        'code',
        'sub_total',
        'total',
        'fecha_pedido',
        'date_updated',
        'venta'
    ]
    
    fieldsets = (
        ('Información del Pedido', {
            'fields': ('code', 'cliente', 'estado', 'tipo_lista')
        }),
        ('Fechas', {
            'fields': ('fecha_pedido', 'fecha_entrega_estimada', 'fecha_entrega_real', 'date_updated')
        }),
        ('Totales', {
            'fields': ('sub_total', 'total')
        }),
        ('Notas y Venta', {
            'fields': ('notas', 'venta'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [PedidoItemInline]
    
    def has_delete_permission(self, request, obj=None):
        """No permitir eliminar pedidos desde el admin"""
        return False


@admin.register(PedidoItem)
class PedidoItemAdmin(admin.ModelAdmin):
    """Configuración del admin para Items de Pedido"""
    
    list_display = [
        'pedido',
        'product',
        'cantidad',
        'precio_unitario',
        'total'
    ]
    
    list_filter = ['pedido__estado']
    
    search_fields = [
        'pedido__code',
        'product__name'
    ]
    
    readonly_fields = ['total']
