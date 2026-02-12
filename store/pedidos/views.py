from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from django.db import models
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime
import json

from .models import Pedido, PedidoItem
from .forms import PedidoForm, PedidoSearchForm, CambiarEstadoPedidoForm
from customers.models import Cliente
from inventory.models import Products
from pos.models import Sales, salesItems


@login_required
@permission_required('pedidos.view_pedido', raise_exception=True)
def pedido_list(request):
    """
    Lista de pedidos con búsqueda y filtros.
    """
    form = PedidoSearchForm(request.GET or None)
    pedidos = Pedido.objects.select_related('cliente').prefetch_related('items').all()
    
    # Aplicar filtros
    if form.is_valid():
        if form.cleaned_data.get('buscar'):
            buscar = form.cleaned_data['buscar']
            pedidos = pedidos.filter(
                models.Q(code__icontains=buscar) |
                models.Q(cliente__name__icontains=buscar) |
                models.Q(cliente__dni__icontains=buscar)
            )
        
        if form.cleaned_data.get('estado'):
            pedidos = pedidos.filter(estado=form.cleaned_data['estado'])
        
        if form.cleaned_data.get('cliente'):
            pedidos = pedidos.filter(cliente=form.cleaned_data['cliente'])
        
        if form.cleaned_data.get('fecha_desde'):
            pedidos = pedidos.filter(fecha_pedido__date__gte=form.cleaned_data['fecha_desde'])
        
        if form.cleaned_data.get('fecha_hasta'):
            pedidos = pedidos.filter(fecha_pedido__date__lte=form.cleaned_data['fecha_hasta'])
    
    # Estadísticas
    stats = {
        'total': pedidos.count(),
        'pendientes': pedidos.filter(estado='pendiente').count(),
        'facturados': pedidos.filter(estado='facturado').count(),
        'cancelados': pedidos.filter(estado='cancelado').count(),
    }
    
    context = {
        'page_title': 'Gestión de Pedidos',
        'pedidos': pedidos,
        'form': form,
        'stats': stats,
    }
    
    return render(request, 'pedidos/pedido_list.html', context)


@login_required
@permission_required('pedidos.view_pedido', raise_exception=True)
def pedido_detail(request, pk):
    """
    Detalle de un pedido.
    """
    pedido = get_object_or_404(
        Pedido.objects.select_related('cliente', 'venta').prefetch_related('items__product'),
        pk=pk
    )
    
    # Verificar disponibilidad de stock
    stock_ok, items_sin_stock = pedido.stock_disponible()
    
    context = {
        'page_title': f'Pedido {pedido.code}',
        'pedido': pedido,
        'stock_ok': stock_ok,
        'items_sin_stock': items_sin_stock,
    }
    
    return render(request, 'pedidos/pedido_detail.html', context)


@login_required
@permission_required('pedidos.add_pedido', raise_exception=True)
def pedido_create(request):
    """
    Vista para tomar un nuevo pedido (similar al POS).
    """
    products = Products.objects.filter(status=1).order_by('name')
    clientes = Cliente.objects.filter(activo=True).order_by('name')
    
    # Preparar datos de productos para JavaScript
    product_json = []
    for product in products:
        product_json.append({
            'id': product.id,
            'name': product.name,
            'precio_mayorista': float(product.precio_mayorista),
            'precio_minorista': float(product.precio_minorista),
        })
    
    context = {
        'page_title': 'Tomar Nuevo Pedido',
        'products': products,
        'clientes': clientes,
        'product_json': json.dumps(product_json),
    }
    
    return render(request, 'pedidos/pedido_create.html', context)


