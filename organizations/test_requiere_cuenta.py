"""Una organización sin cuentas solo puede entrar a "Mis Cuentas".

Transacciones y proyectos quedan bloqueados hasta que exista al menos una
cuenta (Bs., dólares o euros), y al intentar entrar se avisa de que hay que
abrir una cuenta primero.
"""

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from .decorators import MENSAJE_SIN_CUENTAS
from .models import (
    Account,
    Organization,
    OrganizationAccess,
    Project,
    ProjectOrganizationAccess,
    ProjectUserAccess,
)

# Secciones que no tienen sentido sin cuentas. Se prueban por nombre de URL para
# que el día que cambie una ruta el test siga apuntando a la vista correcta.
VISTAS_BLOQUEADAS = [
    'lista_transacciones',
    'crear_transaccion',
    'exportar_pdf_transacciones',
    'exportar_xlsx_transacciones',
    'lista_proyectos',
    'crear_proyecto',
    'listar_enlaces_compartidos',
]


def _cliente(rol='Editor'):
    user = User.objects.create_user(username='u_cta', password='pw')
    user.profile.edit = rol
    user.profile.save()
    org = Organization.objects.create(name='Org Sin Cuentas')
    OrganizationAccess.objects.create(user=user, organization=org)
    c = Client()
    c.login(username='u_cta', password='pw')
    s = c.session
    s['org_id'] = org.id
    s['org_name'] = org.name
    s.save()
    return c, org


@pytest.mark.parametrize('nombre_url', VISTAS_BLOQUEADAS)
@pytest.mark.django_db
def test_sin_cuentas_las_secciones_redirigen_a_mis_cuentas(nombre_url):
    c, _ = _cliente()

    r = c.get(reverse(nombre_url))

    assert r.status_code == 302
    assert r.url == reverse('lista_cuentas')


@pytest.mark.django_db
def test_el_aviso_explica_que_hay_que_abrir_una_cuenta():
    c, _ = _cliente()

    r = c.get(reverse('lista_transacciones'), follow=True)
    html = r.content.decode()

    assert r.status_code == 200
    assert MENSAJE_SIN_CUENTAS in html
    assert 'Primero debes abrir una cuenta' in html


@pytest.mark.django_db
def test_la_seccion_de_cuentas_sigue_accesible_y_permite_crear():
    c, org = _cliente()

    assert c.get(reverse('lista_cuentas')).status_code == 200

    r = c.post(reverse('crear_cuenta'), {
        'name': 'Cuenta Principal',
        'currency': Account.CURRENCY_BS,
    })

    assert r.status_code == 302
    assert Account.objects.filter(organization=org).count() == 1


@pytest.mark.parametrize('moneda', [Account.CURRENCY_BS, Account.CURRENCY_USD, Account.CURRENCY_EUR])
@pytest.mark.django_db
def test_una_cuenta_de_cualquier_moneda_desbloquea_las_secciones(moneda):
    """Cuenta en Bs., dólares o euros: cualquiera sirve para desbloquear."""
    c, org = _cliente()
    Account.objects.create(organization=org, name='Cuenta', currency=moneda)

    assert c.get(reverse('lista_transacciones')).status_code == 200
    assert c.get(reverse('lista_proyectos')).status_code == 200


@pytest.mark.django_db
def test_las_cuentas_de_otra_organizacion_no_desbloquean():
    c, _ = _cliente()
    otra = Organization.objects.create(name='Otra Org')
    Account.objects.create(organization=otra, name='Ajena', currency=Account.CURRENCY_USD)

    assert c.get(reverse('lista_transacciones')).status_code == 302


@pytest.mark.django_db
def test_el_sidebar_marca_las_secciones_bloqueadas():
    c, org = _cliente()

    html = c.get(reverse('lista_cuentas')).content.decode()
    assert 'is-locked' in html
    assert 'Primero debes abrir una cuenta' in html

    Account.objects.create(organization=org, name='Cuenta', currency=Account.CURRENCY_BS)

    html = c.get(reverse('lista_cuentas')).content.decode()
    assert 'is-locked' not in html


@pytest.mark.django_db
def test_inicio_y_configuracion_siguen_accesibles_sin_cuentas():
    """Solo se bloquean transacciones y proyectos; el resto se puede navegar."""
    c, _ = _cliente()

    assert c.get(reverse('home_organizacion')).status_code == 200
    assert c.get(reverse('configuracion')).status_code == 200


@pytest.mark.django_db
def test_un_proyecto_compartido_desbloquea_aunque_no_haya_cuentas():
    """Excepción real: una organización sin cuentas propias puede recibir un
    proyecto compartido por otra, cuyas transacciones viven en las cuentas de
    esa otra. Bloquearla rompería un flujo que ya existe."""
    c, org = _cliente()
    user = User.objects.get(username='u_cta')
    otra = Organization.objects.create(name='Org Dueña')
    Account.objects.create(organization=otra, name='Cuenta', currency=Account.CURRENCY_BS)
    proyecto = Project.objects.create(name='Compartido', organization=otra)
    ProjectOrganizationAccess.objects.create(project=proyecto, organization=org)
    ProjectUserAccess.objects.create(user=user, project=proyecto)

    assert c.get(reverse('lista_proyectos')).status_code == 200
    assert c.get(reverse('lista_transacciones')).status_code == 200
    assert 'is-locked' not in c.get(reverse('lista_cuentas')).content.decode()


@pytest.mark.django_db
def test_un_proyecto_compartido_sin_acceso_del_usuario_no_desbloquea():
    """El proyecto tiene que ser alcanzable por ESTE usuario, no solo por la organización."""
    c, org = _cliente()
    otra = Organization.objects.create(name='Org Dueña')
    proyecto = Project.objects.create(name='Compartido', organization=otra)
    ProjectOrganizationAccess.objects.create(project=proyecto, organization=org)
    # Sin ProjectUserAccess para u_cta.

    assert c.get(reverse('lista_proyectos')).status_code == 302
