def is_vendedor(request):
    """Expone `is_vendedor` a los templates: True si el usuario pertenece
    al grupo 'Vendedor' (y no es superusuario). Sirve para ocultar el menú."""
    user = getattr(request, 'user', None)
    es = False
    if user is not None and user.is_authenticated and not user.is_superuser:
        es = user.groups.filter(name='Vendedor').exists()
    return {'is_vendedor': es}
