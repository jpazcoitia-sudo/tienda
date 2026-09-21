from django.shortcuts import render, redirect

VENDEDOR_GROUP = 'Vendedor'

# Vistas que el grupo Vendedor PUEDE usar.
# view_name = 'namespace:url_name' (o 'url_name' si no hay namespace).
VENDEDOR_ALLOWED = {
    # Autenticacion / cuenta
    'login', 'login-user', 'logout', 'password_reset', 'password_reset_confirm',
    # POS / ventas: crear y ver (borrar queda bloqueado por su propio permiso)
    'pos:pos-page', 'pos:checkout-modal', 'pos:save-pos', 'pos:sales-page', 'pos:receipt-modal',
    # Pedidos: ver y crear
    'pedidos:pedido_list', 'pedidos:pedido_create', 'pedidos:save_pedido', 'pedidos:pedido_detail',
    # Clientes: ver y elegir
    'customers:customer_list', 'customers:customer_detail',
}


class VendedorAccessMiddleware:
    """'Portero': si el usuario esta en el grupo 'Vendedor', solo lo deja
    entrar a las vistas de VENDEDOR_ALLOWED. Todo lo demas -> 403.
    Usuarios que NO son del grupo (ej. el dueño) no se ven afectados.

    Para ampliar/reducir lo que puede hacer Vendedor, editar VENDEDOR_ALLOWED.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return None
        if user.is_superuser:
            return None
        if not user.groups.filter(name=VENDEDOR_GROUP).exists():
            return None

        match = request.resolver_match
        if match is None:
            return None

        view_name = match.view_name
        # Su pantalla de inicio es el POS
        if view_name == 'home-page':
            return redirect('pos:pos-page')
        if view_name in VENDEDOR_ALLOWED:
            return None
        # Cualquier otra cosa: prohibido
        return render(request, 'errors/403.html', status=403)
