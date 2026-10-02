from django.contrib import admin

from .models import Category, Products
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'status', 'date_added', 'date_updated')
    search_fields = ('name', 'description')
    list_filter = ('status', 'date_added', 'date_updated')

class ProductsAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'category', 'cost', 'precio_minorista', 'precio_mayorista', 'status', 'quantity', 'eliminado', 'date_added', 'date_updated')
    search_fields = ('code', 'name', 'description')
    list_filter = ('eliminado', 'status', 'category', 'date_added', 'date_updated')
    actions = ['restaurar_productos']

    def get_queryset(self, request):
        # En el admin se ven TODOS, tambien los eliminados (filtro "Eliminado" a la derecha)
        return Products.todos.all()

    @admin.action(description='Restaurar productos eliminados')
    def restaurar_productos(self, request, queryset):
        cantidad = 0
        for producto in queryset.filter(eliminado=True):
            producto.restaurar()
            cantidad += 1
        self.message_user(request, f'{cantidad} producto(s) restaurado(s). Revisar código de barras y PLU.')
    

admin.site.register(Category, CategoryAdmin)
admin.site.register(Products, ProductsAdmin)