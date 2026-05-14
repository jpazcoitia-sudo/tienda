from django.urls import path
from . import views

app_name = 'customers'

urlpatterns = [
    # Listar clientes
    path('', views.ClienteListView.as_view(), name='customer_list'),
    
    # Ver detalle de cliente
    path('<int:pk>/', views.ClienteDetailView.as_view(), name='customer_detail'),
    
    # Crear cliente
    path('create/', views.ClienteCreateView.as_view(), name='customer_create'),
    
    # Editar cliente
    path('<int:pk>/edit/', views.ClienteUpdateView.as_view(), name='customer_update'),
    
    # Eliminar cliente
    path('<int:pk>/delete/', views.ClienteDeleteView.as_view(), name='customer_delete'),
    
    # Activar/Desactivar cliente
    path('<int:pk>/toggle-activo/', views.cliente_toggle_activo, name='customer_toggle_activo'),

    # Registrar pago cuenta corriente
    path('<int:pk>/registrar-pago/', views.registrar_pago, name='registrar_pago'),
]
