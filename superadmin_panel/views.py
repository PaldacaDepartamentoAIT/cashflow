from django.contrib import messages
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Prefetch
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from datetime import date
from decimal import Decimal, InvalidOperation
import json

from BCV.models import ExchangeRateHistory
from BCV.services.bcv_scrapper import get_rate_for_date
from CashFlow.debug import first_form_error
from accounts.models import Profile
from organizations.amounts import create_initial_balance_transaction
from organizations.models import Account, Organization, OrganizationAccess, Transaction, TransactionAuditLog

from .decorators import superadmin_required
from .forms import (
    BcvRateForm,
    OrganizationAccessForm,
    SuperadminOrganizationForm,
    SuperadminOrganizationWizardForm,
    SuperadminUserCreateForm,
    SuperadminUserEditForm,
)


def _serialize_bcv_rate(rate):
    if not rate:
        return None
    return {
        'id': rate.id,
        'rate': f'{rate.rate:.4f}',
        'fetched_at': timezone.localtime(rate.fetched_at).strftime('%d/%m/%Y %H:%M'),
    }


def _bcv_rates_payload(selected_date):
    rates_qs = ExchangeRateHistory.objects.filter(
        source=ExchangeRateHistory.SOURCE_BCV,
        rate_date=selected_date,
    )
    rates_by_currency = {r.currency: r for r in rates_qs}
    return {
        'date': selected_date.isoformat(),
        'date_display': selected_date.strftime('%d/%m/%Y'),
        'weekday': selected_date.strftime('%A'),
        'usd': _serialize_bcv_rate(rates_by_currency.get(ExchangeRateHistory.CURRENCY_USD)),
        'eur': _serialize_bcv_rate(rates_by_currency.get(ExchangeRateHistory.CURRENCY_EUR)),
    }


def _dates_with_bcv_rates(year, month):
    return sorted({
        d.isoformat()
        for d in ExchangeRateHistory.objects.filter(
            source=ExchangeRateHistory.SOURCE_BCV,
            rate_date__year=year,
            rate_date__month=month,
        ).values_list('rate_date', flat=True).distinct()
    })


@superadmin_required
def dashboard(request):
    stats = {
        'organizations': Organization.objects.count(),
        'users': User.objects.filter(is_active=True).count(),
        'accesses': OrganizationAccess.objects.count(),
    }
    return render(request, 'superadmin_panel/dashboard.html', {'stats': stats    })


def _get_bcv_rate_decimal():
    try:
        rate = get_rate_for_date(timezone.localdate(), currency='USD')
        if rate is not None:
            return Decimal(str(rate))
    except Exception:
        pass
    return Decimal('1')


def _parse_decimal(value):
    if value is None:
        return Decimal('0')
    raw = str(value).strip()
    if not raw:
        return Decimal('0')
    try:
        return Decimal(raw.replace(',', '.'))
    except InvalidOperation:
        return None


def _resolve_account_amounts(usd_raw, bs_raw, rate):
    usd = _parse_decimal(usd_raw)
    bs = _parse_decimal(bs_raw)
    if usd is None or bs is None:
        return None, None
    if usd != 0 and bs == 0:
        bs = (usd * rate).quantize(Decimal('0.01'))
    elif bs != 0 and usd == 0:
        usd = (bs / rate).quantize(Decimal('0.01')) if rate else Decimal('0')
    return usd, bs


def _parse_wizard_accounts(post_data):
    """Lee las cuentas del asistente: solo nombre, moneda y saldo inicial.

    Una cuenta agrupa transacciones de un mismo tipo; no guarda datos bancarios.
    """
    currencies = post_data.getlist('account_currency')
    names = post_data.getlist('account_name')
    balances = post_data.getlist('account_balance')
    accounts = []
    errors = []

    total = len(currencies)
    if total == 0:
        errors.append('Agregue al menos una cuenta en bolívares, dólares o euros.')
        return accounts, errors

    valid_currencies = {code for code, _ in Account.CURRENCY_CHOICES}

    for index in range(total):
        currency = (currencies[index] if index < len(currencies) else '').upper()
        name = (names[index] if index < len(names) else '').strip()
        balance_raw = balances[index] if index < len(balances) else ''

        # Fila vacía: el asistente siempre envía una por moneda.
        if not name:
            continue

        if currency not in valid_currencies:
            errors.append(f'Cuenta #{index + 1}: moneda no válida.')
            continue

        balance = _parse_decimal(balance_raw)
        if balance is None:
            errors.append(f'Cuenta {name}: saldo inicial inválido.')
            continue
        if balance < 0:
            errors.append(f'Cuenta {name}: el saldo inicial no puede ser negativo.')
            continue

        accounts.append({
            'currency': currency,
            'name': name,
            'balance': balance,
        })

    if not accounts and not errors:
        errors.append('Agregue al menos una cuenta válida.')
    return accounts, errors

