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

from .models import Supplier, PurchaseProduct, Purchase
from .forms import SupplierForm, PurchaseForm
from inventory.models import Products 

from django.core.exceptions import ValidationError

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
        context['products'] = Products.objects.exclude(tipo_venta='fraccionable').order_by('name')
        
        # Crear JSON de productos para JavaScript
        products_json = {}
        for product in context['products']:
            products_json[product.id] = {
                'id': product.id,
                'name': product.name,
                'cost': float(product.cost),
            }
        context['products_json'] = json.dumps(products_json)
        
        return context
    
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                supplier_id = request.POST.get('supplier')
                numero_comprobante = request.POST.get('numero_comprobante', '')
                product_ids = request.POST.getlist('product[]')
                costs = request.POST.getlist('cost[]')
                qtys = request.POST.getlist('qty[]')
                
                # IVA y Percepción como montos fijos
                iva_monto = Decimal(request.POST.get('iva_pct', 0) or 0)
                perc_monto = Decimal(request.POST.get('perc_pct', 0) or 0)
                
                if not product_ids:
                    messages.error(request, "Debe agregar al menos un producto.")
                    return redirect('purchase:purchase_create')

                supplier = Supplier.objects.get(id=supplier_id)
                purchase = Purchase.objects.create(
                    supplier=supplier,
                    numero_comprobante=numero_comprobante
                )

                # Calcular subtotal para distribuir IVA y Percepción
                subtotal = Decimal(0)
                items_data = []
                for i in range(len(product_ids)):
                    cost = Decimal(costs[i])
                    qty = Decimal(qtys[i])
                    subtotal += cost * qty
                    items_data.append({
                        'product_id': product_ids[i],
                        'cost': cost,
                        'qty': qty
                    })

                # Distribuir IVA y Percepción proporcionalmente
                total_impuestos = iva_monto + perc_monto
                total = Decimal(0)

                for item in items_data:
                    linea = item['cost'] * item['qty']
                    proporcion = linea / subtotal if subtotal > 0 else Decimal(0)
                    impuesto_linea = total_impuestos * proporcion
                    costo_final = item['cost'] + (impuesto_linea / item['qty'])

                    product = Products.objects.get(id=item['product_id'])
                    PurchaseProduct.objects.create(
                        purchase=purchase,
                        supplier=supplier,
                        product=product,
                        cost=costo_final.quantize(Decimal('0.0001')),
                        qty=item['qty']
                    )
                    total += costo_final * item['qty']

                purchase.total = total
                purchase.subtotal_productos = subtotal  # ← el subtotal SIN impuestos
                purchase.iva_monto = iva_monto
                purchase.perc_monto = perc_monto
                purchase.save()
                
                accion = request.POST.get('accion', 'guardar')
                messages.success(request, f"Compra #{purchase.id} registrada. Total: AR$ {total:,.2f}")

                if accion == 'guardar_pagar':
                    return redirect('purchase:purchase_pagar', pk=purchase.pk)
                else:
                    return redirect('purchase:purchase_list')

        except Exception as e:
            messages.error(request, f"Error al registrar la compra: {str(e)}")
            return redirect('purchase:purchase_create')

    
class PurchaseUpdate(LoginRequiredMixin, PermissionRequiredMixin, generic.View):
    template_name = 'purchases/purchase_update.html'
    permission_required = 'purchase.change_purchaseproduct'

    def get(self, request, pk):
        purchase = get_object_or_404(Purchase, pk=pk)
        items = purchase.items.all()
        suppliers = Supplier.objects.all().order_by('name')
        products = Products.objects.exclude(tipo_venta='fraccionable').order_by('name')
        
        products_json = {}
        for product in products:
            products_json[product.id] = {
                'id': product.id,
                'name': product.name,
                'cost': float(product.cost),
            }
        
        context = {
            'purchase': purchase,
            'items': items,
            'suppliers': suppliers,
            'products': products,
            'products_json': json.dumps(products_json),
        }
        return render(request, self.template_name, context)

    def post(self, request, pk):
        purchase = get_object_or_404(Purchase, pk=pk)
        
        try:
            with transaction.atomic():
                supplier_id = request.POST.get('supplier')
                numero_comprobante = request.POST.get('numero_comprobante', '')
                product_ids = request.POST.getlist('product[]')
                costs = request.POST.getlist('cost[]')
                qtys = request.POST.getlist('qty[]')

                if not product_ids:
                    messages.error(request, "Debe agregar al menos un producto.")
                    return redirect('purchase:purchase_update', pk=pk)

                supplier = Supplier.objects.get(id=supplier_id)
                purchase.supplier = supplier
                purchase.numero_comprobante = numero_comprobante

                # Borrar items anteriores y recrear
                purchase.items.all().delete()

                total = Decimal(0)
                for i in range(len(product_ids)):
                    product = Products.objects.get(id=product_ids[i])
                    cost = Decimal(costs[i])
                    qty = Decimal(qtys[i])
                    PurchaseProduct.objects.create(
                        purchase=purchase,
                        supplier=supplier,
                        product=product,
                        cost=cost,
                        qty=qty
                    )
                    total += cost * qty

                purchase.total = total
                purchase.save()

                messages.success(request, f"Compra #{purchase.id} actualizada. Total: AR$ {total:,.2f}")
                return redirect('purchase:purchase_list')

        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return redirect('purchase:purchase_update', pk=pk)


class PurchaseDelete(SuccessMessageMixin, PermissionRequiredMixin, generic.DeleteView):
    model = Purchase
    template_name = 'purchases/purchase_delete.html'
    success_url = reverse_lazy('purchase:purchase_list')
    success_message = "Compra eliminada exitosamente."
    permission_required = 'purchase.delete_purchaseproduct'

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()  
        return super().delete(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['purchase'] = self.get_object() 
        return context

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
