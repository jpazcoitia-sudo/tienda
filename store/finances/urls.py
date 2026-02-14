from django.urls import path
from . import views

app_name = 'finances'

urlpatterns = [
    # Dashboard principal
    path('', views.dashboard_caja, name='dashboard'),
    
    # Operaciones
    path('transferir/', views.transferir_dinero, name='transferir'),
    path('retiro/', views.registrar_retiro, name='retiro'),
    path('gasto/', views.registrar_gasto, name='gasto'),
    path('ajuste/', views.ajuste_manual, name='ajuste'),
    
    # Historial y reportes
    path('historial/', views.historial_movimientos, name='historial'),
    path('movimiento/<int:pk>/', views.detalle_movimiento, name='detalle_movimiento'),
    
    # Cierre de caja
    path('cierre/', views.cierre_caja, name='cierre_caja'),
    path('cierres/', views.lista_cierres, name='lista_cierres'),
    path('cierre/<int:pk>/', views.detalle_cierre, name='detalle_cierre'),
    
    # Reportes
    path('reportes/', views.reportes_financieros, name='reportes'),
    path('reporte/flujo-caja/', views.reporte_flujo_caja, name='reporte_flujo_caja'),
]
