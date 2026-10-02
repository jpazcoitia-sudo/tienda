from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views import generic
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db import transaction
import json
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth.decorators import login_required

from .models import Supplier, PurchaseProduct, Purchase, aplicar_diferencia_stock
from .forms import SupplierForm, PurchaseForm
from inventory.models import Products 

from django.core.exceptions import ValidationError

def _numero(texto):
    """Convierte lo que manda el formulario a Decimal (acepta coma o punto decimal)."""
    return Decimal(str(texto or 0).replace(',', '.'))


def _renglones_del_formulario(request):
    """
    Lee los renglones que manda la pantalla de compra (crear o editar).
    Devuelve una lista de (producto, costo_de_factura, cantidad).
    """
    product_ids = request.POST.getlist('product[]')
    costs = request.POST.getlist('cost[]')
    qtys = request.POST.getlist('qty[]')
    renglones = []
    for i in range(len(product_ids)):
        producto = Products.objects.get(id=product_ids[i])
        renglones.append((producto, _numero(costs[i]), _numero(qtys[i])))
    return renglones


def _productos_para_pantalla():
    """Productos + el JSON que usa el JavaScript de la pantalla de compra."""
    products = Products.objects.all().order_by('name')
    products_json = {}
    for product in products:
        products_json[product.id] = {
            'id': product.id,
            'code': product.code,
            'name': product.name,
            'cost': float(product.cost),
            'codigo_barras': product.codigo_barras or '',
        }
    return products, products_json


class SupplierList(LoginRequiredMixin, PermissionRequiredMixin, generic.ListView):
    model = Supplier
    template_name ='purchases/supplier_list.html'
    context_object_name = 'suppliers'
    permission_required = 'purchase.view_supplier'
    
class SupplierCreate(LoginRequiredMixin, PermissionRequiredMixin, generic.CreateView):
    model = Supplier
    form_class = SupplierForm  
    template_name = 'purchases/supplier_create.html'
    success_url = reverse_lazy('purchase:supplier_list')
    permission_required = 'purchase.add_supplier'
    
    def form_valid(self, form):
        response = super().form_valid(form)
        supplier_name = form.instance.name
        messages.success(self.request, f"Proveedor '{supplier_name}' creado exitosamente.")
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Hubo un error al crear el proveedor. Por favor, intente de nuevo.")
        return self.render_to_response(self.get_context_data(form=form))
    
    
class SupplierUpdate(LoginRequiredMixin, PermissionRequiredMixin, generic.UpdateView):
    model = Supplier
    form_class = SupplierForm  
    template_name = 'purchases/supplier_update.html'
    success_url = reverse_lazy('purchase:supplier_list')
    permission_required = 'purchase.change_supplier'
    
    def form_valid(self, form):
        supplier_name = self.get_object().name
        response = super().form_valid(form)
        messages.success(self.request, f"Proveedor '{supplier_name}' actualizada exitosamente.")
        return response
    
class SupplierDelete(LoginRequiredMixin, SuccessMessageMixin, PermissionRequiredMixin, generic.DeleteView):
    model = Supplier
    template_name = 'purchases/supplier_delete.html'
    success_url = reverse_lazy('purchase:supplier_list')
    permission_required = 'purchase.delete_supplier'
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        supplier_name = self.object.name
        success_message = f"Proveedor '{supplier_name}' eliminado exitosamente."
        messages.success(self.request, success_message)
        return self.delete(request, *args, **kwargs)
    
class PurchaseList(LoginRequiredMixin,PermissionRequiredMixin, generic.ListView):
    model = Purchase
    template_name = 'purchases/purchase_list.html'
    context_object_name = 'purchases'
    ordering = ['-date_added'] 
    permission_required = 'purchase.view_purchaseproduct'
    