@superadmin_required
def organizaciones(request):
    orgs = (
        Organization.objects.annotate(
            users_count=Count('user_accesses', distinct=True),
            accounts_count=Count('accounts', distinct=True),
            projects_count=Count('projects', distinct=True),
            transactions_count=Count('transactions', distinct=True),
        )
        .prefetch_related(
            Prefetch('user_accesses', queryset=OrganizationAccess.objects.select_related('user'))
        )
        .order_by('name')
    )
    org_form = SuperadminOrganizationForm()
    wizard_form = SuperadminOrganizationWizardForm()
    access_form = OrganizationAccessForm()
    return render(request, 'superadmin_panel/organizaciones.html', {
        'organizations': orgs,
        'org_form': org_form,
        'wizard_form': wizard_form,
        'access_form': access_form,
        'all_users': User.objects.filter(is_superuser=False).order_by('username'),
        'bcv_rate': _get_bcv_rate_decimal(),
    })


@superadmin_required
def usuarios(request):
    users = (
        User.objects.select_related('profile').annotate(
            orgs_count=Count('organization_accesses', distinct=True),
        )
        .order_by('username')
    )
    create_form = SuperadminUserCreateForm()
    edit_form = SuperadminUserEditForm()
    return render(request, 'superadmin_panel/usuarios.html', {
        'users': users,
        'create_form': create_form,
        'edit_form': edit_form,
    })


@superadmin_required
def guardar_usuario(request, user_id=None):
    if request.method != 'POST':
        return redirect('superadmin_usuarios')

    user = get_object_or_404(User, pk=user_id) if user_id else None
    form_class = SuperadminUserEditForm if user else SuperadminUserCreateForm
    form = form_class(request.POST, instance=user)
    if form.is_valid():
        if user:
            # Si estamos editando un usuario existente
            if user.pk == request.user.pk:
                # El superadmin actual no puede desactivarse ni quitarse el superuser desde aquí
                user_obj = form.save(commit=False)
                user_obj.is_superuser = True
                user_obj.is_active = True
                user_obj.save()
                # Manual profile update since commit=False skips the form's save logic for the profile
                profile, _ = Profile.objects.get_or_create(user=user_obj)
                profile.edit = form.cleaned_data.get('edit')
                profile.save()
                form.save_m2m() # Guardar el resto de relaciones si las hubiera
            else:
                form.save()
        else:
            # Nuevo usuario
            form.save()
        
        action = 'actualizado' if user else 'creado'
        messages.success(request, f'Usuario "{form.instance.username}" {action} correctamente.')
    else:
        messages.error(request, f'No se pudo guardar el usuario: {first_form_error(form)}')
    return redirect('superadmin_usuarios')


@superadmin_required
def eliminar_usuario(request, user_id):
    if request.method != 'POST':
        return redirect('superadmin_usuarios')

    user = get_object_or_404(User, pk=user_id)
    if user.pk == request.user.pk:
        messages.error(
            request,
            'No puede eliminar su propia cuenta de superadministrador: pida a otro '
            'superadministrador que la elimine si es necesario.'
        )
        return redirect('superadmin_usuarios')

    username = user.username
    user.delete()
    messages.success(request, f'Usuario "{username}" eliminado.')
    return redirect('superadmin_usuarios')


def _wizard_error_messages(form, account_errors):
    errors = list(form.non_field_errors())
    for errs in form.errors.values():
        errors.extend(str(err) for err in errs)
    errors.extend(account_errors)
    return errors


def _wizard_error_response(request, form, account_errors):
    errors = _wizard_error_messages(form, account_errors)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': False, 'errors': errors}, status=400)

    for err in errors:
        messages.error(request, err)
    return redirect('superadmin_organizaciones')


