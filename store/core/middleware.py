from django.contrib.auth.views import redirect_to_login
from django.shortcuts import render, redirect

VENDEDOR_GROUP = 'Vendedor'

# Vistas que se pueden abrir SIN iniciar sesion. Todo lo demas exige login.
# view_name = 'namespace:url_name' (o 'url_name' si no hay namespace).
PUBLICAS = {
    'login', 'login-user', 'logout',
    'redirect-admin',
    # Planilla de emergencia: la vista misma exige sesion o un token secreto.
    'inventory:planilla_emergencia',
}

# Vistas que puede usar un usuario que NO es superusuario (hoy: el grupo Vendedor).
VENDEDOR_ALLOWED = {
    # Autenticacion / cuenta
    'login', 'login-user', 'logout',
    # POS / ventas: crear y ver (borrar queda bloqueado por su propio permiso)
    'pos:pos-page', 'pos:checkout-modal', 'pos:save-pos', 'pos:sales-page', 'pos:receipt-modal',
    # Pedidos: ver y crear
    'pedidos:pedido_list', 'pedidos:pedido_create', 'pedidos:save_pedido', 'pedidos:pedido_detail',
    # Clientes: ver y elegir
    'customers:customer_list', 'customers:customer_detail',
}


class VendedorAccessMiddleware:
    """'Portero' del sistema. Se fija en cada pedido, antes de ejecutar la vista:

    1. Sin iniciar sesion: solo se puede abrir el login (PUBLICAS) y el admin
       (que tiene su propio login). Cualquier otra direccion redirige al login.
       Asi ninguna pantalla queda abierta por olvido, aunque la vista no tenga
       @login_required.
    2. Superusuario (dueños): sin restricciones.
    3. Cualquier otro usuario: solo las vistas de VENDEDOR_ALLOWED; el resto -> 403.
       Esto vale para el grupo 'Vendedor' y tambien para un usuario sin grupo:
       lo que no esta permitido expresamente, esta prohibido.
       (Dentro de esas vistas ademas rigen los permisos del grupo.)

    Para ampliar/reducir lo que puede hacer un Vendedor, editar VENDEDOR_ALLOWED.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        match = request.resolver_match
        if match is None:
            return None
        view_name = match.view_name
        user = getattr(request, 'user', None)

        # 1. Sin sesion
        if user is None or not user.is_authenticated:
            if view_name in PUBLICAS or 'admin' in match.namespaces:
                return None
            return redirect_to_login(request.get_full_path())

        # 2. Superusuario
        if user.is_superuser:
            return None

        # 3. Resto de los usuarios: lista blanca
        if view_name == 'home-page':
            return redirect('pos:pos-page')     # su pantalla de inicio es el POS
        if view_name in VENDEDOR_ALLOWED:
            return None
        return render(request, 'errors/403.html', status=403)
