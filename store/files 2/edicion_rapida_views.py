"""
Vista para edición rápida de costos y precios de productos
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Prefetch
from inventory.models import Products, Category
from purchase.models import Supplier, PurchaseProduct
from decimal import Decimal
import json


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
    proveedores = Supplier.objects.filter(status=1).order_by('name')
    
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
    return round(((precio - costo) / costo) * 100, 2)


@login_required
@csrf_exempt
def guardar_cambios_precios(request):
    """Guarda los cambios de precios editados"""
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
    try:
        data = json.loads(request.body)
        cambios = data.get('cambios', [])
        
        actualizados = 0
        errores = []
        
        for cambio in cambios:
            try:
                producto = Products.objects.get(id=cambio['id'])
                
                # Actualizar valores
                producto.cost = Decimal(str(cambio['cost']))
                porc_minor = Decimal(str(cambio['porc_minorista']))
                porc_mayor = Decimal(str(cambio['porc_mayorista']))
                
                # Calcular nuevos precios
                producto.precio_minorista = producto.cost * (1 + porc_minor / 100)
                producto.precio_mayorista = producto.cost * (1 + porc_mayor / 100)
                
                producto.save()
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