@superadmin_required
def crear_organizacion_wizard(request):
    if request.method != 'POST':
        return redirect('superadmin_organizaciones')

    form = SuperadminOrganizationWizardForm(request.POST)
    accounts, account_errors = _parse_wizard_accounts(request.POST)

    if not form.is_valid() or account_errors:
        return _wizard_error_response(request, form, account_errors)

    rate = _get_bcv_rate_decimal()
    org_name = form.cleaned_data['name']
    org_users = list(form.cleaned_data.get('org_users') or [])
    user_ids = {user.pk for user in org_users}
    new_username = form.cleaned_data.get('new_user_username', '').strip()

    with transaction.atomic():
        org = Organization.objects.create(name=org_name)

        created_username = None
        if new_username:
            new_user = User.objects.create_user(
                username=new_username,
                email=form.cleaned_data['new_user_email'],
                password=form.cleaned_data['new_user_password1'],
                first_name=form.cleaned_data.get('new_user_first_name') or '',
                last_name=form.cleaned_data.get('new_user_last_name') or '',
            )
            user_ids.add(new_user.pk)
            created_username = new_user.username

        for user_id in user_ids:
            OrganizationAccess.objects.create(organization=org, user_id=user_id)

        for account_data in accounts:
            account = Account.objects.create(
                organization=org,
                currency=account_data['currency'],
                name=account_data['name'],
            )
            create_initial_balance_transaction(
                organization=org,
                account=account,
                balance=account_data['balance'],
                daily_rate=rate,
                created_by=request.user,
            )

    admins_count = len(user_ids)
    detail_parts = [f'{len(accounts)} cuenta(s)', f'{admins_count} administrador(es)']
    if created_username:
        detail_parts.append(f'usuario nuevo "{created_username}"')
    success_message = f'Organización "{org_name}" creada con {", ".join(detail_parts)}.'
    messages.success(request, success_message)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'ok': True,
            'redirect': reverse('superadmin_organizaciones'),
        })
    return redirect('superadmin_organizaciones')


@superadmin_required
def guardar_organizacion(request, org_id=None):
    if request.method != 'POST':
        return redirect('superadmin_organizaciones')

    if not org_id:
        return redirect('superadmin_organizaciones')

    org = get_object_or_404(Organization, pk=org_id)
    form = SuperadminOrganizationForm(request.POST, instance=org)
    if form.is_valid():
        form.save()
        messages.success(request, 'Organización guardada correctamente.')
    else:
        messages.error(request, f'No se pudo guardar la organización: {first_form_error(form)}')
    return redirect('superadmin_organizaciones')


@superadmin_required
def eliminar_organizacion(request, org_id):
    if request.method != 'POST':
        return redirect('superadmin_organizaciones')

    org = get_object_or_404(Organization, pk=org_id)
    name = org.name
    org.delete()
    messages.success(request, f'Organización "{name}" eliminada.')
    return redirect('superadmin_organizaciones')


@superadmin_required
def actualizar_accesos_organizacion(request, org_id):
    if request.method != 'POST':
        return redirect('superadmin_organizaciones')

    org = get_object_or_404(Organization, pk=org_id)
    form = OrganizationAccessForm(request.POST)
    if form.is_valid():
        selected_users = set(form.cleaned_data['users'].values_list('pk', flat=True))
        current_users = set(
            OrganizationAccess.objects.filter(organization=org).values_list('user_id', flat=True)
        )
        to_add = selected_users - current_users
        to_remove = current_users - selected_users

        OrganizationAccess.objects.filter(organization=org, user_id__in=to_remove).delete()
        for user_id in to_add:
            OrganizationAccess.objects.create(organization=org, user_id=user_id)

        messages.success(request, f'Accesos actualizados para "{org.name}".')
    else:
        messages.error(request, f'No se pudieron actualizar los accesos: {first_form_error(form)}')
    return redirect('superadmin_organizaciones')