# NUEVA: Vista para crear compra con múltiples productos
class PurchaseCreate(LoginRequiredMixin, PermissionRequiredMixin, generic.TemplateView):
    template_name = 'purchases/purchase_create.html'
    permission_required = 'purchase.add_purchaseproduct'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['suppliers'] = Supplier.objects.all().order_by('name')
        products, products_json = _productos_para_pantalla()
        context['products'] = products
        context['products_json'] = json.dumps(products_json)
        context['items_json'] = '[]'   # compra nueva: sin renglones precargados
        return context
    
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                renglones = _renglones_del_formulario(request)
                if not renglones:
                    messages.error(request, "Debe agregar al menos un producto.")
                    return redirect('purchase:purchase_create')

                supplier = Supplier.objects.get(id=request.POST.get('supplier'))
                purchase = Purchase.objects.create(
                    supplier=supplier,
                    numero_comprobante=request.POST.get('numero_comprobante', '')
                )

                # IVA y Percepción llegan como montos fijos (los campos se llaman *_pct por historia).
                purchase.guardar_renglones(
                    renglones,
                    iva_monto=_numero(request.POST.get('iva_pct')),
                    perc_monto=_numero(request.POST.get('perc_pct')),
                )

                accion = request.POST.get('accion', 'guardar')
                messages.success(request, f"Compra #{purchase.id} registrada. Total: AR$ {purchase.total:,.2f}")

                if accion == 'guardar_pagar':
                    return redirect('purchase:purchase_pagar', pk=purchase.pk)
                else:
                    return redirect('purchase:purchase_list')

        except Exception as e:
            messages.error(request, f"Error al registrar la compra: {str(e)}")
            return redirect('purchase:purchase_create')

    
class PurchaseUpdate(LoginRequiredMixin, PermissionRequiredMixin, generic.View):
    # Editar usa LA MISMA pantalla que Crear, con los datos de la compra precargados.
    template_name = 'purchases/purchase_create.html'
    permission_required = 'purchase.change_purchaseproduct'

    def get(self, request, pk):
        purchase = get_object_or_404(Purchase, pk=pk)
        products, products_json = _productos_para_pantalla()

        # Renglones actuales, con el costo DE FACTURA (sin impuestos): es lo que la
        # pantalla muestra y reenvia. El IVA y la percepcion van en sus propios campos.
        items = []
        for item in purchase.items.select_related('product').order_by('id'):
            if not item.product:
                continue
            items.append({
                'product_id': item.product_id,
                'cost': format(item.get_costo_neto().normalize(), 'f'),   # 'f' evita notacion 1E+2
                'qty': str(item.qty),
            })

        context = {
            'purchase': purchase,
            'suppliers': Supplier.objects.all().order_by('name'),
            'products': products,
            'products_json': json.dumps(products_json),
            'items_json': json.dumps(items),
        }
        return render(request, self.template_name, context)

    def post(self, request, pk):
        purchase = get_object_or_404(Purchase, pk=pk)
        
        try:
            with transaction.atomic():
                renglones = _renglones_del_formulario(request)
                if not renglones:
                    messages.error(request, "Debe agregar al menos un producto.")
                    return redirect('purchase:purchase_update', pk=pk)

                purchase.supplier = Supplier.objects.get(id=request.POST.get('supplier'))
                purchase.numero_comprobante = request.POST.get('numero_comprobante', '')

                # Misma funcion que al crear: reparte IVA/percepcion, ajusta el stock
                # por la diferencia y actualiza los costos.
                purchase.guardar_renglones(
                    renglones,
                    iva_monto=_numero(request.POST.get('iva_pct')),
                    perc_monto=_numero(request.POST.get('perc_pct')),
                )

                messages.success(request, f"Compra #{purchase.id} actualizada. Total: AR$ {purchase.total:,.2f}")
                return redirect('purchase:purchase_list')

        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return redirect('purchase:purchase_update', pk=pk)


class PurchaseDetail(LoginRequiredMixin, PermissionRequiredMixin, generic.View):
    """Ver una compra, solo lectura (no modifica nada)."""
    template_name = 'purchases/purchase_detail.html'
    permission_required = 'purchase.view_purchaseproduct'

    def get(self, request, pk):
        purchase = get_object_or_404(Purchase, pk=pk)
        items = list(purchase.items.select_related('product').order_by('id'))
        subtotal = Decimal('0')
        for item in items:
            item.importe_factura = item.get_costo_neto() * item.qty
            subtotal += item.importe_factura
        return render(request, self.template_name, {
            'purchase': purchase,
            'items': items,
            'subtotal': subtotal,
        })