@login_required
@permission_required('pedidos.add_pedido', raise_exception=True)
@csrf_exempt
def save_pedido(request):
    """
    Guardar un nuevo pedido (AJAX).
    """
    resp = {'status': 'failed', 'msg': ''}
    
    if request.method != 'POST':
        resp['msg'] = 'Método no permitido'
        return JsonResponse(resp)
    
    data = request.POST
    
    try:
        with transaction.atomic():
            # Generar código de pedido
            pref = datetime.now().year
            i = 1
            while True:
                code = f'PED-{pref}-{i:05d}'
                if not Pedido.objects.filter(code=code).exists():
                    break
                i += 1
            
            # Obtener cliente
            cliente_id = data.get('cliente_id')
            if not cliente_id:
                resp['msg'] = 'Debe seleccionar un cliente'
                return JsonResponse(resp)
            
            cliente = get_object_or_404(Cliente, pk=cliente_id)
            
            # Crear pedido
            tipo_lista = data.get('tipo_lista', 'minorista')
            fecha_entrega = data.get('fecha_entrega_estimada', None)
            
            pedido = Pedido.objects.create(
                code=code,
                cliente=cliente,
                tipo_lista=tipo_lista,
                sub_total=0,
                total=0,
                fecha_entrega_estimada=fecha_entrega if fecha_entrega else None,
                notas=data.get('notas', ''),
                estado='pendiente'
            )
            
            # Crear items del pedido
            productos = data.getlist('product[]')
            cantidades = data.getlist('qty[]')
            precios = data.getlist('price[]')
            
            if not productos:
                resp['msg'] = 'El pedido debe tener al menos un producto'
                return JsonResponse(resp)
            
            for i, prod_id in enumerate(productos):
                product = get_object_or_404(Products, id=prod_id)
                cantidad = float(cantidades[i])
                precio = float(precios[i])
                
                PedidoItem.objects.create(
                    pedido=pedido,
                    product=product,
                    cantidad=cantidad,
                    precio_unitario=precio,
                    total=cantidad * precio
                )
            
            # Calcular totales
            pedido.calcular_totales()
            
            resp['status'] = 'success'
            resp['pedido_id'] = pedido.pk
            resp['code'] = pedido.code
            messages.success(request, f'Pedido {pedido.code} creado exitosamente para {cliente.name}.')
    
    except Exception as e:
        resp['msg'] = f'Error al crear pedido: {str(e)}'
    
    return JsonResponse(resp)


@login_required
@permission_required('pedidos.change_pedido', raise_exception=True)
def cambiar_estado(request, pk):
    """
    Cambiar el estado de un pedido.
    """
    pedido = get_object_or_404(Pedido, pk=pk)
    
    if request.method == 'POST':
        form = CambiarEstadoPedidoForm(request.POST)
        if form.is_valid():
            nuevo_estado = form.cleaned_data['nuevo_estado']
            notas_adicionales = form.cleaned_data.get('notas', '')
            
            # Actualizar estado
            pedido.estado = nuevo_estado
            
            # Agregar notas si hay
            if notas_adicionales:
                if pedido.notas:
                    pedido.notas += f"\n\n[{timezone.now().strftime('%d/%m/%Y %H:%M')}] {notas_adicionales}"
                else:
                    pedido.notas = f"[{timezone.now().strftime('%d/%m/%Y %H:%M')}] {notas_adicionales}"
            
            pedido.save()
            
            messages.success(request, f'Estado del pedido {pedido.code} actualizado a: {pedido.get_estado_display()}')
            return redirect('pedidos:pedido_detail', pk=pedido.pk)
    else:
        form = CambiarEstadoPedidoForm(initial={'nuevo_estado': pedido.estado})
    
    context = {
        'page_title': f'Cambiar Estado - {pedido.code}',
        'pedido': pedido,
        'form': form,
    }
    
    return render(request, 'pedidos/cambiar_estado.html', context)


@login_required
@permission_required('pedidos.change_pedido', raise_exception=True)
def convertir_a_venta(request, pk):
    """
    Redirige al POS con los datos del pedido precargados.
    El usuario podrá revisar y procesar la venta desde el POS.
    """
    pedido = get_object_or_404(Pedido, pk=pk)
    
    # Validar que puede convertirse
    if not pedido.puede_convertirse_a_venta():
        messages.error(request, 'Este pedido no puede convertirse en venta.')
        return redirect('pedidos:pedido_detail', pk=pedido.pk)
    
    # Guardar datos del pedido en la sesión para cargarlos en el POS
    request.session['pedido_a_facturar'] = {
        'pedido_id': pedido.pk,
        'cliente_id': pedido.cliente.pk,
        'tipo_lista': pedido.tipo_lista,
        'items': [
            {
                'product_id': item.product.pk,
                'cantidad': float(item.cantidad),
                'precio': float(item.precio_unitario)
            }
            for item in pedido.items.all()
        ]
    }
    
    messages.info(
        request,
        f'Pedido {pedido.code} cargado en el POS. Revise los datos y procese la venta.'
    )
    
    return redirect('pos:pos-page')


@login_required
@permission_required('pedidos.delete_pedido', raise_exception=True)
def pedido_delete(request, pk):
    """
    Eliminar/cancelar un pedido.
    """
    pedido = get_object_or_404(Pedido, pk=pk)
    
    if not pedido.puede_cancelarse():
        messages.error(request, 'Este pedido no puede cancelarse.')
        return redirect('pedidos:pedido_detail', pk=pedido.pk)
    
    if request.method == 'POST':
        code = pedido.code
        pedido.estado = 'cancelado'
        pedido.save()
        
        messages.success(request, f'Pedido {code} cancelado.')
        return redirect('pedidos:pedido_list')
    
    context = {
        'page_title': f'Cancelar Pedido - {pedido.code}',
        'pedido': pedido,
    }
    
    return render(request, 'pedidos/pedido_confirm_delete.html', context)