@superadmin_required
def tasas_bcv(request):
    selected_date_str = request.GET.get('date') or timezone.localdate().isoformat()
    try:
        selected_date = date.fromisoformat(selected_date_str)
    except ValueError:
        selected_date = timezone.localdate()
        selected_date_str = selected_date.isoformat()

    rates_by_currency = {
        r.currency: r
        for r in ExchangeRateHistory.objects.filter(
            source=ExchangeRateHistory.SOURCE_BCV,
            rate_date=selected_date,
        )
    }

    recent_rates = (
        ExchangeRateHistory.objects.filter(source=ExchangeRateHistory.SOURCE_BCV)
        .order_by('-rate_date', 'currency')[:15]
    )

    return render(request, 'superadmin_panel/tasas_bcv.html', {
        'selected_date': selected_date,
        'selected_date_str': selected_date_str,
        'calendar_year': selected_date.year,
        'calendar_month': selected_date.month,
        'dates_with_rates_json': json.dumps(_dates_with_bcv_rates(selected_date.year, selected_date.month)),
        'today_str': timezone.localdate().isoformat(),
        'recent_rates': recent_rates,
        'usd_rate': rates_by_currency.get(ExchangeRateHistory.CURRENCY_USD),
        'eur_rate': rates_by_currency.get(ExchangeRateHistory.CURRENCY_EUR),
    })


@superadmin_required
def tasas_bcv_api(request):
    date_str = request.GET.get('date')
    if date_str:
        try:
            selected_date = date.fromisoformat(date_str)
        except ValueError:
            return JsonResponse({'error': 'Fecha inválida.'}, status=400)
        return JsonResponse(_bcv_rates_payload(selected_date))

    year = request.GET.get('year')
    month = request.GET.get('month')
    if year and month:
        try:
            year_int = int(year)
            month_int = int(month)
            if not (1 <= month_int <= 12):
                raise ValueError
        except ValueError:
            return JsonResponse({'error': 'Mes o año inválido.'}, status=400)
        return JsonResponse({
            'year': year_int,
            'month': month_int,
            'dates_with_rates': _dates_with_bcv_rates(year_int, month_int),
        })

    return JsonResponse({'error': 'Parámetros requeridos: date o year+month.'}, status=400)


@superadmin_required
def guardar_tasa_bcv(request):
    if request.method != 'POST':
        return redirect('superadmin_tasas_bcv')

    form = BcvRateForm(request.POST)
    if form.is_valid():
        rate_date = form.cleaned_data['rate_date']
        currency = form.cleaned_data['currency']
        rate = form.cleaned_data['rate']
        ExchangeRateHistory.objects.update_or_create(
            rate_date=rate_date,
            source=ExchangeRateHistory.SOURCE_BCV,
            currency=currency,
            defaults={
                'rate': rate,
                'raw_label': 'Manual (Superadmin)',
            },
        )
        messages.success(request, f'Tasa {currency} guardada para {rate_date.strftime("%d/%m/%Y")}.')
        return redirect(reverse('superadmin_tasas_bcv') + f'?date={rate_date.isoformat()}')

    messages.error(request, f'No se pudo guardar la tasa: {first_form_error(form)}')
    rate_date = request.POST.get('rate_date') or timezone.localdate().isoformat()
    return redirect(reverse('superadmin_tasas_bcv') + f'?date={rate_date}')


@superadmin_required
def eliminar_tasa_bcv(request, rate_id):
    if request.method != 'POST':
        return redirect('superadmin_tasas_bcv')

    rate = get_object_or_404(
        ExchangeRateHistory,
        pk=rate_id,
        source=ExchangeRateHistory.SOURCE_BCV,
    )
    rate_date = rate.rate_date.isoformat()
    currency = rate.currency
    rate.delete()
    messages.success(request, f'Tasa {currency} eliminada.')
    return redirect(reverse('superadmin_tasas_bcv') + f'?date={rate_date}')


@superadmin_required
def auditoria_transacciones(request):
    logs = TransactionAuditLog.objects.select_related('organization', 'user', 'transaction').all()

    org_id = request.GET.get('organization')
    if org_id:
        logs = logs.filter(organization_id=org_id)

    action = request.GET.get('action')
    if action in dict(TransactionAuditLog.ACTION_CHOICES):
        logs = logs.filter(action=action)

    search = request.GET.get('search', '').strip()
    if search:
        logs = logs.filter(transaction_description__icontains=search)

    paginator = Paginator(logs, 30)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'superadmin_panel/auditoria.html', {
        'page_obj': page_obj,
        'organizations': Organization.objects.order_by('name'),
        'action_choices': TransactionAuditLog.ACTION_CHOICES,
        'selected_organization': org_id or '',
        'selected_action': action or '',
        'search': search,
    })


@superadmin_required
def auditoria_snapshot(request, log_id):
    log = get_object_or_404(TransactionAuditLog, id=log_id)
    return render(request, 'superadmin_panel/partials/auditoria_snapshot.html', {'log': log})
