import json
import logging
from decimal import Decimal
from datetime import date, datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.db.models import Count, Sum, Q, Prefetch
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.views import generic
from django.views.decorators.csrf import csrf_exempt
from django.contrib.messages.views import SuccessMessageMixin

from .models import Category, Products
from .forms import ProductsForm, CategoryForm
from purchase.models import Supplier, PurchaseProduct
from django.db import transaction

logger = logging.getLogger(__name__)

class CategoryProductsList(LoginRequiredMixin, PermissionRequiredMixin, generic.ListView):

    model = Category
    template_name = "inventory/category_list_link.html"
    context_object_name = "products"
    permission_required = 'inventory.view_category'
    
    def get_queryset(self):
        self.category = get_object_or_404(Category, id=self.kwargs['pk'])
        return Products.objects.filter(category=self.category)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category'] = self.category
        return context
    
class CategoryList(LoginRequiredMixin, PermissionRequiredMixin, generic.ListView):

    model = Category
    template_name = "inventory/category_list.html"
    context_object_name = "categories"
    permission_required = 'inventory.view_category'
    
    def get_queryset(self):
        return Category.objects.annotate(product_count=Count('products'))
    
class CategoryCreate(LoginRequiredMixin, PermissionRequiredMixin, generic.CreateView):
    model = Category
    template_name = "inventory/category_create.html"
    form_class = CategoryForm
    success_url = reverse_lazy('inventory:category_list')
    permission_required = 'inventory.add_category'
    
    def form_valid(self, form):
        response = super().form_valid(form)
        category_name = form.instance.name
        messages.success(self.request, f"Categoria '{category_name}' creado exitosamente.")
        return response

    def form_invalid(self, form):
        logger.error("Error creating category: %s", form.errors)
        messages.error(self.request, "Hubo un error al crear el categoria. Por favor, intente de nuevo.")
        return self.render_to_response(self.get_context_data(form=form))
    
class CategoryUpdate(LoginRequiredMixin, PermissionRequiredMixin, generic.UpdateView):
    model = Category
    template_name = "inventory/category_update.html"
    form_class = CategoryForm
    success_url = reverse_lazy('inventory:category_list')
    permission_required = 'inventory.change_category'

    def form_valid(self, form):
        category_name = self.get_object().name
        response = super().form_valid(form)
        messages.success(self.request, f"Categoría '{category_name}' actualizada exitosamente.")
        return response

    def form_invalid(self, form):
        category_name = self.get_object().name
        messages.error(self.request, f"No se pudo actualizar la categoría '{category_name}'. Por favor corrige los errores.")
        return super().form_invalid(form)
    
class CategoryDelete(LoginRequiredMixin, SuccessMessageMixin,PermissionRequiredMixin, generic.DeleteView):
    model = Category
    template_name = "inventory/category_delete.html"
    success_url = reverse_lazy('inventory:category_list')
    permission_required = 'inventory.delete_category'
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        category_name = self.object.name
        success_message = f"Categoria '{category_name}' eliminado exitosamente."
        messages.success(self.request, success_message)
        return self.delete(request, *args, **kwargs)



class ProductDetailView(LoginRequiredMixin, PermissionRequiredMixin, generic.DetailView):
    model = Products
    template_name = "inventory/product_details.html"
    context_object_name = "product"
    permission_required = 'inventory.view_products'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.get_object()
        
        purchase_products = PurchaseProduct.objects.filter(product=product)
        logger.debug(f"Purchase products count: {purchase_products.count()}")

        cantidad_historica = sum([pp.qty for pp in purchase_products])
        logger.debug(f"Cantidad histórica calculada: {cantidad_historica}")

        context['cantidad_historica'] = cantidad_historica
        return context
    
class ProductList(LoginRequiredMixin, PermissionRequiredMixin, generic.ListView):
    model = Products
    template_name = "inventory/product_list.html"
    context_object_name = "products"
    permission_required = 'inventory.view_products'
    
class ProductCreate(LoginRequiredMixin, PermissionRequiredMixin, generic.CreateView):
    model = Products
    template_name = "inventory/product_create.html"
    form_class = ProductsForm
    success_url = reverse_lazy('inventory:product_list')
    permission_required = 'inventory.add_products'
    
    def form_valid(self, form):
        response = super().form_valid(form)
        product_name = form.instance.name
        messages.success(self.request, f"Producto '{product_name}' creado exitosamente.")
        return response

    def form_invalid(self, form):
        logger.error("Error creating product: %s", form.errors)
        messages.error(self.request, "Hubo un error al crear el producto. Por favor, intente de nuevo.")
        return self.render_to_response(self.get_context_data(form=form))
    
class ProductUpdate(LoginRequiredMixin, PermissionRequiredMixin, generic.UpdateView):
    model = Products
    template_name = "inventory/product_update.html"
    form_class = ProductsForm
    success_url = reverse_lazy('inventory:product_list')
    permission_required = 'inventory.change_products'
    
    def form_valid(self, form):
        product_name = self.get_object().name
        response = super().form_valid(form)
        messages.success(self.request, f"Producto '{product_name}' actualizado exitosamente.")
        return response
    
    def form_invalid(self, form):
        logger.error("Error updating product: %s", form.errors)
        messages.error(self.request, "Hubo un error al actualizar el producto. Por favor, intente de nuevo.")
        return self.render_to_response(self.get_context_data(form=form))

