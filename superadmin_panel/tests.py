from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from organizations.models import Account, Organization, OrganizationAccess, Transaction


class SuperadminPanelTests(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='password123',
        )
        self.user = User.objects.create_user(
            username='normal',
            email='normal@test.com',
            password='password123',
        )
        self.client = Client()

    def test_superuser_login_redirects_to_panel(self):
        response = self.client.post(reverse('login'), {
            'username': 'admin',
            'password': 'password123',
        })
        self.assertRedirects(response, reverse('superadmin_dashboard'))

    def test_superuser_blocked_from_org_dashboard(self):
        self.client.login(username='admin', password='password123')
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, reverse('superadmin_dashboard'))

    def test_normal_user_cannot_access_superadmin(self):
        self.client.login(username='normal', password='password123')
        response = self.client.get(reverse('superadmin_dashboard'))
        self.assertEqual(response.status_code, 403)

    def test_superuser_can_access_usuarios(self):
        self.client.login(username='admin', password='password123')
        response = self.client.get(reverse('superadmin_usuarios'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'normal')

    def test_superuser_cannot_delete_self(self):
        self.client.login(username='admin', password='password123')
        response = self.client.post(reverse('superadmin_eliminar_usuario', args=[self.superadmin.pk]))
        self.assertRedirects(response, reverse('superadmin_usuarios'))
        self.assertTrue(User.objects.filter(pk=self.superadmin.pk).exists())

    def test_wizard_creates_bs_account(self):
        self.client.login(username='admin', password='password123')
        response = self.client.post(reverse('superadmin_crear_organizacion_wizard'), {
            'name': 'Empresa Test',
            'org_users': [self.user.pk],
            'account_currency': ['BS'],
            'account_name': ['Caja Bs.'],
            'account_balance': ['1000.00'],
        })
        self.assertRedirects(response, reverse('superadmin_organizaciones'))
        org = Organization.objects.get(name='Empresa Test')
        account = Account.objects.get(organization=org)
        self.assertEqual(account.currency, Account.CURRENCY_BS)
        self.assertEqual(account.name, 'Caja Bs.')
        self.assertEqual(Transaction.objects.filter(account=account).count(), 1)
        tx = Transaction.objects.get(account=account)
        self.assertEqual(tx.amount_bs, 1000)
        self.assertGreater(tx.amount_usd, 0)

    def test_wizard_creates_usd_account_separately(self):
        self.client.login(username='admin', password='password123')
        response = self.client.post(reverse('superadmin_crear_organizacion_wizard'), {
            'name': 'Empresa USD',
            'org_users': [self.user.pk],
            'account_currency': ['USD'],
            'account_name': ['Caja USD'],
            'account_balance': ['250.00'],
        })
        self.assertRedirects(response, reverse('superadmin_organizaciones'))
        account = Account.objects.get(organization__name='Empresa USD')
        self.assertEqual(account.currency, Account.CURRENCY_USD)
        tx = Transaction.objects.get(account=account)
        self.assertEqual(tx.real_dollars, 250)
        self.assertEqual(tx.amount_usd, 0)
        self.assertEqual(tx.amount_bs, 0)

