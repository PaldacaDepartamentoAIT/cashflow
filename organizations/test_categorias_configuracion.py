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
def test_portada_configuracion_enlaza_a_la_pantalla_de_categorias():
    """La portada ya no gestiona categorías: solo cuenta y enlaza."""
    c, org = _cliente()
    Category.objects.create(organization=org, name='Nómina', color='#ff8800')
    Category.objects.create(organization=org, name='Viáticos', color='#00ff88')

    r = c.get(reverse('configuracion'))
    html = r.content.decode()
    assert r.status_code == 200
    assert reverse('configuracion_categorias') in html
    assert 'Administrar categorías' in html
    assert '>2<' in html                       # contador de categorías
    assert 'id="catModal"' not in html         # los modales viven en la otra pantalla
    assert 'cat-list__item' not in html


@pytest.mark.django_db
def test_el_enlace_comparte_la_caja_de_las_filas_de_radios():
    """El enlace reutiliza .cf-option, la misma clase que las filas de radios
    de las otras tarjetas, para que su caja sea idéntica por construcción."""
    c, org = _cliente()
    html = c.get(reverse('configuracion')).content.decode()

    enlace = [ln for ln in html.splitlines() if reverse('configuracion_categorias') in ln]
    assert len(enlace) == 1, enlace
    assert 'class="cf-option config-card__action"' in enlace[0]
    # No debe volver a las clases de botón, que traen otro padding y tipografía.
    assert 'cf-btn' not in enlace[0]


@pytest.mark.django_db
def test_pantalla_de_categorias_lista_y_ofrece_selector_de_color():
    c, org = _cliente()
    Category.objects.create(organization=org, name='Nómina', color='#ff8800')
    otra = Organization.objects.create(name='Ajena')
    Category.objects.create(organization=otra, name='NoDebeVerse', color='#123456')

    r = c.get(reverse('configuracion_categorias'))
    html = r.content.decode()
    assert r.status_code == 200
    assert 'Nómina' in html
    assert '#ff8800' in html
    assert 'NoDebeVerse' not in html           # aislamiento por organización
    assert 'type="color"' in html              # selector de color nativo
    assert 'cat-color-presets' in html
    assert 'id="catModal"' in html
    assert reverse('configuracion') in html    # migaja de pan de vuelta


@pytest.mark.django_db
def test_pantalla_de_categorias_exige_organizacion_en_sesion():
    user = User.objects.create_user(username='sin_org', password='pw')
    c = Client()
    c.login(username='sin_org', password='pw')
    r = c.get(reverse('configuracion_categorias'))
    assert r.status_code == 302 and r.url == reverse('dashboard')


@pytest.mark.django_db
def test_crear_editar_y_eliminar_desde_configuracion():
    c, org = _cliente()

    r = c.post(reverse('crear_categoria'), {
        'name': 'Viáticos', 'description': 'Gastos de viaje',
        'color': '#3b82f6', 'next': 'configuracion_categorias',
    })
    assert r.status_code == 302 and r.url == reverse('configuracion_categorias')
    cat = Category.objects.get(organization=org, name='Viáticos')
    assert cat.color == '#3b82f6'

    r = c.post(reverse('editar_categoria', args=[cat.id]), {
        'name': 'Viáticos', 'description': 'Gastos de viaje',
        'color': '#10b981', 'next': 'configuracion_categorias',
    })
    assert r.status_code == 302 and r.url == reverse('configuracion_categorias')
    cat.refresh_from_db()
    assert cat.color == '#10b981'

    r = c.post(reverse('eliminar_categoria', args=[cat.id]), {'next': 'configuracion_categorias'})
    assert r.status_code == 302 and r.url == reverse('configuracion_categorias')
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

    html = c.get(reverse('configuracion_categorias')).content.decode()
    assert 'Solo lectura' in html
    assert 'id="cat-new-btn"' not in html
    assert 'id="catModal"' not in html

    r = c.post(reverse('crear_categoria'), {
        'name': 'Prohibida', 'color': '#000000', 'next': 'configuracion_categorias',
    })
    assert not Category.objects.filter(name='Prohibida').exists()
