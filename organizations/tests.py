from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse

from .amounts import opening_balance_transaction_amounts
from .models import Organization, OrganizationAccess, Project, Transaction, Account, Category, ProjectOrganizationAccess, ProjectUserAccess, CostCenter

class TransactionAccessTest(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(username='user_a', password='password')
        self.org_a = Organization.objects.create(name='Org A')
        OrganizationAccess.objects.create(user=self.user_a, organization=self.org_a)
        
        self.org_b = Organization.objects.create(name='Org B')
        
        self.project_p = Project.objects.create(name='Project P', organization=self.org_b)
        
        # Share project P with Org A
        ProjectOrganizationAccess.objects.create(project=self.project_p, organization=self.org_a)
        # Give User A access to project P
        ProjectUserAccess.objects.create(user=self.user_a, project=self.project_p)
        
        self.account_b = Account.objects.create(
            organization=self.org_b,
            currency=Account.CURRENCY_BS,
            name='Account B',
        )
        self.category_b = Category.objects.create(organization=self.org_b, name='Category B')
        
        self.transaction = Transaction.objects.create(
            date=date.today(),
            organization=self.org_b,
            account=self.account_b,
            description='Test Trans',
            amount_bs=100,
            amount_usd=10,
            daily_rate=10,
            project=self.project_p,
            status='completado'
        )
        self.transaction.categories.add(self.category_b)
        
        self.client = Client()
        self.client.login(username='user_a', password='password')
        
        # Set org_id in session
        session = self.client.session
        session['org_id'] = self.org_a.id
        session.save()

    def test_valuation_visibility_in_project_detail(self):
        """
        Verify that valuations are rendered in the project detail view.
        """
        from .models import Valuation
        valuation = Valuation.objects.create(
            project=self.project_p,
            name="Valuacion de Prueba",
            amount_usd=1000,
            amount_bs=36000,
            daily_rate=36
        )
        
        url = reverse('detalle_proyecto', kwargs={'proj_id': self.project_p.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Valuacion de Prueba")

    def test_valuation_visibility_for_viewer(self):
        """
        Verify that valuations are rendered in the project detail view for viewers.
        """
        from .models import Valuation
        # Change user role to Viewer in their Profile
        profile = self.user_a.profile
        profile.edit = 'Viewer'
        profile.save()
        
        valuation = Valuation.objects.create(
            project=self.project_p,
            name="Valuacion Viewer",
            amount_usd=500,
            amount_bs=18000,
            daily_rate=36
        )
        
        url = reverse('detalle_proyecto', kwargs={'proj_id': self.project_p.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Valuacion Viewer")
        # Ensure buttons are hidden for viewers
        self.assertNotContains(response, "Añadir Valuación")
        self.assertNotContains(response, "Nueva Transacción")
        # But toggle should be visible
        self.assertContains(response, "Gestionar Valuaciones")

    def test_viewer_restricted_with_whitespace(self):
        """
        Verify that viewer_restricted blocks users even if there's trailing whitespace in the role field.
        """
        profile = self.user_a.profile
        profile.edit = 'Viewer ' # Trailing space
        profile.save()
        
        self.client.login(username='user_a', password='password')
        
        # Try to create a category (restricted action)
        url = reverse('crear_categoria')
        data = {'name': 'Restricted Category', 'color': '#ff0000'}
        response = self.client.post(url, data)
        
        # Should be redirected (to dashboard by default if no referer)
        self.assertEqual(response.status_code, 302)
        
        # Check for error message
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("Su cuenta es de solo lectura" in str(m) for m in messages))

    def test_edit_shared_project_transaction_success(self):
        """
        Verify that editing a transaction from another organization
        works if it belongs to a shared project the user has access to.
        """
        url = reverse('editar_transaccion', kwargs={'trans_id': self.transaction.id})
        data = {
            'date': self.transaction.date,
            'organization': self.org_b.id,
            'account': self.account_b.id,
            'description': 'Updated Trans',
            'amount_bs': 200, # Revenue (positive)
            'amount_usd': 20,
            'daily_rate': 10,
            'project': self.project_p.id,
            'categories': [self.category_b.id],
            'status': 'completado',
            'bank_fee_bs': 0,
            'bank_fee_usd': 0,
            'bank_fee_real_usd': 0,
        }
        response = self.client.post(url, data, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Verify transaction was updated
        self.transaction.refresh_from_db()
        self.assertEqual(float(self.transaction.amount_bs), 200.0)
        self.assertEqual(self.transaction.description, 'Updated Trans')

    def test_detail_shared_project_transaction_success(self):
        """
        Verify that viewing details of a transaction from another organization
        works if it belongs to a shared project the user has access to.
        """
        url = reverse('detalle_transaccion', kwargs={'trans_id': self.transaction.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.transaction.description)

    def test_delete_shared_project_transaction_success(self):
        """
        Verify that deleting a transaction from another organization
        works if it belongs to a shared project the user has access to.
        """
        url = reverse('eliminar_transaccion', kwargs={'trans_id': self.transaction.id})
        # Use POST for delete
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.filter(id=self.transaction.id).exists())


def test_saldo_inicial_cuenta_bs_calcula_usd():
    amount_bs, amount_usd = opening_balance_transaction_amounts(
        Decimal('36500'), Account.CURRENCY_BS, Decimal('36.5')
    )
    assert amount_bs == Decimal('36500')
    assert amount_usd == Decimal('1000.00')


def test_saldo_inicial_cuenta_usd_calcula_bs():
    amount_bs, amount_usd = opening_balance_transaction_amounts(
        Decimal('100'), Account.CURRENCY_USD, Decimal('36.5')
    )
    assert amount_usd == Decimal('100')
    assert amount_bs == Decimal('3650.00')


@pytest.mark.django_db
def test_crear_cuenta_bs_registra_equivalente_usd(client):
    user = User.objects.create_user(username='cuenta_bs', password='password')
    org = Organization.objects.create(name='Org BS')
    OrganizationAccess.objects.create(user=user, organization=org)

    client.force_login(user)
    session = client.session
    session['org_id'] = org.id
    session.save()

    response = client.post(reverse('crear_cuenta'), {
        'currency': Account.CURRENCY_BS,
        'name': 'Cuenta de Prueba BS',
        'initial_balance': '36500.00',
        'daily_rate': '36.5000',
    }, follow=True)

    assert response.status_code == 200
    tx = Transaction.objects.get(organization=org)
    assert float(tx.amount_bs) == 36500.0
    assert float(tx.amount_usd) == 1000.0
    assert float(tx.daily_rate) == 36.5


@pytest.mark.django_db
def test_get_report_data_aplica_filtros(client):
    from django.test import RequestFactory
    from organizations.views import _get_report_data
    from organizations.models import Category, Transaction, Account, CostCenter
    from datetime import date
    
    user = User.objects.create_user(username='report_user', password='password')
    org = Organization.objects.create(name='Org Report')
    OrganizationAccess.objects.create(user=user, organization=org)
    
    acc = Account.objects.create(
        organization=org,
        currency=Account.CURRENCY_BS,
        name='Cuenta Test',
    )
    
    cat1 = Category.objects.create(organization=org, name='Cat A', color='#111111')
    cat2 = Category.objects.create(organization=org, name='Cat B', color='#222222')

    cc1 = CostCenter.objects.create(organization=org, code='CC01', name='Cost Center One')
    cc2 = CostCenter.objects.create(organization=org, code='CC02', name='Cost Center Two')
    
    t1 = Transaction.objects.create(
        organization=org,
        account=acc,
        date=date(2026, 6, 1),
        description='Gastos de Oficina A',
        amount_usd=100.00,
        amount_bs=3600.00,
        daily_rate=36.00,
        cost_center=cc1,
    )
    t1.categories.add(cat1)
    t2 = Transaction.objects.create(
        organization=org,
        account=acc,
        date=date(2026, 6, 15),
        description='Gastos de Oficina B',
        amount_usd=200.00,
        amount_bs=7200.00,
        daily_rate=36.00,
        cost_center=cc2,
    )
    t2.categories.add(cat2)
    
    factory = RequestFactory()
    
    # 1. Sin filtros
    request = factory.get('/transacciones/exportar-pdf/', {'report_type': 'bcv'})
    request.user = user
    request.session = {'org_id': org.id}
    _, transactions, _, _, _ = _get_report_data(request)
    assert transactions.count() == 2
    
    # 2. Filtrar por categoría Cat A
    request = factory.get('/transacciones/exportar-pdf/', {'report_type': 'bcv', 'category': cat1.id})
    request.user = user
    request.session = {'org_id': org.id}
    _, transactions, _, _, label = _get_report_data(request)
    assert transactions.count() == 1
    assert transactions[0].id == t1.id
    assert "Cat A" in label

    # 3. Filtrar por búsqueda
    request = factory.get('/transacciones/exportar-pdf/', {'report_type': 'bcv', 'search': 'Oficina B'})
    request.user = user
    request.session = {'org_id': org.id}
    _, transactions, _, _, _ = _get_report_data(request)
    assert transactions.count() == 1
    assert transactions[0].id == t2.id

    # 4. Filtrar por rango de fechas
    request = factory.get('/transacciones/exportar-pdf/', {
        'report_type': 'bcv',
        'date_from': '2026-06-01',
        'date_to': '2026-06-10'
    })
    request.user = user
    request.session = {'org_id': org.id}
    _, transactions, _, _, _ = _get_report_data(request)
    assert transactions.count() == 1
    assert transactions[0].id == t1.id

    # 5. Filtrar por centro de costo
    request = factory.get('/transacciones/exportar-pdf/', {
        'report_type': 'bcv',
        'cost_center': cc1.id
    })
    request.user = user
    request.session = {'org_id': org.id}
    _, transactions, _, _, label = _get_report_data(request)
    assert transactions.count() == 1
    assert transactions[0].id == t1.id
    assert "Centro de Costo: CC01 - Cost Center One" in label

    # 6. Filtrar por búsqueda de código de centro de costo
    request = factory.get('/transacciones/exportar-pdf/', {
        'report_type': 'bcv',
        'search': 'CC02'
    })
    request.user = user
    request.session = {'org_id': org.id}
    _, transactions, _, _, _ = _get_report_data(request)
    assert transactions.count() == 1
    assert transactions[0].id == t2.id


@pytest.mark.django_db
def test_transaction_form_cost_center():
    from organizations.forms import TransactionForm
    from organizations.models import CostCenter, Organization
    org = Organization.objects.create(name='Org Form Test')
    org2 = Organization.objects.create(name='Other Org')
    cc = CostCenter.objects.create(organization=org, code='CC01', name='CC 01')
    cc_other = CostCenter.objects.create(organization=org2, code='CC02', name='CC 02')
    
    # Check form queryset filtering
    form = TransactionForm(organization=org)
    assert cc in form.fields['cost_center'].queryset
    assert cc_other not in form.fields['cost_center'].queryset




# --- Cuentas y transacciones en euros ---


def _eur_account(org, name='Cuenta EUR'):
    return Account.objects.create(
        organization=org,
        currency=Account.CURRENCY_EUR,
        name=name,
    )


@pytest.mark.django_db
def test_saldo_inicial_cuenta_eur_solo_mueve_euros():
    """El saldo inicial de una cuenta en euros va a amount_eur, sin tocar el
    resto de las columnas ni convertir por la tasa BCV."""
    from organizations.amounts import create_initial_balance_transaction

    org = Organization.objects.create(name='Org EUR')
    account = _eur_account(org)

    tx = create_initial_balance_transaction(
        organization=org, account=account, balance=Decimal('250.00'), daily_rate=Decimal('40'),
    )

    assert tx.amount_eur == Decimal('250.00')
    assert tx.amount_bs == 0
    assert tx.amount_usd == 0
    assert tx.real_dollars == 0


@pytest.mark.django_db
def test_transaction_form_rechaza_bolivares_en_cuenta_eur():
    from organizations.forms import TransactionForm

    org = Organization.objects.create(name='Org EUR Form')
    account = _eur_account(org)

    form = TransactionForm(data={
        'date': date.today(), 'organization': org.id, 'account': account.id,
        'description': 'Gasto', 'status': 'completado',
        'amount_bs': 100, 'amount_usd': 0, 'daily_rate': 40,
        'bank_fee_bs': 0, 'bank_fee_usd': 0, 'bank_fee_real_usd': 0,
        'amount_eur': 0, 'bank_fee_eur': 0,
    }, organization=org)

    assert not form.is_valid()
    assert 'euros' in ' '.join(form.errors['__all__']).lower()


@pytest.mark.django_db
def test_transaction_form_rechaza_euros_en_cuenta_bs():
    from organizations.forms import TransactionForm

    org = Organization.objects.create(name='Org BS Form')
    account = Account.objects.create(
        organization=org, currency=Account.CURRENCY_BS, name='Cuenta Bs',
    )

    form = TransactionForm(data={
        'date': date.today(), 'organization': org.id, 'account': account.id,
        'description': 'Gasto', 'status': 'completado',
        'amount_bs': 100, 'amount_usd': 0, 'daily_rate': 40,
        'bank_fee_bs': 0, 'bank_fee_usd': 0, 'bank_fee_real_usd': 0,
        'amount_eur': 50, 'bank_fee_eur': 0,
    }, organization=org)

    assert not form.is_valid()
    assert "'Euros'" in ' '.join(form.errors['__all__'])


@pytest.mark.django_db
def test_transaction_form_acepta_euros_en_cuenta_eur():
    from organizations.forms import TransactionForm

    org = Organization.objects.create(name='Org EUR OK')
    account = _eur_account(org)

    form = TransactionForm(data={
        'date': date.today(), 'organization': org.id, 'account': account.id,
        'description': 'Gasto en euros', 'status': 'completado',
        'amount_bs': 0, 'amount_usd': 0, 'daily_rate': 40,
        'bank_fee_bs': 0, 'bank_fee_usd': 0, 'bank_fee_real_usd': 0,
        'amount_eur': -75, 'bank_fee_eur': 2,
    }, organization=org)

    assert form.is_valid(), form.errors
    tx = form.save()
    assert tx.amount_eur == Decimal('-75')
    assert tx.bank_fee_eur == Decimal('2')
    # Las demás pistas de moneda quedan en cero
    assert tx.amount_bs == 0 and tx.amount_usd == 0 and tx.real_dollars == 0


@pytest.mark.django_db
def test_balances_por_moneda_en_organizacion_mixta():
    """Los saldos de cada moneda se agregan por separado, sin mezclarse."""
    from organizations.views import balance_aggregates, currency_totals, organization_currencies

    org = Organization.objects.create(name='Org Mixta')
    acc_bs = Account.objects.create(
        organization=org, currency=Account.CURRENCY_BS, name='Bs',
    )
    acc_usd = Account.objects.create(
        organization=org, currency=Account.CURRENCY_USD, name='Usd',
    )
    acc_eur = _eur_account(org, name='Eur')

    common = dict(organization=org, date=date.today(), daily_rate=40, status='completado')
    Transaction.objects.create(account=acc_bs, description='bs', amount_bs=400, amount_usd=10, **common)
    Transaction.objects.create(account=acc_usd, description='usd', amount_bs=0, amount_usd=0, real_dollars=30, **common)
    Transaction.objects.create(account=acc_eur, description='eur', amount_bs=0, amount_usd=0, amount_eur=20, **common)
    Transaction.objects.create(account=acc_eur, description='eur gasto', amount_bs=0, amount_usd=0, amount_eur=-5, **common)

    qs = Transaction.objects.filter(organization=org)
    balances = qs.aggregate(**balance_aggregates())
    assert balances['balance_bs'] == 400
    assert balances['balance_usd'] == 10
    assert balances['balance_real_usd'] == 30
    assert balances['balance_eur'] == 15

    totals = currency_totals(qs)
    assert totals['income_eur'] == 20
    assert totals['expense_eur'] == 5

    assert organization_currencies(org.id) == {'BS', 'USD', 'EUR'}


# --- Higiene de plantillas ---


def test_no_hay_comentarios_django_multilinea():
    """Django solo reconoce {# ... #} dentro de una misma línea.

    Si un comentario abarca varias líneas, el lexer no lo detecta y el texto se
    renderiza tal cual en la página. Este test evita que vuelva a colarse.
    """
    import glob
    from pathlib import Path

    base = Path(__file__).resolve().parent.parent / 'templates'
    ofensores = []
    for ruta in glob.glob(str(base / '**' / '*.html'), recursive=True):
        for numero, linea in enumerate(Path(ruta).read_text(encoding='utf-8').splitlines(), 1):
            if '{#' in linea and '#}' not in linea:
                ofensores.append(f'{Path(ruta).relative_to(base)}:{numero}')

    assert not ofensores, (
        'Comentarios {# #} multilínea: Django los renderiza como texto visible. '
        'Deben caber en una sola línea. Encontrados en: ' + ', '.join(ofensores)
    )


# --- Fotos adjuntas de transacciones ---


def _imagen_subida(nombre='foto.jpg', size=(60, 40), fmt='JPEG', color='red'):
    """Archivo de imagen válido en memoria, listo para subir."""
    import io

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    buf = io.BytesIO()
    Image.new('RGB', size, color).save(buf, fmt)
    tipos = {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'WEBP': 'image/webp'}
    return SimpleUploadedFile(nombre, buf.getvalue(), content_type=tipos[fmt])


def _org_con_cuenta(client, sufijo, media_root):
    """Usuario editor con organización activa y una cuenta en Bs."""
    user = User.objects.create_user(username=f'fotos_{sufijo}', password='password')
    org = Organization.objects.create(name=f'Org Fotos {sufijo}')
    OrganizationAccess.objects.create(user=user, organization=org)
    cuenta = Account.objects.create(
        organization=org, currency=Account.CURRENCY_BS, name='Cuenta Fotos'
    )
    client.force_login(user)
    session = client.session
    session['org_id'] = org.id
    session.save()
    return user, org, cuenta


def _datos_transaccion(org, cuenta, **extra):
    datos = {
        'date': '2026-01-15',
        'organization': org.id,
        'account': cuenta.id,
        'description': 'Compra con comprobante',
        'status': 'completado',
        'amount_bs': '100.00',
        'amount_usd': '0',
        'daily_rate': '36.5000',
        'bank_fee_bs': '0',
        'bank_fee_usd': '0',
        'bank_fee_real_usd': '0',
    }
    datos.update(extra)
    return datos


def _crear_transaccion_con_fotos(client, org, cuenta, n_fotos):
    from .models import TransactionPhoto

    client.post(
        reverse('crear_transaccion'),
        _datos_transaccion(
            org, cuenta,
            photos=[_imagen_subida(f'f{i}.jpg') for i in range(n_fotos)],
        ),
        follow=True,
    )
    tx = Transaction.objects.get(organization=org)
    assert tx.photos.count() == n_fotos, TransactionPhoto.objects.count()
    return tx


@pytest.mark.django_db
def test_subir_fotos_crea_registros_y_archivos(client, tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)
    _, org, cuenta = _org_con_cuenta(client, 'crear', tmp_path)

    tx = _crear_transaccion_con_fotos(client, org, cuenta, 2)

    import os
    for foto in tx.photos.all():
        assert foto.size_bytes > 0
        assert foto.width > 0 and foto.height > 0
        assert os.path.exists(os.path.join(str(tmp_path), foto.image.name))


@pytest.mark.django_db
def test_toda_foto_guardada_pesa_menos_del_objetivo(client, tmp_path, settings):
    """El requisito central: nada superior al objetivo llega al almacenamiento."""
    import random

    from PIL import Image

    settings.MEDIA_ROOT = str(tmp_path)
    _, org, cuenta = _org_con_cuenta(client, 'peso', tmp_path)

    # Ruido puro a alta resolución: el peor caso posible para JPEG.
    rnd = random.Random(0)
    grande = Image.new('RGB', (1800, 1400))
    grande.putdata([
        (rnd.randrange(256), rnd.randrange(256), rnd.randrange(256))
        for _ in range(1800 * 1400)
    ])
    import io

    from django.core.files.uploadedfile import SimpleUploadedFile
    buf = io.BytesIO()
    grande.save(buf, 'JPEG', quality=95)
    pesada = SimpleUploadedFile('pesada.jpg', buf.getvalue(), content_type='image/jpeg')
    assert pesada.size > settings.TRANSACTION_PHOTO_TARGET_BYTES

    client.post(
        reverse('crear_transaccion'),
        _datos_transaccion(org, cuenta, photos=[pesada]),
        follow=True,
    )

    foto = Transaction.objects.get(organization=org).photos.get()
    assert foto.size_bytes <= settings.TRANSACTION_PHOTO_TARGET_BYTES
    assert foto.image.size <= settings.TRANSACTION_PHOTO_TARGET_BYTES


@pytest.mark.django_db
def test_rechaza_la_foto_que_supera_el_tope(client, tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)
    settings.TRANSACTION_PHOTOS_MAX = 3
    _, org, cuenta = _org_con_cuenta(client, 'tope', tmp_path)

    tx = _crear_transaccion_con_fotos(client, org, cuenta, 3)

    response = client.post(
        reverse('editar_transaccion', args=[tx.id]),
        _datos_transaccion(org, cuenta, description='Editada', photos=[_imagen_subida('extra.jpg')]),
        follow=True,
    )
    assert response.status_code == 200
    tx.refresh_from_db()
    assert tx.photos.count() == 3
    # La transacción tampoco debe haberse modificado.
    assert tx.description == 'Compra con comprobante'


@pytest.mark.django_db
def test_el_tope_considera_las_eliminaciones(client, tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)
    settings.TRANSACTION_PHOTOS_MAX = 3
    _, org, cuenta = _org_con_cuenta(client, 'canje', tmp_path)

    tx = _crear_transaccion_con_fotos(client, org, cuenta, 3)
    a_borrar = list(tx.photos.values_list('id', flat=True))[:2]

    client.post(
        reverse('editar_transaccion', args=[tx.id]),
        _datos_transaccion(
            org, cuenta,
            delete_photo_ids=a_borrar,
            photos=[_imagen_subida('n1.jpg'), _imagen_subida('n2.jpg')],
        ),
        follow=True,
    )

    tx.refresh_from_db()
    assert tx.photos.count() == 3
    assert not tx.photos.filter(id__in=a_borrar).exists()


@pytest.mark.django_db
def test_rechaza_archivo_que_no_es_imagen(client, tmp_path, settings):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from .models import TransactionPhoto

    settings.MEDIA_ROOT = str(tmp_path)
    _, org, cuenta = _org_con_cuenta(client, 'noimg', tmp_path)

    falsa = SimpleUploadedFile('virus.jpg', b'esto no es una imagen', content_type='image/jpeg')
    response = client.post(
        reverse('crear_transaccion'),
        _datos_transaccion(org, cuenta, photos=[falsa]),
        follow=True,
    )

    assert response.status_code == 200
    # Atomicidad: ni la transacción ni las fotos deben existir.
    assert not Transaction.objects.filter(organization=org).exists()
    assert TransactionPhoto.objects.count() == 0


@pytest.mark.django_db
def test_rechaza_archivo_demasiado_grande(client, tmp_path, settings):
    from .models import TransactionPhoto

    settings.MEDIA_ROOT = str(tmp_path)
    settings.TRANSACTION_PHOTO_MAX_UPLOAD_BYTES = 100  # 100 bytes
    _, org, cuenta = _org_con_cuenta(client, 'grande', tmp_path)

    client.post(
        reverse('crear_transaccion'),
        _datos_transaccion(org, cuenta, photos=[_imagen_subida('g.jpg', size=(400, 400))]),
        follow=True,
    )

    assert not Transaction.objects.filter(organization=org).exists()
    assert TransactionPhoto.objects.count() == 0


@pytest.mark.django_db
def test_eliminar_foto_borra_el_archivo_del_disco(client, tmp_path, settings, django_capture_on_commit_callbacks):
    import os

    settings.MEDIA_ROOT = str(tmp_path)
    _, org, cuenta = _org_con_cuenta(client, 'borrar', tmp_path)

    tx = _crear_transaccion_con_fotos(client, org, cuenta, 1)
    foto = tx.photos.get()
    ruta = os.path.join(str(tmp_path), foto.image.name)
    assert os.path.exists(ruta)

    # on_commit no corre dentro de la transacción envolvente del test.
    with django_capture_on_commit_callbacks(execute=True):
        client.post(reverse('eliminar_foto_transaccion', args=[foto.id]))

    assert not tx.photos.exists()
    assert not os.path.exists(ruta)


@pytest.mark.django_db
def test_eliminar_transaccion_borra_fotos_y_archivos(client, tmp_path, settings, django_capture_on_commit_callbacks):
    import os

    from .models import TransactionPhoto

    settings.MEDIA_ROOT = str(tmp_path)
    _, org, cuenta = _org_con_cuenta(client, 'cascada', tmp_path)

    tx = _crear_transaccion_con_fotos(client, org, cuenta, 2)
    rutas = [os.path.join(str(tmp_path), f.image.name) for f in tx.photos.all()]

    with django_capture_on_commit_callbacks(execute=True):
        client.post(reverse('eliminar_transaccion', args=[tx.id]), follow=True)

    assert not Transaction.objects.filter(id=tx.id).exists()
    assert TransactionPhoto.objects.count() == 0
    for ruta in rutas:
        assert not os.path.exists(ruta)


@pytest.mark.django_db
def test_no_se_pueden_eliminar_fotos_de_otra_transaccion(client, tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)
    _, org, cuenta = _org_con_cuenta(client, 'ajena', tmp_path)

    tx_a = _crear_transaccion_con_fotos(client, org, cuenta, 1)
    foto_ajena = tx_a.photos.get()

    tx_b = Transaction.objects.create(
        date=date(2026, 1, 20), organization=org, account=cuenta,
        description='Otra', amount_bs=Decimal('50'), amount_usd=Decimal('0'),
        daily_rate=Decimal('36.5'),
    )

    client.post(
        reverse('editar_transaccion', args=[tx_b.id]),
        _datos_transaccion(org, cuenta, description='Otra', delete_photo_ids=[foto_ajena.id]),
        follow=True,
    )

    # La foto ajena sigue intacta.
    tx_a.refresh_from_db()
    assert tx_a.photos.filter(id=foto_ajena.id).exists()


@pytest.mark.django_db
def test_ver_foto_respeta_el_alcance_de_organizacion(client, tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)
    _, org_a, cuenta_a = _org_con_cuenta(client, 'orga', tmp_path)
    tx = _crear_transaccion_con_fotos(client, org_a, cuenta_a, 1)
    foto = tx.photos.get()

    # El dueño la ve.
    assert client.get(reverse('ver_foto_transaccion', args=[foto.id])).status_code == 200

    # Un usuario de otra organización recibe 404, no 403.
    intruso = User.objects.create_user(username='intruso', password='password')
    org_b = Organization.objects.create(name='Org Intrusa')
    OrganizationAccess.objects.create(user=intruso, organization=org_b)
    otro = Client()
    otro.force_login(intruso)
    sesion = otro.session
    sesion['org_id'] = org_b.id
    sesion.save()

    assert otro.get(reverse('ver_foto_transaccion', args=[foto.id])).status_code == 404


@pytest.mark.django_db
def test_ver_foto_sin_login_redirige(client, tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)
    _, org, cuenta = _org_con_cuenta(client, 'anon', tmp_path)
    tx = _crear_transaccion_con_fotos(client, org, cuenta, 1)
    foto = tx.photos.get()

    anonimo = Client()
    response = anonimo.get(reverse('ver_foto_transaccion', args=[foto.id]))
    assert response.status_code == 302
    assert '/login' in response.url or 'login' in response.url


@pytest.mark.django_db
def test_viewer_no_puede_subir_fotos(client, tmp_path, settings):
    from .models import TransactionPhoto

    settings.MEDIA_ROOT = str(tmp_path)
    user, org, cuenta = _org_con_cuenta(client, 'viewer', tmp_path)
    user.profile.edit = 'viewer'
    user.profile.save()

    client.post(
        reverse('crear_transaccion'),
        _datos_transaccion(org, cuenta, photos=[_imagen_subida()]),
        follow=True,
    )

    assert not Transaction.objects.filter(organization=org).exists()
    assert TransactionPhoto.objects.count() == 0


@pytest.mark.django_db
def test_formulario_invalido_no_guarda_fotos(client, tmp_path, settings):
    from .models import TransactionPhoto

    settings.MEDIA_ROOT = str(tmp_path)
    _, org, cuenta = _org_con_cuenta(client, 'invalido', tmp_path)

    # description es obligatoria: el formulario no valida.
    client.post(
        reverse('crear_transaccion'),
        _datos_transaccion(org, cuenta, description='', photos=[_imagen_subida()]),
        follow=True,
    )

    assert not Transaction.objects.filter(organization=org).exists()
    assert TransactionPhoto.objects.count() == 0
    # Sin archivos huérfanos en el almacenamiento.
    assert not list(tmp_path.rglob('*.jpg'))


@pytest.mark.django_db
def test_listar_fotos_devuelve_el_partial(client, tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)
    _, org, cuenta = _org_con_cuenta(client, 'listar', tmp_path)
    tx = _crear_transaccion_con_fotos(client, org, cuenta, 2)

    response = client.get(reverse('listar_fotos_transaccion', args=[tx.id]))
    assert response.status_code == 200
    contenido = response.content.decode()
    for foto in tx.photos.all():
        assert f'data-foto-id="{foto.id}"' in contenido


def test_modales_de_transaccion_tienen_enctype():
    """El modal #transactionForm está duplicado en tres plantillas.

    Sin enctype="multipart/form-data" el navegador no envía los archivos y
    request.FILES llega vacío sin ningún error visible: las fotos simplemente
    desaparecen. Este test evita que se olvide en alguna de las tres copias.
    """
    from pathlib import Path

    base = Path(__file__).resolve().parent.parent / 'templates' / 'organizations'
    plantillas = ['transacciones.html', 'detalle_cuenta.html', 'detalle_proyecto.html']

    sin_enctype = []
    sin_loading = []
    for nombre in plantillas:
        contenido = (base / nombre).read_text(encoding='utf-8')
        for linea in contenido.splitlines():
            if 'id="transactionForm"' not in linea:
                continue
            if 'multipart/form-data' not in linea:
                sin_enctype.append(nombre)
            # Recomprimir las fotos tarda: sin estado de carga el usuario cree
            # que no pasó nada y vuelve a pulsar Guardar.
            if 'data-cf-loading' not in linea:
                sin_loading.append(nombre)

    assert not sin_enctype, f"Falta enctype multipart en: {', '.join(sin_enctype)}"
    assert not sin_loading, f"Falta data-cf-loading en: {', '.join(sin_loading)}"


def test_el_visor_de_fotos_se_dibuja_sobre_los_demas_modales():
    """#photoModal se abre encima del modal de detalle o del de edición.

    Todos los .cf-modal comparten z-index 2000, así que sin una regla explícita
    ganaría el que aparezca después en el DOM y la foto quedaría por detrás.
    """
    import re
    from pathlib import Path

    css = (Path(__file__).resolve().parent.parent
           / 'static' / 'css' / 'base' / 'photos.css').read_text(encoding='utf-8')

    bloque = re.search(r'#photoModal\s*\{([^}]*)\}', css)
    assert bloque, "photos.css no define una regla para #photoModal"

    z = re.search(r'z-index:\s*(\d+)', bloque.group(1))
    assert z, "#photoModal no fija z-index"
    assert int(z.group(1)) > 2000, f"z-index {z.group(1)} no supera el de .cf-modal (2000)"


def _heic_subido(nombre='IMG_0001.HEIC', size=(1600, 1200), content_type='image/heic'):
    """HEIC real, como el que sube un iPhone con la cámara en 'Alta eficiencia'."""
    import io

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image
    import pillow_heif

    pillow_heif.register_heif_opener()
    buf = io.BytesIO()
    Image.new('RGB', size, 'darkgreen').save(buf, format='HEIF', quality=90)
    return SimpleUploadedFile(nombre, buf.getvalue(), content_type=content_type)


@pytest.mark.django_db
def test_acepta_heic_y_lo_convierte_a_jpg(client, tmp_path, settings):
    """Los iPhone graban HEIC: debe aceptarse y quedar guardado como JPEG."""
    settings.MEDIA_ROOT = str(tmp_path)
    _, org, cuenta = _org_con_cuenta(client, 'heic', tmp_path)

    client.post(
        reverse('crear_transaccion'),
        _datos_transaccion(org, cuenta, photos=[_heic_subido()]),
        follow=True,
    )

    tx = Transaction.objects.get(organization=org)
    foto = tx.photos.get()

    assert foto.original_filename == 'IMG_0001.HEIC'
    assert foto.image.name.endswith('.jpg')
    assert foto.size_bytes <= settings.TRANSACTION_PHOTO_TARGET_BYTES

    # El archivo en disco es realmente un JPEG, no un HEIC renombrado.
    from PIL import Image
    with foto.image.open('rb') as fh:
        assert Image.open(fh).format == 'JPEG'


@pytest.mark.django_db
def test_acepta_heic_con_content_type_generico(client, tmp_path, settings):
    """Algunos navegadores envían application/octet-stream para HEIC: la
    comprobación real es Pillow, no la cabecera declarada por el cliente."""
    settings.MEDIA_ROOT = str(tmp_path)
    _, org, cuenta = _org_con_cuenta(client, 'heicgen', tmp_path)

    client.post(
        reverse('crear_transaccion'),
        _datos_transaccion(
            org, cuenta,
            photos=[_heic_subido(content_type='application/octet-stream')],
        ),
        follow=True,
    )

    assert Transaction.objects.get(organization=org).photos.count() == 1


@pytest.mark.django_db
def test_sigue_rechazando_un_no_imagen_con_extension_heic(client, tmp_path, settings):
    """Ampliar los formatos no debe abrir la puerta a archivos arbitrarios."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    from .models import TransactionPhoto

    settings.MEDIA_ROOT = str(tmp_path)
    _, org, cuenta = _org_con_cuenta(client, 'falsoheic', tmp_path)

    falso = SimpleUploadedFile('falso.heic', b'no soy un HEIC', content_type='image/heic')
    client.post(
        reverse('crear_transaccion'),
        _datos_transaccion(org, cuenta, photos=[falso]),
        follow=True,
    )

    assert not Transaction.objects.filter(organization=org).exists()
    assert TransactionPhoto.objects.count() == 0