class ProductDelete(LoginRequiredMixin, SuccessMessageMixin,PermissionRequiredMixin,  generic.DeleteView):
    model = Products
    template_name = "inventory/product_delete.html"
    success_url = reverse_lazy('inventory:product_list')
    permission_required = 'inventory.delete_products'
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        product_name = self.object.name
        success_message = f"Producto '{product_name}' eliminado exitosamente."
        messages.success(self.request, success_message)
        return self.delete(request, *args, **kwargs)

"""
Vista para edición rápida de costos y precios de productos
"""
@login_required
def edicion_rapida_precios(request):
    """Vista principal para edición rápida de precios"""
    
    # Obtener productos con último proveedor
    productos = Products.objects.filter(status=1).select_related('category')
    
    # Obtener último proveedor para cada producto
    productos_data = []
    for producto in productos:
        ultimo_proveedor = PurchaseProduct.objects.filter(
            product=producto
        ).select_related('purchase__supplier').order_by('-date_added').first()
        
        proveedor_nombre = ultimo_proveedor.purchase.supplier.name if ultimo_proveedor else 'Sin proveedor registrado'
        
        productos_data.append({
            'id': producto.id,
            'code': producto.code,
            'name': producto.name,
            'cost': float(producto.cost),
            'porc_minorista': calcular_porcentaje(producto.cost, producto.precio_minorista),
            'porc_mayorista': calcular_porcentaje(producto.cost, producto.precio_mayorista),
            'precio_minorista': float(producto.precio_minorista),
            'precio_mayorista': float(producto.precio_mayorista),
            'quantity': producto.quantity,
            'ultimo_proveedor': proveedor_nombre,
            'category': producto.category.name if producto.category else '-',
        })
    
    # Obtener proveedores para filtro
    proveedores = Supplier.objects.all().order_by('name')
    
    context = {
        'page_title': 'Actualización Rápida de Precios',
        'productos_json': json.dumps(productos_data),
        'proveedores': proveedores,
    }
    
    return render(request, 'inventory/edicion_rapida_precios.html', context)


def calcular_porcentaje(costo, precio):
    """Calcula el porcentaje de ganancia"""
    if costo <= 0:
        return 0
    return float(round(((float(precio) - float(costo)) / float(costo)) * 100, 2))


@login_required
@csrf_exempt
def guardar_cambios_precios(request):
    """Guarda los cambios de precios editados"""
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
    try:
        data = json.loads(request.body)
        cambios = data.get('cambios', [])
        
        
        with transaction.atomic():
            actualizados = 0
            errores = []
        
            for cambio in cambios:
                try:
                    producto = Products.objects.get(id=cambio['id'])
                    
                    # Actualizar valores
                    nuevo_costo = Decimal(str(cambio['cost']))
                    porc_minor = Decimal(str(cambio['porc_minorista']))
                    porc_mayor = Decimal(str(cambio['porc_mayorista']))
                    
                    # Actualizar costo
                    # Guardar cada campo específicamente
                    producto.cost = nuevo_costo
                    producto.margen_minorista = porc_minor  # AGREGAR
                    producto.margen_mayorista = porc_mayor  # AGREGAR
                    producto.precio_minorista = round(nuevo_costo * (1 + porc_minor / 100), 2)
                    producto.precio_mayorista = round(nuevo_costo * (1 + porc_mayor / 100), 2)

                    # Guardar solo los campos modificados
                    producto.save(update_fields=['cost', 'precio_minorista', 'precio_mayorista'])

                    # Verificar inmediatamente
                    producto.refresh_from_db()
                    actualizados += 1
                    
                except Products.DoesNotExist:
                    errores.append(f"Producto ID {cambio['id']} no encontrado")
                except Exception as e:
                    errores.append(f"Error en producto {cambio.get('name', '?')}: {str(e)}")
            
            return JsonResponse({
                'success': True,
                'actualizados': actualizados,
                'errores': errores
            })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@csrf_exempt
def actualizacion_masiva_proveedor(request):
    """Actualización masiva de productos por proveedor"""
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
    try:
        data = json.loads(request.body)
        proveedor_id = data.get('proveedor_id')
        accion = data.get('accion')  # 'aumentar_costo', 'disminuir_costo', 'recalcular_porcentajes'
        porcentaje = Decimal(str(data.get('porcentaje', 0)))
        porc_minorista = data.get('porc_minorista')
        porc_mayorista = data.get('porc_mayorista')
        
        # Obtener productos del proveedor
        productos_ids = PurchaseProduct.objects.filter(
            purchase__supplier_id=proveedor_id
        ).values_list('product_id', flat=True).distinct()
        
        productos = Products.objects.filter(id__in=productos_ids, status=1)
        
        actualizados = 0
        
        for producto in productos:
            if accion == 'aumentar_costo':
                producto.cost = producto.cost * (1 + porcentaje / 100)
            elif accion == 'disminuir_costo':
                producto.cost = producto.cost * (1 - porcentaje / 100)
            
            # Recalcular precios
            if porc_minorista is not None:
                porc_min = Decimal(str(porc_minorista))
                producto.precio_minorista = producto.cost * (1 + porc_min / 100)
            
            if porc_mayorista is not None:
                porc_may = Decimal(str(porc_mayorista))
                producto.precio_mayorista = producto.cost * (1 + porc_may / 100)
            
            producto.save()
            actualizados += 1
        
        return JsonResponse({
            'success': True,
            'actualizados': actualizados,
            'mensaje': f'Se actualizaron {actualizados} productos'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
    