"""El monto BCV en dólares de los KPIs muestra debajo su equivalente en Bs."""
from datetime import date

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from .models import (Organization, OrganizationAccess, Account, Project,
                     ProjectUserAccess, Transaction)


@pytest.fixture
def escenario(db):
    user = User.objects.create_user(username='u_kpi', password='pw')
    org = Organization.objects.create(name='Org KPI')
    OrganizationAccess.objects.create(user=user, organization=org)
    cuenta = Account.objects.create(
        organization=org, currency=Account.CURRENCY_BS, name='Cuenta Bs')
    proyecto = Project.objects.create(organization=org, name='Proyecto KPI')
    ProjectUserAccess.objects.create(user=user, project=proyecto)
    Transaction.objects.create(
        date=date.today(), organization=org, account=cuenta, description='Ingreso',
        amount_bs=3600, amount_usd=100, daily_rate=36, project=proyecto,
        status='completado')

    c = Client()
    c.login(username='u_kpi', password='pw')
    s = c.session
    s['org_id'] = org.id
    s['org_name'] = org.name
    s.save()
    return c, org, cuenta, proyecto


def _sub_bcv(html):
    """Líneas de conversión que acompañan a un monto BCV en dólares."""
    return [ln.strip() for ln in html.splitlines()
            if 'cf-kpi-row__sub' in ln or 'cf-stat-sub' in ln]


@pytest.mark.parametrize('vista', ['lista_transacciones', 'lista_cuentas'])
@pytest.mark.django_db
def test_kpi_muestra_conversion_a_bolivares(escenario, vista):
    c = escenario[0]
    html = c.get(reverse(vista)).content.decode()
    subs = _sub_bcv(html)
    assert subs, f'{vista} sin línea de conversión'
    # Cada conversión se oculta con la preferencia en Bs., donde el monto
    # principal ya está en bolívares.
    for ln in subs:
        assert 'currency-usd-content' in ln, ln
        assert 'Bs' in ln, ln


@pytest.mark.django_db
def test_kpi_de_proyecto_muestra_conversion(escenario):
    c, _org, _cuenta, proyecto = escenario
    html = c.get(reverse('detalle_proyecto', args=[proyecto.id])).content.decode()
    subs = _sub_bcv(html)
    assert len(subs) == 3, subs          # balance, ingresos y gastos
    assert all('currency-usd-content' in ln for ln in subs)


@pytest.mark.django_db
def test_transacciones_convierte_con_el_importe_real(escenario):
    """3.600 Bs. a tasa 36 = 100 $: ambos deben aparecer juntos."""
    c = escenario[0]
    html = c.get(reverse('lista_transacciones')).content.decode()
    assert '$100,00' in html
    assert 'Bs. 3.600,00' in html


@pytest.mark.django_db
def test_las_columnas_no_bcv_no_llevan_conversion(escenario):
    """Las filas de Dólares y Euros son monedas propias, no equivalentes BCV."""
    c, org, _cuenta, _proyecto = escenario
    Account.objects.create(
        organization=org, currency=Account.CURRENCY_USD, name='Cuenta USD')
    Account.objects.create(
        organization=org, currency=Account.CURRENCY_EUR, name='Cuenta EUR')

    html = c.get(reverse('lista_transacciones')).content.decode()
    # Las tres tarjetas siguen teniendo una sola conversión cada una: la de BCV.
    assert len(_sub_bcv(html)) == 3

    # En el listado de cuentas, la tarjeta de la cuenta en dólares no la lleva.
    html_cuentas = c.get(reverse('lista_cuentas')).content.decode()
    assert len(_sub_bcv(html_cuentas)) == 1   # solo la cuenta en bolívares
