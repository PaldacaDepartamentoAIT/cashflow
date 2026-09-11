from .decorators import organizacion_bloqueada


def estado_cuentas(request):
    """Expone `org_sin_cuentas` para que el sidebar marque las secciones bloqueadas.

    Solo consulta cuando hay organización activa en sesión, y la consulta cara
    (proyectos compartidos) únicamente para organizaciones que no tienen cuentas.
    """
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {}
    org_id = request.session.get('org_id') if hasattr(request, 'session') else None
    if not org_id:
        return {}
    return {'org_sin_cuentas': organizacion_bloqueada(request.user, org_id)}
