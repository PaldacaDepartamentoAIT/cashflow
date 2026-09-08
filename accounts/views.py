import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import LoginView as AuthLoginView
from django.contrib.auth.views import (
    PasswordResetCompleteView,
    PasswordResetConfirmView,
)
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.views.generic import TemplateView

from CashFlow.debug import debug_event

from .forms import LoginForm, NuevaPasswordForm, RegistroForm, SolicitarResetForm

# Contexto comun de las pantallas de autenticacion: base.html usa estas banderas
# para renderizar el layout centrado (auth-container) sin navbar ni sidebar.
AUTH_LAYOUT = {'hide_navbar': True, 'hide_sidebar': True}


class LoginView(AuthLoginView):
    template_name = 'accounts/login.html'
    form_class = LoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        if self.request.user.is_superuser:
            return reverse_lazy('superadmin_dashboard')
        return super().get_success_url()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({'hide_navbar': True, 'hide_sidebar': True})
        return context

    def get_default_redirect_url(self):
        if self.request.user.is_authenticated and self.request.user.is_superuser:
            return reverse_lazy('superadmin_dashboard')
        return super().get_default_redirect_url()


def registro(request):
    if request.method == 'POST':
        form = RegistroForm(request.POST)
        debug_event(
            "usuario.registro.intento",
            username=request.POST.get("username"),
            email=request.POST.get("email"),
        )
        if form.is_valid():
            user = form.save()
            debug_event(
                "usuario.creado",
                user_id=user.id,
                username=user.username,
                email=user.email,
                is_superuser=user.is_superuser,
            )
            login(request, user)
            messages.success(request, "Registro exitoso. ¡Bienvenido!")
            return redirect('dashboard')
        debug_event(
            "usuario.registro.error",
            username=request.POST.get("username"),
            errors=form.errors.get_json_data(),
        )
    else:
        form = RegistroForm()
    
    # Pasamos banderas para ocultar navbar y sidebar
    return render(request, 'accounts/registro.html', {
        'form': form,
        'hide_navbar': True,
        'hide_sidebar': True
    })


# -----------------------------------------------------------------------------
# Restablecimiento de contrasena
# -----------------------------------------------------------------------------
# El flujo arranca con el NOMBRE DE USUARIO (no con el correo, como el de Django)
# y tiene tres desenlaces: enlace enviado, cuenta sin correo registrado, o usuario
# inexistente. Solo el primer paso es propio; el resto reutiliza las vistas y el
# generador de tokens de django.contrib.auth.

_RESET_THROTTLE_KEY = 'password_reset_intentos'
_RESET_EMAIL_KEY = 'password_reset_email'


def _throttle_superado(request):
    """Limita las solicitudes por sesion para no bombardear buzones ni la cuota SMTP.

    Es evitable borrando cookies; solo frena el abuso casual sin obligar a
    configurar CACHES (con varios workers de gunicorn LocMemCache no seria fiable).
    """
    ventana = settings.PASSWORD_RESET_VENTANA_SEGUNDOS
    maximo = settings.PASSWORD_RESET_MAX_INTENTOS
    ahora = time.time()

    intentos = [t for t in request.session.get(_RESET_THROTTLE_KEY, []) if ahora - t < ventana]
    if len(intentos) >= maximo:
        request.session[_RESET_THROTTLE_KEY] = intentos
        return True

    intentos.append(ahora)
    request.session[_RESET_THROTTLE_KEY] = intentos
    return False


def _enmascarar_email(email):
    """'contabilidad@dominio.com' -> 'co***@dominio.com' (para confirmar sin exponer)."""
    nombre, _, dominio = email.partition('@')
    if not dominio:
        return '***'
    visible = nombre[:2] if len(nombre) > 2 else nombre[:1]
    return f'{visible}***@{dominio}'


