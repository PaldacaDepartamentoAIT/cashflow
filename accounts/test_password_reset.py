"""Recuperación de contraseña iniciada con el nombre de usuario.

Tres desenlaces posibles: enlace enviado, cuenta sin correo registrado
(hay que contactar al administrador) y usuario inexistente.
"""

import re

import pytest
from django.contrib.auth.models import User
from django.urls import reverse


@pytest.fixture
def usuario_con_correo(db):
    return User.objects.create_user(
        username='ana', password='clave-vieja-123', email='ana@ejemplo.com'
    )


@pytest.fixture
def usuario_sin_correo(db):
    return User.objects.create_user(username='beto', password='clave-vieja-123')


def _solicitar(client, username):
    return client.post(reverse('password_reset'), {'username': username})


def _enlace_del_correo(mensaje):
    """Extrae la URL de confirmación del cuerpo en texto plano."""
    encontrado = re.search(r'/accounts/password-reset/[\w\-]+/[\w\-]+/', mensaje.body)
    assert encontrado, f'no se encontró el enlace en el cuerpo:\n{mensaje.body}'
    return encontrado.group(0)


def test_usuario_con_correo_recibe_enlace(client, usuario_con_correo, mailoutbox):
    respuesta = _solicitar(client, 'ana')

    assert respuesta.status_code == 302
    assert respuesta.url == reverse('password_reset_sent')
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ['ana@ejemplo.com']
    assert '\n' not in mailoutbox[0].subject
    _enlace_del_correo(mailoutbox[0])


def test_pantalla_de_envio_muestra_el_correo_enmascarado(client, usuario_con_correo, mailoutbox):
    _solicitar(client, 'ana')
    contenido = client.get(reverse('password_reset_sent')).content.decode()

    assert 'an***@ejemplo.com' in contenido
    assert 'ana@ejemplo.com' not in contenido


def test_usuario_sin_correo_va_a_contactar_al_administrador(client, usuario_sin_correo, mailoutbox):
    respuesta = _solicitar(client, 'beto')

    assert respuesta.status_code == 302
    assert respuesta.url == reverse('password_reset_no_email')
    assert len(mailoutbox) == 0

    contenido = client.get(reverse('password_reset_no_email')).content.decode()
    assert 'Contacta al administrador' in contenido


def test_usuario_inexistente_muestra_error_en_el_formulario(client, db, mailoutbox):
    respuesta = _solicitar(client, 'nadie')

    assert respuesta.status_code == 200
    assert respuesta.context['form'].errors['username']
    assert len(mailoutbox) == 0


def test_usuario_inactivo_se_trata_como_inexistente(client, usuario_con_correo, mailoutbox):
    usuario_con_correo.is_active = False
    usuario_con_correo.save()

    respuesta = _solicitar(client, 'ana')

    assert respuesta.status_code == 200
    assert respuesta.context['form'].errors['username']
    assert len(mailoutbox) == 0


def test_flujo_completo_cambia_la_contrasena(client, usuario_con_correo, mailoutbox):
    _solicitar(client, 'ana')
    enlace = _enlace_del_correo(mailoutbox[0])

    # La vista de Django guarda el token en sesión y redirige a .../set-password/
    respuesta = client.get(enlace)
    assert respuesta.status_code == 302
    formulario = client.get(respuesta.url)
    assert formulario.context['validlink'] is True

    respuesta = client.post(respuesta.url, {
        'new_password1': 'nueva-clave-segura-99',
        'new_password2': 'nueva-clave-segura-99',
    })
    assert respuesta.status_code == 302
    assert respuesta.url == reverse('password_reset_complete')

    usuario_con_correo.refresh_from_db()
    assert usuario_con_correo.check_password('nueva-clave-segura-99')
    assert client.login(username='ana', password='nueva-clave-segura-99')


def test_el_enlace_no_sirve_dos_veces(client, usuario_con_correo, mailoutbox):
    enlace = None
    _solicitar(client, 'ana')
    enlace = _enlace_del_correo(mailoutbox[0])

    destino = client.get(enlace).url
    client.post(destino, {
        'new_password1': 'nueva-clave-segura-99',
        'new_password2': 'nueva-clave-segura-99',
    })

    # Sesión limpia: el token ya fue consumido al cambiar la contraseña.
    client.logout()
    assert client.get(enlace).context['validlink'] is False


def test_token_manipulado_no_es_valido(client, usuario_con_correo, mailoutbox):
    _solicitar(client, 'ana')
    enlace = _enlace_del_correo(mailoutbox[0])
    uidb64, token = enlace.rstrip('/').split('/')[-2:]

    alterado = f'/accounts/password-reset/{uidb64}/{token[:-1]}x/'
    assert client.get(alterado).context['validlink'] is False


def test_throttle_corta_las_solicitudes_repetidas(client, usuario_con_correo, mailoutbox, settings):
    settings.PASSWORD_RESET_MAX_INTENTOS = 2

    _solicitar(client, 'ana')
    _solicitar(client, 'ana')
    respuesta = _solicitar(client, 'ana')

    assert respuesta.status_code == 200
    assert len(mailoutbox) == 2


def test_login_enlaza_a_la_recuperacion(client, db):
    contenido = client.get(reverse('login')).content.decode()
    assert reverse('password_reset') in contenido
