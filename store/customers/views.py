from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.db.models import Q, Sum, Count
from .models import Cliente
from .forms import ClienteForm, ClienteSearchForm

# ============================================
# VISTAS BASADAS EN CLASES (CBV)
# ============================================

class ClienteListView(LoginRequiredMixin, ListView):
    """
    Vista para listar todos los clientes con filtros de búsqueda.
    """
    model = Cliente
    template_name = 'customers/customer_list.html'
    context_object_name = 'clientes'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Cliente.objects.all()
        
        # Obtener parámetros de búsqueda
        search = self.request.GET.get('search', '')
        tipo_cliente = self.request.GET.get('tipo_cliente', '')
        activo = self.request.GET.get('activo', '')
        
        # Filtrar por búsqueda de texto
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(dni__icontains=search) |
                Q(phone__icontains=search) |
                Q(email__icontains=search)
            )
        
        # Filtrar por tipo de cliente
        if tipo_cliente:
            queryset = queryset.filter(tipo_cliente=tipo_cliente)
        
        # Filtrar por estado activo
        if activo == 'true':
            queryset = queryset.filter(activo=True)
        elif activo == 'false':
            queryset = queryset.filter(activo=False)
        
        return queryset.order_by('-date_added')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = ClienteSearchForm(self.request.GET)
        context['total_clientes'] = Cliente.objects.filter(activo=True).count()
        return context


class ClienteDetailView(LoginRequiredMixin, DetailView):
    """
    Vista para ver el detalle de un cliente y su historial de ventas.
    """
    model = Cliente
    template_name = 'customers/customer_detail.html'
    context_object_name = 'cliente'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cliente = self.get_object()
        
        # Importar Sales aquí para evitar circular import
        from pos.models import Sales
        
        # Obtener ventas del cliente
        ventas = Sales.objects.filter(cliente=cliente).order_by('-date_added')
        
        # Estadísticas
        context['ventas'] = ventas[:10]  # Últimas 10 ventas
        context['total_ventas'] = ventas.count()
        context['total_facturado'] = ventas.aggregate(
            total=Sum('grand_total')
        )['total'] or 0
        
        # Productos más comprados
        from pos.models import salesItems
        productos_stats = salesItems.objects.filter(
            sale__cliente=cliente
        ).values(
            'product__name'
        ).annotate(
            cantidad_total=Sum('qty'),
            veces_comprado=Count('id')
        ).order_by('-cantidad_total')[:5]
        
        context['productos_top'] = productos_stats
        
        return context


class ClienteCreateView(LoginRequiredMixin, CreateView):
    """
    Vista para crear un nuevo cliente.
    """
    model = Cliente
    form_class = ClienteForm
    template_name = 'customers/customer_form.html'
    success_url = reverse_lazy('customers:customer_list')
    
    def form_valid(self, form):
        messages.success(
            self.request,
            f'Cliente "{form.instance.name}" creado exitosamente.'
        )
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Crear Nuevo Cliente'
        context['button_text'] = 'Crear Cliente'
        return context


class ClienteUpdateView(LoginRequiredMixin, UpdateView):
    """
    Vista para editar un cliente existente.
    """
    model = Cliente
    form_class = ClienteForm
    template_name = 'customers/customer_form.html'
    success_url = reverse_lazy('customers:customer_list')
    
    def form_valid(self, form):
        messages.success(
            self.request,
            f'Cliente "{form.instance.name}" actualizado exitosamente.'
        )
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Editar Cliente: {self.object.name}'
        context['button_text'] = 'Guardar Cambios'
        return context


class ClienteDeleteView(LoginRequiredMixin, DeleteView):
    """
    Vista para eliminar un cliente.
    Nota: En lugar de eliminar, se recomienda desactivar.
    """
    model = Cliente
    template_name = 'customers/customer_confirm_delete.html'
    success_url = reverse_lazy('customers:customer_list')
    
    def delete(self, request, *args, **kwargs):
        cliente = self.get_object()
        messages.success(
            self.request,
            f'Cliente "{cliente.name}" eliminado exitosamente.'
        )
        return super().delete(request, *args, **kwargs)


# ============================================
# VISTAS BASADAS EN FUNCIONES (FBV)
# ============================================

@login_required
def cliente_toggle_activo(request, pk):
    """
    Activa o desactiva un cliente sin eliminarlo.
    """
    cliente = get_object_or_404(Cliente, pk=pk)
    cliente.activo = not cliente.activo
    cliente.save()
    
    estado = "activado" if cliente.activo else "desactivado"
    messages.success(request, f'Cliente "{cliente.name}" {estado} exitosamente.')
    
    return redirect('customers:customer_detail', pk=pk)
