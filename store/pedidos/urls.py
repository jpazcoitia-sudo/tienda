from django.urls import path
from . import views

app_name = 'pedidos'

urlpatterns = [
    # Lista y creación
    path('', views.pedido_list, name='pedido_list'),
    path('crear/', views.pedido_create, name='pedido_create'),
    path('guardar/', views.save_pedido, name='save_pedido'),
    
    # Detalle y acciones
    path('<int:pk>/', views.pedido_detail, name='pedido_detail'),
    path('<int:pk>/cambiar-estado/', views.cambiar_estado, name='cambiar_estado'),
    path('<int:pk>/convertir-venta/', views.convertir_a_venta, name='convertir_venta'),
    path('<int:pk>/cancelar/', views.pedido_delete, name='pedido_delete'),
]
