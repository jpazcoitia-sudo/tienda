from django.contrib import admin
from .models import Cliente

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    """
    Configuración del panel de administración para Cliente.
    """
    
    list_display = [
        'name',
        'dni',
        'phone',
        'email',
        'tipo_cliente',
        'activo',
        'date_added',
    ]
    
    list_filter = [
        'tipo_cliente',
        'activo',
        'date_added',
    ]
    
    search_fields = [
        'name',
        'dni',
        'phone',
        'email',
    ]
    
    readonly_fields = [
        'date_added',
        'date_updated',
    ]
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'dni', 'tipo_cliente')
        }),
        ('Información de Contacto', {
            'fields': ('phone', 'email', 'address')
        }),
        ('Estado y Notas', {
            'fields': ('activo', 'notas')
        }),
        ('Metadata', {
            'fields': ('date_added', 'date_updated'),
            'classes': ('collapse',)
        }),
    )
    
    list_per_page = 25
    
    actions = ['activar_clientes', 'desactivar_clientes']
    
    def activar_clientes(self, request, queryset):
        """Acción para activar clientes seleccionados"""
        updated = queryset.update(activo=True)
        self.message_user(request, f'{updated} cliente(s) activado(s) exitosamente.')
    activar_clientes.short_description = "Activar clientes seleccionados"
    
    def desactivar_clientes(self, request, queryset):
        """Acción para desactivar clientes seleccionados"""
        updated = queryset.update(activo=False)
        self.message_user(request, f'{updated} cliente(s) desactivado(s) exitosamente.')
    desactivar_clientes.short_description = "Desactivar clientes seleccionados"
