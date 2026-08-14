from django.shortcuts import redirect


class SuperuserPanelMiddleware:
    """Los superusuarios operan solo en el panel superadmin, no en el flujo de organizaciones."""

    ALLOWED_PATH_PREFIXES = (
        '/superadmin/',
        '/accounts/logout/',
        '/admin/',
        '/health/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user and user.is_authenticated and user.is_superuser:
            path = request.path
            if path.startswith('/static/') or path.startswith('/media/'):
                return self.get_response(request)
            if not any(path.startswith(prefix) for prefix in self.ALLOWED_PATH_PREFIXES):
                return redirect('superadmin_dashboard')
        return self.get_response(request)
