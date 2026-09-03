from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
import pytest

from .models import Organization, OrganizationAccess, Category


def _cliente(rol='Editor'):
    user = User.objects.create_user(username='u_cfg', password='pw')
    user.profile.edit = rol
    user.profile.save()
    org = Organization.objects.create(name='Org Cfg')
    OrganizationAccess.objects.create(user=user, organization=org)
    c = Client()
    c.login(username='u_cfg', password='pw')
    s = c.session
    s['org_id'] = org.id
    s['org_name'] = org.name
    s.save()
    return c, org


@pytest.mark.django_db
def test_configuracion_lista_categorias_y_selector_de_color():
    c, org = _cliente()
    Category.objects.create(organization=org, name='Nómina', color='#ff8800')
    otra = Organization.objects.create(name='Ajena')
    Category.objects.create(organization=otra, name='NoDebeVerse', color='#123456')

    r = c.get(reverse('configuracion'))
    html = r.content.decode()
    assert r.status_code == 200
    assert 'Nómina' in html
    assert '#ff8800' in html
    assert 'NoDebeVerse' not in html          # aislamiento por organización
    assert 'type="color"' in html             # selector de color nativo
    assert 'cat-color-presets' in html
    assert 'id="catModal"' in html


@pytest.mark.django_db
def test_crear_editar_y_eliminar_desde_configuracion():
    c, org = _cliente()

    r = c.post(reverse('crear_categoria'), {
        'name': 'Viáticos', 'description': 'Gastos de viaje',
        'color': '#3b82f6', 'next': 'configuracion',
    })
    assert r.status_code == 302 and r.url == reverse('configuracion')
    cat = Category.objects.get(organization=org, name='Viáticos')
    assert cat.color == '#3b82f6'

    r = c.post(reverse('editar_categoria', args=[cat.id]), {
        'name': 'Viáticos', 'description': 'Gastos de viaje',
        'color': '#10b981', 'next': 'configuracion',
    })
    assert r.status_code == 302 and r.url == reverse('configuracion')
    cat.refresh_from_db()
    assert cat.color == '#10b981'

    r = c.post(reverse('eliminar_categoria', args=[cat.id]), {'next': 'configuracion'})
    assert r.status_code == 302 and r.url == reverse('configuracion')
    assert not Category.objects.filter(id=cat.id).exists()


@pytest.mark.django_db
def test_sin_next_sigue_volviendo_al_listado_de_categorias():
    """La pantalla /categorias/ no cambia de comportamiento."""
    c, org = _cliente()
    r = c.post(reverse('crear_categoria'), {'name': 'X', 'color': '#000000'})
    assert r.status_code == 302 and r.url == reverse('lista_categorias')


@pytest.mark.django_db
def test_next_arbitrario_no_redirige_fuera():
    c, org = _cliente()
    r = c.post(reverse('crear_categoria'), {
        'name': 'Y', 'color': '#000000', 'next': 'https://malicioso.example/',
    })
    assert r.status_code == 302 and r.url == reverse('lista_categorias')


@pytest.mark.django_db
def test_viewer_ve_categorias_pero_no_puede_modificarlas():
    c, org = _cliente(rol='Viewer')
    Category.objects.create(organization=org, name='Solo lectura', color='#ff0000')

    html = c.get(reverse('configuracion')).content.decode()
    assert 'Solo lectura' in html
    assert 'id="cat-new-btn"' not in html
    assert 'id="catModal"' not in html

    r = c.post(reverse('crear_categoria'), {
        'name': 'Prohibida', 'color': '#000000', 'next': 'configuracion',
    })
    assert not Category.objects.filter(name='Prohibida').exists()
