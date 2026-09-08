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


@pytest.mark.django_db
def test_el_monto_en_bs_es_la_suma_de_la_columna_no_una_reconversion(escenario):
    """El importe en bolívares del KPI BCV suma la columna `amount_bs`, que se
    grabó con la tasa del día de cada transacción. NO reconvierte el total en
    dólares a la tasa de hoy: si lo hiciera, dos movimientos registrados a
    tasas distintas darían un número muy distinto al de la suma."""
    c, org, cuenta, proyecto = escenario
    Transaction.objects.all().delete()

    # 100 $ a tasa 10 y 100 $ a tasa 60: 200 $ en total, pero 7.000 Bs.
    Transaction.objects.create(
        date=date(2026, 1, 10), organization=org, account=cuenta, description='t1',
        amount_bs=1000, amount_usd=100, daily_rate=10, project=proyecto,
        status='completado')
    Transaction.objects.create(
        date=date(2026, 6, 10), organization=org, account=cuenta, description='t2',
        amount_bs=6000, amount_usd=100, daily_rate=60, project=proyecto,
        status='completado')

    html = c.get(reverse('lista_transacciones')).content.decode()
    assert '$200,00' in html          # suma de la columna en dólares
    assert 'Bs. 7.000,00' in html     # suma de la columna en bolívares (1.000 + 6.000)

    # Una reconversión de los 200 $ a una única tasa daría cualquier otra cifra.
    tasa_implicita = 7000 / 200
    assert tasa_implicita == 35, 'la cifra en Bs. no es la suma de la columna'
