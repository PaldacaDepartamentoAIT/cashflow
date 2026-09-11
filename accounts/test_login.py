"""Aviso de credenciales incorrectas en el login.

El error de AuthenticationForm es un non_field_error: si la plantilla solo
recorre los campos, el usuario reenvía el formulario sin ver ninguna razón.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse


@pytest.fixture
def usuario(db):
    return User.objects.create_user(username='ana', password='clave-correcta-123')


def test_contrasena_incorrecta_muestra_el_aviso(client, usuario):
    r = client.post(reverse('login'), {'username': 'ana', 'password': 'mal'})
    html = r.content.decode()

    assert r.status_code == 200
    assert 'Usuario o contraseña incorrectos' in html
    assert 'auth-form-error' in html
    assert not r.wsgi_request.user.is_authenticated


def test_usuario_inexistente_muestra_el_mismo_aviso(client, db):
    """Mismo texto que con la contraseña mala: no se revela si el usuario existe."""
    r = client.post(reverse('login'), {'username': 'nadie', 'password': 'x'})

    assert r.status_code == 200
    assert 'Usuario o contraseña incorrectos' in r.content.decode()


def test_usuario_inactivo_no_entra(client, usuario):
    usuario.is_active = False
    usuario.save()

    r = client.post(reverse('login'), {'username': 'ana', 'password': 'clave-correcta-123'})

    assert r.status_code == 200
    assert r.context['form'].non_field_errors()
    assert not r.wsgi_request.user.is_authenticated


def test_credenciales_correctas_entran(client, usuario):
    r = client.post(reverse('login'), {'username': 'ana', 'password': 'clave-correcta-123'})

    assert r.status_code == 302
    assert 'Usuario o contraseña incorrectos' not in client.get(reverse('login')).content.decode()


def test_el_login_ofrece_recuperar_la_contrasena(client, usuario):
    """Tras fallar, el enlace de recuperación debe estar a la vista."""
    r = client.post(reverse('login'), {'username': 'ana', 'password': 'mal'})

    assert reverse('password_reset') in r.content.decode()