def _enviar_correo_reset(request, user):
    """Arma el enlace firmado y lo envia. Propaga la excepcion si el SMTP falla."""
    enlace = request.build_absolute_uri(reverse('password_reset_confirm', kwargs={
        'uidb64': urlsafe_base64_encode(force_bytes(user.pk)),
        'token': default_token_generator.make_token(user),
    }))
    contexto = {
        'user': user,
        'enlace': enlace,
        'horas_validez': max(1, settings.PASSWORD_RESET_TIMEOUT // 3600),
    }
    # El asunto no puede tener saltos de linea (Django lanza BadHeaderError).
    asunto = ''.join(render_to_string('accounts/email/password_reset_subject.txt', contexto).splitlines()).strip()
    cuerpo = render_to_string('accounts/email/password_reset_body.txt', contexto)

    send_mail(asunto, cuerpo, None, [user.email], fail_silently=False)


def solicitar_reset(request):
    """Pide el nombre de usuario y decide entre los tres desenlaces posibles."""
    if request.method != 'POST':
        return render(request, 'accounts/password_reset_form.html',
                      {'form': SolicitarResetForm(), **AUTH_LAYOUT})

    form = SolicitarResetForm(request.POST)
    if not form.is_valid():
        return render(request, 'accounts/password_reset_form.html',
                      {'form': form, **AUTH_LAYOUT})

    username = form.cleaned_data['username']
    debug_event("usuario.password_reset.solicitud", username=username)

    if _throttle_superado(request):
        debug_event("usuario.password_reset.throttle", username=username)
        messages.error(
            request,
            "Has hecho demasiadas solicitudes seguidas. Espera un momento antes de volver a intentarlo.",
        )
        return render(request, 'accounts/password_reset_form.html',
                      {'form': form, **AUTH_LAYOUT})

    # Las cuentas inactivas se tratan igual que las inexistentes.
    user = User.objects.filter(username=username, is_active=True).first()

    if user is None:
        debug_event("usuario.password_reset.usuario_inexistente", username=username)
        form.add_error('username', "No existe una cuenta activa con ese nombre de usuario.")
        return render(request, 'accounts/password_reset_form.html',
                      {'form': form, **AUTH_LAYOUT})

    if not user.email:
        debug_event("usuario.password_reset.sin_correo", user_id=user.id, username=user.username)
        return redirect('password_reset_no_email')

    try:
        _enviar_correo_reset(request, user)
    except Exception as exc:  # SMTP caido, credenciales malas, timeout...
        debug_event(
            "usuario.password_reset.error",
            user_id=user.id,
            username=user.username,
            error=str(exc),
        )
        messages.error(
            request,
            "No se pudo enviar el correo en este momento. Intenta de nuevo mas tarde o contacta al administrador.",
        )
        return render(request, 'accounts/password_reset_form.html',
                      {'form': form, **AUTH_LAYOUT})

    debug_event("usuario.password_reset.enviado", user_id=user.id, username=user.username)
    request.session[_RESET_EMAIL_KEY] = _enmascarar_email(user.email)
    return redirect('password_reset_sent')


class PasswordResetSentView(TemplateView):
    """Confirma el envio mostrando el correo enmascarado guardado en sesion."""

    template_name = 'accounts/password_reset_sent.html'
    extra_context = AUTH_LAYOUT

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['email_enmascarado'] = self.request.session.pop(_RESET_EMAIL_KEY, None)
        return context


class PasswordResetNoEmailView(TemplateView):
    """La cuenta existe pero no tiene correo: hay que contactar al administrador."""

    template_name = 'accounts/password_reset_no_email.html'
    extra_context = AUTH_LAYOUT


class ResetConfirmView(PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    form_class = NuevaPasswordForm
    success_url = reverse_lazy('password_reset_complete')
    extra_context = AUTH_LAYOUT

    def form_valid(self, form):
        debug_event(
            "usuario.password_reset.completado",
            user_id=self.user.id,
            username=self.user.username,
        )
        return super().form_valid(form)


class ResetCompleteView(PasswordResetCompleteView):
    template_name = 'accounts/password_reset_complete.html'
    extra_context = AUTH_LAYOUT
