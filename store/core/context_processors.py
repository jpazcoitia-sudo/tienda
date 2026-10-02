def is_vendedor(request):
    """Expone `is_vendedor` a los templates: True para todo usuario con sesion
    que NO es superusuario (hoy, el grupo 'Vendedor'). Sirve para mostrarle el
    menu reducido: es el mismo criterio que usa el portero (core/middleware.py)."""
    user = getattr(request, 'user', None)
    es = user is not None and user.is_authenticated and not user.is_superuser
    return {'is_vendedor': es}
