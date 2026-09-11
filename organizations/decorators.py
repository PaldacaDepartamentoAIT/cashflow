from functools import wraps

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import redirect

from CashFlow.debug import debug_event

from .models import Account, Project

# Una organización recién creada no puede registrar nada: las transacciones se
# cargan contra una cuenta y los proyectos se alimentan de transacciones. En vez
# de dejar entrar a secciones vacías donde no se puede hacer nada, se redirige a
# "Mis Cuentas" con el aviso.
MENSAJE_SIN_CUENTAS = (
    "Primero debes abrir una cuenta. Crea una cuenta en Bolívares, Dólares o Euros "
    "y podrás empezar a registrar transacciones y proyectos."
)


def organizacion_bloqueada(user, org_id):
    """True si desde esta organización no hay nada que el usuario pueda operar.

    La condición base es no tener ninguna cuenta (de cualquier moneda), pero hay
    una excepción real: una organización sin cuentas propias sí puede tener
    proyectos compartidos por otra organización, y sus transacciones viven en las
    cuentas de esa otra. Bloquearla dejaría fuera un flujo que ya existe.
    """
    if not org_id:
        return False
    if Account.objects.filter(organization_id=org_id).exists():
        return False
    # Solo se llega aquí con organizaciones sin cuentas, que son la minoría.
    return not Project.objects.filter(
        Q(organization_id=org_id) | Q(shared_organizations__organization_id=org_id),
        user_accesses__user=user,
    ).exists()


def requiere_cuenta(view_func):
    """Bloquea transacciones y proyectos mientras no haya con qué trabajar.

    Va después de @login_required. Si no hay organización activa no hace nada:
    de eso ya se encarga la propia vista redirigiendo al dashboard.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        org_id = request.session.get('org_id')
        if organizacion_bloqueada(request.user, org_id):
            debug_event(
                "organizacion.sin_cuentas.acceso_bloqueado",
                org_id=org_id,
                user_id=request.user.id,
                vista=view_func.__name__,
            )
            messages.warning(request, MENSAJE_SIN_CUENTAS)
            return redirect('lista_cuentas')
        return view_func(request, *args, **kwargs)
    return _wrapped_view