class PurchaseDelete(SuccessMessageMixin, PermissionRequiredMixin, generic.DeleteView):
    model = Purchase
    template_name = 'purchases/purchase_delete.html'
    success_url = reverse_lazy('purchase:purchase_list')
    success_message = "Compra eliminada. El stock de sus productos fue descontado."
    permission_required = 'purchase.delete_purchaseproduct'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['purchase'] = self.object
        context['items'] = self.object.items.select_related('product').order_by('id')
        return context

    def form_valid(self, form):
        # Anotar los productos ANTES de borrar, para avisar despues cuales revisar.
        compra = self.object
        productos = [f"{it.product.code} - {it.product.name}"
                     for it in compra.items.select_related('product').order_by('id') if it.product]
        estaba_pagada = compra.pagado
        respuesta = super().form_valid(form)   # borra la compra (Purchase.delete devuelve el stock)

        if productos:
            messages.warning(
                self.request,
                "El costo y los precios NO se modificaron. Revisalos en Actualizar Precios: "
                + "; ".join(productos) + "."
            )
        if estaba_pagada:
            messages.warning(
                self.request,
                "La compra estaba pagada: el pago en Caja no se revirtió solo. Corregilo en Caja y Banco."
            )
        return respuesta

@login_required
def purchase_payment_list(request):
    """Lista de compras para gestionar pagos"""
    purchases = Purchase.objects.all().order_by('-date_added')
    
    context = {
        'page_title': 'Gestión de Pagos de Compras',
        'purchases': purchases,
    }
    return render(request, 'purchases/payment_list.html', context)


@login_required
@csrf_exempt
def marcar_compra_pagada(request, pk):
    """Marca una compra como pagada y crea movimiento de caja"""
    if request.method == 'POST':
        purchase = get_object_or_404(Purchase, pk=pk)
        
        if purchase.pagado:
            messages.warning(request, 'Esta compra ya fue pagada.')
            return redirect('purchase:payment_list')
        
        forma_pago = request.POST.get('forma_pago', 'efectivo')
        
        # Marcar como pagada
        purchase.marcar_como_pagado(forma_pago=forma_pago)
        
        # Crear movimiento de caja
        try:
            from finances.models import MovimientoCaja
            MovimientoCaja.crear_desde_compra(
                compra=purchase,
                forma_pago=forma_pago,
                usuario=request.user
            )
            messages.success(request, f'✅ Compra pagada: AR$ {purchase.total}')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
        
        return redirect('purchase:payment_list')
    
    return redirect('purchase:payment_list')

def purchase_pagar_view(request, pk):
    """Vista para registrar el pago de una compra recién creada"""
    purchase = get_object_or_404(Purchase, pk=pk)
    
    if request.method == 'POST':
        forma_pago = request.POST.get('forma_pago')
        monto_efectivo = Decimal(request.POST.get('monto_efectivo', 0) or 0)
        monto_banco = Decimal(request.POST.get('monto_banco', 0) or 0)
        
        from finances.models import MovimientoCaja
        
        if monto_efectivo > 0:
            MovimientoCaja.objects.create(
                tipo='compra_efectivo',
                monto=monto_efectivo,
                concepto=f'Pago compra #{purchase.id} - {purchase.supplier}',
                afecta_efectivo=True,
                afecta_banco=False,
                es_ingreso=False,
                usuario=request.user
            )
        
        if monto_banco > 0:
            MovimientoCaja.objects.create(
                tipo='compra_banco',
                monto=monto_banco,
                concepto=f'Pago compra #{purchase.id} - {purchase.supplier}',
                afecta_efectivo=False,
                afecta_banco=True,
                es_ingreso=False,
                usuario=request.user
            )
        
        purchase.marcar_como_pagado(forma_pago=forma_pago)
                
        messages.success(request, f"Pago registrado correctamente para compra #{purchase.id}.")
        return redirect('purchase:payment_list')
    
    context = {
        'purchase': purchase,
    }
    return render(request, 'purchases/purchase_pagar.html', context)

@login_required
def api_productos_compra(request):
    """Devuelve lista de productos disponibles para compra en formato JSON."""
    _products, products_json = _productos_para_pantalla()
    return JsonResponse(products_json)
