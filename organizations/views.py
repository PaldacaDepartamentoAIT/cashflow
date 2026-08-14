from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db import models
from django.db.models import Sum, OuterRef, Subquery, Value, F, Q, Count
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib import messages
from django.core.paginator import Paginator
from django.core import signing
from django.urls import reverse
from datetime import timedelta
import json
from decimal import Decimal

from .models import Organization, OrganizationAccess, Transaction, TransactionAuditLog, Category, Account, Project, Valuation, CostCenter, ProjectShareLink
from accounts.models import Profile
from accounts.decorators import viewer_restricted
from .amounts import create_initial_balance_transaction
from .audit import log_transaction_audit
from .forms import TransactionForm, CategoryForm, AccountForm, ProjectForm, ValuationForm
from CashFlow.debug import debug_event, first_form_error
from BCV.services.bcv_scrapper import as_dashboard_rates, get_rate_for_date


def get_chart_data(transactions_qs, mode='bcv', json_format=True):
    # 1. Desglose de Gastos por Categoría
    if mode == 'real':
        category_spending = transactions_qs.filter(real_dollars__lt=0).values('categories__name', 'categories__color').annotate(
            total=Sum('real_dollars')
        ).order_by('total')
    else:
        category_spending = transactions_qs.filter(amount_usd__lt=0).values('categories__name', 'categories__color').annotate(
            total=Sum('amount_usd')
        ).order_by('total')
    
    cat_labels = [item['categories__name'] or 'Sin categoría' for item in category_spending]
    cat_series = [float(abs(item['total'] or 0)) for item in category_spending]
    cat_colors = [item['categories__color'] or '#000000' for item in category_spending]

    # 2. Gastos por Centro de Costo (Porcentajes)
    if mode == 'real':
        cost_center_spending = transactions_qs.filter(real_dollars__lt=0, cost_center__isnull=False).values('cost_center__name').annotate(
            total=Sum('real_dollars')
        ).order_by('total')
    else:
        cost_center_spending = transactions_qs.filter(amount_usd__lt=0, cost_center__isnull=False).values('cost_center__name').annotate(
            total=Sum('amount_usd')
        ).order_by('total')
    
    cc_labels = [item['cost_center__name'] or 'Sin centro de costo' for item in cost_center_spending]
    cc_values = [float(abs(item['total'] or 0)) for item in cost_center_spending]
    total_expense_cc = sum(cc_values)
    cc_percentages = [(v / total_expense_cc * 100) if total_expense_cc > 0 else 0 for v in cc_values]

    # 2. Balance Total (Ingresos vs Gastos)
    if mode == 'real':
        totals_data = transactions_qs.aggregate(
            income=Sum('real_dollars', filter=Q(real_dollars__gt=0)),
            expense=Sum('real_dollars', filter=Q(real_dollars__lt=0)),
            fees=Sum('bank_fee_real_usd')
        )
        total_income = float(totals_data['income'] or 0)
        total_expense = float(abs(totals_data['expense'] or 0)) + float(totals_data['fees'] or 0)
    else:
        totals_data = transactions_qs.aggregate(
            income=Sum('amount_usd', filter=Q(amount_usd__gt=0)),
            expense=Sum('amount_usd', filter=Q(amount_usd__lt=0)),
            fees=Sum('bank_fee_usd')
        )
        total_income = float(totals_data['income'] or 0)
        total_expense = float(abs(totals_data['expense'] or 0)) + float(totals_data['fees'] or 0)

    # 3. Evolución del Saldo
    if mode == 'real':
        evolution_data = transactions_qs.order_by('date').values('date').annotate(
            daily_sum=Sum(F('real_dollars') - F('bank_fee_real_usd'))
        )
    else:
        evolution_data = transactions_qs.order_by('date').values('date').annotate(
            daily_sum=Sum(F('amount_usd') - F('bank_fee_usd'))
        )
    
    evo_labels = []
    evo_series = []
    current_balance = 0
    for item in evolution_data:
        current_balance += float(item['daily_sum'] or 0)
        evo_labels.append(item['date'].strftime('%Y-%m-%d'))
        evo_series.append(round(current_balance, 2))

    if json_format:
        return {
            'cat_labels': json.dumps(cat_labels),
            'cat_series': json.dumps(cat_series),
            'cat_colors': json.dumps(cat_colors),
            'total_income': total_income,
            'total_expense': total_expense,
            'evo_labels': json.dumps(evo_labels),
            'evo_series': json.dumps(evo_series),
            'cc_labels': json.dumps(cc_labels),
            'cc_percentages': json.dumps(cc_percentages),
        }
    else:
        return {
            'cat_labels': cat_labels,
            'cat_series': cat_series,
            'cat_colors': cat_colors,
            'total_income': total_income,
            'total_expense': total_expense,
            'evo_labels': evo_labels,
            'evo_series': evo_series,
            'cc_labels': cc_labels,
            'cc_percentages': cc_percentages,
        }

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

@login_required
def dashboard(request):
    accesses = OrganizationAccess.objects.filter(user=request.user)
    organizations = [access.organization for access in accesses]
    return render(request, 'organizations/dashboard.html', {
        'organizations': organizations,
        'hide_sidebar': True,
    })

@login_required
def seleccionar_organizacion(request, org_id):
    get_object_or_404(OrganizationAccess, user=request.user, organization_id=org_id)
    org = get_object_or_404(Organization, id=org_id)
    request.session['org_id'] = org.id
    request.session['org_name'] = org.name
    return redirect('home_organizacion')

def get_filtered_totals_both(org_id, filter_type):
    now = timezone.now()
    transactions = Transaction.objects.filter(organization_id=org_id)
    
    if filter_type == 'day':
        start_date = now - timedelta(days=1)
        transactions = transactions.filter(date__gte=start_date)
    elif filter_type == 'week':
        start_date = now - timedelta(weeks=1)
        transactions = transactions.filter(date__gte=start_date)
    elif filter_type == '15days':
        start_date = now - timedelta(days=15)
        transactions = transactions.filter(date__gte=start_date)
    elif filter_type == 'month':
        start_date = now - timedelta(days=30)
        transactions = transactions.filter(date__gte=start_date)
    elif filter_type == '3months':
        start_date = now - timedelta(days=90)
        transactions = transactions.filter(date__gte=start_date)
    elif filter_type == '6months':
        start_date = now - timedelta(days=180)
        transactions = transactions.filter(date__gte=start_date)
    elif filter_type == 'year':
        start_date = now - timedelta(days=365)
        transactions = transactions.filter(date__gte=start_date)

    res = transactions.aggregate(
        income_usd=Sum('amount_usd', filter=models.Q(amount_usd__gt=0)),
        expense_usd=Sum('amount_usd', filter=models.Q(amount_usd__lt=0)),
        fees_usd=Sum('bank_fee_usd'),
        income_bs=Sum('amount_bs', filter=models.Q(amount_bs__gt=0)),
        expense_bs=Sum('amount_bs', filter=models.Q(amount_bs__lt=0)),
        fees_bs=Sum('bank_fee_bs'),
        income_real_usd=Sum('real_dollars', filter=models.Q(real_dollars__gt=0)),
        expense_real_usd=Sum('real_dollars', filter=models.Q(real_dollars__lt=0)),
        fees_real_usd=Sum('bank_fee_real_usd')
    )

    return {
        'income_usd': res['income_usd'] or 0,
        'expense_usd': abs(res['expense_usd'] or 0) + (res['fees_usd'] or 0),
        'income_bs': res['income_bs'] or 0,
        'expense_bs': abs(res['expense_bs'] or 0) + (res['fees_bs'] or 0),
        'income_real_usd': res['income_real_usd'] or 0,
        'expense_real_usd': abs(res['expense_real_usd'] or 0) + (res['fees_real_usd'] or 0),
    }

def get_bcv_rate(target_date=None):
    rate_date = target_date or timezone.localdate()
    try:
        # Si es para hoy, usar la misma lógica que el dashboard para consistencia total
        if rate_date == timezone.localdate():
            rates = as_dashboard_rates()
            if rates.get('usd_bcv') and rates['usd_bcv'].get('promedio') is not None:
                return float(rates['usd_bcv']['promedio'])

        rate = get_rate_for_date(rate_date, currency="USD")
        if rate is not None:
            return float(rate)
    except Exception as exc:
        debug_event(
            "bcv.tasa.error",
            rate_date=str(rate_date),
            exception=str(exc),
        )
        return 1.0
    debug_event(
        "bcv.tasa.error",
        rate_date=str(rate_date),
        reason="no_rate_available",
    )
    return 1.0

@login_required
def home_organizacion(request):
    org_id = request.session.get('org_id')
    if not org_id:
        return redirect('dashboard')
    
    view_mode = request.GET.get('view_mode', 'bcv') # 'bcv' or 'real'
    
    totals = Transaction.objects.filter(organization_id=org_id).aggregate(
        balance_usd=Sum(F('amount_usd') - F('bank_fee_usd')),
        balance_bs=Sum(F('amount_bs') - F('bank_fee_bs')),
        balance_real_usd=Sum(F('real_dollars') - F('bank_fee_real_usd'))
    )

    pending_totals = Transaction.objects.filter(organization_id=org_id, status='pendiente').aggregate(
        balance_usd=Sum(F('amount_usd') - F('bank_fee_usd')),
        balance_bs=Sum(F('amount_bs') - F('bank_fee_bs')),
        balance_real_usd=Sum(F('real_dollars') - F('bank_fee_real_usd')),
        count=Count('id')
    )
    has_pending = pending_totals['count'] > 0

    income_filter = request.GET.get('income_filter', 'all')
    expense_filter = request.GET.get('expense_filter', 'all')

    def get_filtered_totals_by_mode(filter_val, mode, status=None):
        transactions = Transaction.objects.filter(organization_id=org_id)
        if status:
            transactions = transactions.filter(status=status)
        today = timezone.localdate()
        if filter_val != 'all':
            if filter_val == 'day': start_date = today - timedelta(days=1)
            elif filter_val == 'week': start_date = today - timedelta(days=7)
            elif filter_val == '15days': start_date = today - timedelta(days=15)
            elif filter_val == 'month': start_date = today - timedelta(days=30)
            elif filter_val == '3months': start_date = today - timedelta(days=90)
            elif filter_val == '6months': start_date = today - timedelta(days=180)
            elif filter_val == 'year': start_date = today - timedelta(days=365)
            transactions = transactions.filter(date__gte=start_date)

        if mode == 'real':
            res = transactions.aggregate(
                income=Sum('real_dollars', filter=models.Q(real_dollars__gt=0)),
                expense=Sum('real_dollars', filter=models.Q(real_dollars__lt=0)),
                fees=Sum('bank_fee_real_usd'),
                count=Count('id')
            )
            return {
                'income': res['income'] or 0,
                'expense': abs(res['expense'] or 0) + (res['fees'] or 0),
                'count': res['count'],
            }
        else:
            res = transactions.aggregate(
                income_usd=Sum('amount_usd', filter=models.Q(amount_usd__gt=0)),
                expense_usd=Sum('amount_usd', filter=models.Q(amount_usd__lt=0)),
                fees_usd=Sum('bank_fee_usd'),
                income_bs=Sum('amount_bs', filter=models.Q(amount_bs__gt=0)),
                expense_bs=Sum('amount_bs', filter=models.Q(amount_bs__lt=0)),
                fees_bs=Sum('bank_fee_bs'),
                count=Count('id')
            )
            return {
                'income_usd': res['income_usd'] or 0,
                'expense_usd': abs(res['expense_usd'] or 0) + (res['fees_usd'] or 0),
                'income_bs': res['income_bs'] or 0,
                'expense_bs': abs(res['expense_bs'] or 0) + (res['fees_bs'] or 0),
                'count': res['count'],
            }

    inc_totals = get_filtered_totals_by_mode(income_filter, view_mode)
    exp_totals = get_filtered_totals_by_mode(expense_filter, view_mode)
    inc_pending_totals = get_filtered_totals_by_mode(income_filter, view_mode, status='pendiente')
    exp_pending_totals = get_filtered_totals_by_mode(expense_filter, view_mode, status='pendiente')
    
    try:
        rates = as_dashboard_rates()
    except Exception:
        rates = {
            'usd_bcv': None,
            'usd_paralelo': None,
            'eur_bcv': None,
            'eur_paralelo': None,
        }
    
    sort = request.GET.get('sort', 'desc')
    recent_transactions = Transaction.objects.filter(organization_id=org_id).order_by('-date', '-id')[:10]
    
    # Filtrar chart_data por el modo seleccionado
    base_qs = Transaction.objects.filter(organization_id=org_id)
    if view_mode == 'real':
        chart_qs = base_qs.exclude(models.Q(real_dollars=0) | models.Q(real_dollars__isnull=True))
    else:
        chart_qs = base_qs.filter(models.Q(real_dollars=0) | models.Q(real_dollars__isnull=True))
        
    chart_data = get_chart_data(chart_qs, mode=view_mode)
    
    context = {
        'view_mode': view_mode,
        'balance_usd': totals['balance_usd'] or 0,
        'balance_bs': totals['balance_bs'] or 0,
        'balance_real_usd': totals['balance_real_usd'] or 0,
        'income_usd': inc_totals.get('income_usd', 0),
        'income_bs': inc_totals.get('income_bs', 0),
        'income_real_usd': inc_totals.get('income', 0),
        'expense_usd': exp_totals.get('expense_usd', 0),
        'expense_bs': exp_totals.get('expense_bs', 0),
        'expense_real_usd': exp_totals.get('expense', 0),
        'has_pending': has_pending,
        'pending_balance_usd': pending_totals['balance_usd'] or 0,
        'pending_balance_bs': pending_totals['balance_bs'] or 0,
        'pending_balance_real_usd': pending_totals['balance_real_usd'] or 0,
        'pending_income_usd': inc_pending_totals.get('income_usd', 0),
        'pending_income_bs': inc_pending_totals.get('income_bs', 0),
        'pending_income_real_usd': inc_pending_totals.get('income', 0),
        'pending_income_count': inc_pending_totals.get('count', 0),
        'pending_expense_usd': exp_pending_totals.get('expense_usd', 0),
        'pending_expense_bs': exp_pending_totals.get('expense_bs', 0),
        'pending_expense_real_usd': exp_pending_totals.get('expense', 0),
        'pending_expense_count': exp_pending_totals.get('count', 0),
        'income_filter': income_filter,
        'expense_filter': expense_filter,
        'rates': rates,
        'recent_transactions': recent_transactions,
        'chart_data': chart_data,
        'sort': sort,
        'now_ve': timezone.now(),
        'filter_options': [
            ('day', 'Último día'),
            ('week', 'Última semana'),
            ('15days', 'Últimos 15 días'),
            ('month', 'Último mes'),
            ('3months', 'Últimos 3 meses'),
            ('6months', 'Últimos 6 meses'),
            ('year', 'Último año'),
            ('all', 'Desde el principio'),
        ]
    }
    return render(request, 'organizations/home.html', context)

@login_required
def configuracion(request):
    if not request.session.get('org_id'):
        return redirect('dashboard')
    return render(request, 'organizations/configuracion.html')

@login_required
def salir_organizacion(request):
    if 'org_id' in request.session: del request.session['org_id']
    if 'org_name' in request.session: del request.session['org_name']
    return redirect('dashboard')

@login_required
@viewer_restricted
def crear_organizacion(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        if nombre:
            org = Organization.objects.create(name=nombre)
            OrganizationAccess.objects.create(user=request.user, organization=org)
            messages.success(request, f"Organización '{nombre}' creada con éxito.")
            return redirect('dashboard')
        else:
            messages.error(request, "El nombre de la organización es obligatorio: ingrese un nombre antes de crearla.")
    return render(request, 'organizations/crear.html', {'hide_sidebar': True})

# --- Transacciones ---

from io import BytesIO
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import PieChart, BarChart, LineChart, Reference
from openpyxl.chart.marker import DataPoint
from openpyxl.chart.shapes import GraphicalProperties
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.widgets.markers import makeMarker
from reportlab.lib import colors

@login_required
def lista_transacciones(request):
    org_id = request.session.get('org_id')
    if not org_id:
        return redirect('dashboard')
    
    org = get_object_or_404(Organization, id=org_id)
    
    # --- Lógica de Filtrado ---
    filter_type = request.GET.get('filter_type', 'all')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    category_raw = request.GET.getlist('category')
    category_ids = []
    for val in category_raw:
        if ',' in val:
            category_ids.extend([v.strip() for v in val.split(',') if v.strip()])
        else:
            category_ids.append(val)
    category_ids = [cid for cid in category_ids if cid and cid != 'None' and cid != 'null']
    cost_center_id = request.GET.get('cost_center')
    project_id = request.GET.get('project')
    account_id = request.GET.get('account')
    search_query = request.GET.get('search', '')
    tx_filter = request.GET.get('tx_filter', 'all') # 'all', 'bcv', 'real'
    view_mode = request.GET.get('view_mode', 'bcv') # 'bcv' or 'real'
    status_filter = request.GET.get('status', '') # 'completado', 'pendiente', ''

    # Sincronización: El filtro de transacciones afecta al toggle de balance
    if tx_filter == 'real':
        view_mode = 'real'
    elif tx_filter == 'bcv':
        view_mode = 'bcv'
    # Si es 'all', se mantiene el view_mode que venga en el GET (o el default)

    # Sanitizar valores 'None' que pueden venir de la URL
    if date_from == 'None': date_from = None
    if date_to == 'None': date_to = None
    if cost_center_id == 'None' or cost_center_id == '': cost_center_id = None
    if project_id == 'None' or project_id == '': project_id = None
    if account_id == 'None' or account_id == '': account_id = None

    # Base: TODAS las transacciones para la tabla
    transactions_list = Transaction.objects.filter(organization=org)

    # Filtrar por tipo de transacción (BCV / Real Dollars)
    if tx_filter == 'real':
        transactions_list = transactions_list.exclude(models.Q(real_dollars=0) | models.Q(real_dollars__isnull=True))
    elif tx_filter == 'bcv':
        transactions_list = transactions_list.filter(models.Q(real_dollars=0) | models.Q(real_dollars__isnull=True))
    
    if search_query:
        # OJO: el lookup categories__name atraviesa una relación M2M, lo que puede
        # multiplicar filas si la transacción tiene más de una categoría (aparecería
        # duplicada en la tabla y en los KPIs). Se aplica distinct() para evitarlo.
        transactions_list = transactions_list.filter(
            models.Q(description__icontains=search_query) |
            models.Q(reference_number__icontains=search_query) |
            models.Q(notes__icontains=search_query) |
            models.Q(categories__name__icontains=search_query) |
            models.Q(cost_center__code__icontains=search_query) |
            models.Q(cost_center__name__icontains=search_query) |
            models.Q(account__name__icontains=search_query) |
            models.Q(project__name__icontains=search_query) |
            models.Q(valuation__name__icontains=search_query) |
            models.Q(status__icontains=search_query) |
            models.Q(amount_bs__icontains=search_query) |
            models.Q(amount_usd__icontains=search_query) |
            models.Q(real_dollars__icontains=search_query) |
            models.Q(daily_rate__icontains=search_query)
        ).distinct()

    if category_ids:
        transactions_list = transactions_list.filter(categories__id__in=category_ids).distinct()

    if cost_center_id:
        transactions_list = transactions_list.filter(cost_center_id=cost_center_id)

    if project_id:
        transactions_list = transactions_list.filter(project_id=project_id)

    if account_id:
        transactions_list = transactions_list.filter(account_id=account_id)

    # Punto de control: mismos filtros aplicados hasta aquí (tx_filter, búsqueda,
    # categorías, centro de costo, proyecto, cuenta) pero sin el filtro de estado, para
    # poder calcular el saldo pendiente independientemente del estado seleccionado.
    qs_before_status = transactions_list

    # Filtrar por estado (status)
    if status_filter:
        transactions_list = transactions_list.filter(status=status_filter)

    today = timezone.localdate()

    def apply_date_filter(qs):
        # Si hay fechas explícitas, ignoramos el filter_type (periodo)
        if date_from or date_to:
            if date_from:
                qs = qs.filter(date__gte=date_from)
            if date_to:
                qs = qs.filter(date__lte=date_to)
        elif filter_type != 'all' and filter_type != 'custom':
            if filter_type == 'day': start_date = today
            elif filter_type == 'week': start_date = today - timedelta(days=7)
            elif filter_type == '15days': start_date = today - timedelta(days=15)
            elif filter_type == 'month': start_date = today - timedelta(days=30)
            elif filter_type == 'quarter': start_date = today - timedelta(days=90)
            elif filter_type == '6months': start_date = today - timedelta(days=180)
            elif filter_type == 'year': start_date = today - timedelta(days=365)
            else: start_date = None
            if start_date:
                qs = qs.filter(date__gte=start_date)
                if filter_type == 'day':
                    # "Hoy" debe mostrar solo el día de hoy, no fechas futuras.
                    qs = qs.filter(date__lte=today)
        return qs

    transactions_list = apply_date_filter(transactions_list)
    pending_qs_base = apply_date_filter(qs_before_status).filter(status='pendiente')

    sort = request.GET.get('sort', 'desc')
    if sort == 'asc':
        transactions_list = transactions_list.order_by('date', 'id')
    else:
        transactions_list = transactions_list.order_by('-date', '-id')

    # --- Calcular totales filtrados basados en view_mode para los KPIs ---
    if view_mode == 'real':
        kpi_qs = transactions_list.exclude(models.Q(real_dollars=0) | models.Q(real_dollars__isnull=True))
        totals = kpi_qs.aggregate(
            balance=Sum(F('real_dollars') - F('bank_fee_real_usd')),
            income=Sum('real_dollars', filter=models.Q(real_dollars__gt=0)),
            expense=Sum('real_dollars', filter=models.Q(real_dollars__lt=0)),
            fees=Sum('bank_fee_real_usd')
        )
        res_totals = {
            'balance_real_usd': totals['balance'] or 0,
            'income_real_usd': totals['income'] or 0,
            'expense_real_usd': abs(totals['expense'] or 0) + (totals['fees'] or 0),
        }
    else:
        kpi_qs = transactions_list.filter(models.Q(real_dollars=0) | models.Q(real_dollars__isnull=True))
        totals = kpi_qs.aggregate(
            balance_usd=Sum(F('amount_usd') - F('bank_fee_usd')),
            balance_bs=Sum(F('amount_bs') - F('bank_fee_bs')),
            income_usd=Sum('amount_usd', filter=models.Q(amount_usd__gt=0)),
            income_bs=Sum('amount_bs', filter=models.Q(amount_bs__gt=0)),
            expense_usd=Sum('amount_usd', filter=models.Q(amount_usd__lt=0)),
            expense_bs=Sum('amount_bs', filter=models.Q(amount_bs__lt=0)),
            fees_usd=Sum('bank_fee_usd'),
            fees_bs=Sum('bank_fee_bs')
        )
        res_totals = {
            'balance_usd': totals['balance_usd'] or 0,
            'balance_bs': totals['balance_bs'] or 0,
            'income_usd': totals['income_usd'] or 0,
            'income_bs': totals['income_bs'] or 0,
            'expense_usd': abs(totals['expense_usd'] or 0) + (totals['fees_usd'] or 0),
            'expense_bs': abs(totals['expense_bs'] or 0) + (totals['fees_bs'] or 0),
        }

    # --- Saldo pendiente: mismos filtros aplicados (excepto estado), solo transacciones 'pendiente' ---
    has_pending = pending_qs_base.exists()
    if view_mode == 'real':
        pending_kpi_qs = pending_qs_base.exclude(models.Q(real_dollars=0) | models.Q(real_dollars__isnull=True))
        pending_totals_raw = pending_kpi_qs.aggregate(
            balance=Sum(F('real_dollars') - F('bank_fee_real_usd')),
            income=Sum('real_dollars', filter=models.Q(real_dollars__gt=0)),
            expense=Sum('real_dollars', filter=models.Q(real_dollars__lt=0)),
            fees=Sum('bank_fee_real_usd')
        )
        res_totals['pending_balance_real_usd'] = pending_totals_raw['balance'] or 0
        res_totals['pending_income_real_usd'] = pending_totals_raw['income'] or 0
        res_totals['pending_expense_real_usd'] = abs(pending_totals_raw['expense'] or 0) + (pending_totals_raw['fees'] or 0)
    else:
        pending_kpi_qs = pending_qs_base.filter(models.Q(real_dollars=0) | models.Q(real_dollars__isnull=True))
        pending_totals_raw = pending_kpi_qs.aggregate(
            balance_usd=Sum(F('amount_usd') - F('bank_fee_usd')),
            balance_bs=Sum(F('amount_bs') - F('bank_fee_bs')),
            income_usd=Sum('amount_usd', filter=models.Q(amount_usd__gt=0)),
            income_bs=Sum('amount_bs', filter=models.Q(amount_bs__gt=0)),
            expense_usd=Sum('amount_usd', filter=models.Q(amount_usd__lt=0)),
            expense_bs=Sum('amount_bs', filter=models.Q(amount_bs__lt=0)),
            fees_usd=Sum('bank_fee_usd'),
            fees_bs=Sum('bank_fee_bs')
        )
        res_totals['pending_balance_usd'] = pending_totals_raw['balance_usd'] or 0
        res_totals['pending_balance_bs'] = pending_totals_raw['balance_bs'] or 0
        res_totals['pending_income_usd'] = pending_totals_raw['income_usd'] or 0
        res_totals['pending_income_bs'] = pending_totals_raw['income_bs'] or 0
        res_totals['pending_expense_usd'] = abs(pending_totals_raw['expense_usd'] or 0) + (pending_totals_raw['fees_usd'] or 0)
        res_totals['pending_expense_bs'] = abs(pending_totals_raw['expense_bs'] or 0) + (pending_totals_raw['fees_bs'] or 0)
    
    paginator = Paginator(transactions_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    form = TransactionForm(organization=org)

    # Mapeo de proyectos a valuaciones para filtrado dinámico en JS
    projects_data = {}
    projects = Project.objects.filter(organization=org)
    for p in projects:
        projects_data[p.id] = list(Valuation.objects.filter(project=p).values('id', 'name', 'amount_usd'))

    # Mapeo de cuentas a monedas para lógica en JS
    accounts_qs = Account.objects.filter(organization=org)
    accounts_data = {a.id: a.currency for a in accounts_qs}

    bcv_rate = get_bcv_rate()
    categories = Category.objects.filter(organization=org)

    return render(request, 'organizations/transacciones.html', {
        'page_obj': page_obj,
        'form': form,
        'bcv_rate': bcv_rate,
        'categories': categories,
        'cost_centers': CostCenter.objects.filter(organization=org),
        'selected_cost_center': cost_center_id,
        'projects': projects,
        'selected_project': project_id,
        'accounts': accounts_qs,
        'selected_account': account_id,
        'selected_category': category_ids[0] if category_ids else '',
        'selected_categories': category_ids,
        'projects_data': json.dumps(projects_data, cls=DecimalEncoder),
        'accounts_data': json.dumps(accounts_data),
        'filter_type': filter_type,
        'date_from': date_from,
        'date_to': date_to,
        'search': search_query,
        'sort': sort,
        'view_mode': view_mode,
        'tx_filter': tx_filter,
        'status_filter': status_filter,
        'totals': res_totals,
        'has_pending': has_pending,
        'tx_filter_options': [
            ('all', 'Todas las transacciones'),
            ('bcv', 'Transacciones BCV'),
            ('real', 'Transacciones Dólares Reales'),
        ],
        'status_filter_options': [
            ('', 'Todos los estados'),
            ('completado', 'Completado'),
            ('pendiente', 'Pendiente'),
        ],
        'filter_options': [
            ('day', 'Hoy'),
            ('week', 'Esta semana'),
            ('15days', 'Últimos 15 días'),
            ('month', 'Último mes'),
            ('quarter', 'Último trimestre'),
            ('6months', 'Últimos 6 meses'),
            ('year', 'Último año'),
            ('all', 'Todo el tiempo'),
            ('custom', 'Personalizado'),
        ]
    })

@login_required
def _get_report_data(request):
    org_id = request.session.get('org_id')
    org = get_object_or_404(Organization, id=org_id)
    
    report_type = request.GET.get('report_type', 'bcv') # 'bcv' or 'real'
    filter_type = request.GET.get('filter_type', 'all')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    category_raw = request.GET.getlist('category')
    category_ids = []
    for val in category_raw:
        if ',' in val:
            category_ids.extend([v.strip() for v in val.split(',') if v.strip()])
        else:
            category_ids.append(val)
    category_ids = [cid for cid in category_ids if cid and cid != 'None' and cid != 'null']
    cost_center_id = request.GET.get('cost_center')
    search_query = request.GET.get('search', '')
    account_id = request.GET.get('account')
    tx_filter = request.GET.get('tx_filter', 'all')
    project_id = request.GET.get('project')
    selected_org_id = request.GET.get('organization')
    status_filter = request.GET.get('status', '')

    # Sanitizar valores 'None' que pueden venir de la URL
    if date_from == 'None': date_from = None
    if date_to == 'None': date_to = None
    if account_id == 'None' or account_id == '': account_id = None
    if project_id == 'None' or project_id == '': project_id = None
    if selected_org_id == 'None' or selected_org_id == '': selected_org_id = None
    if cost_center_id == 'None' or cost_center_id == '': cost_center_id = None
    
    if project_id:
        # Si filtramos por proyecto, buscamos transacciones de ese proyecto donde la org tenga acceso
        project = get_object_or_404(Project, id=project_id)
        # Verificar acceso: la org debe ser dueña o tener el proyecto compartido, Y el usuario
        # debe tener acceso individual al proyecto (mismo criterio que detalle_proyecto/guardar_transaccion)
        is_owner = project.organization == org
        is_shared = project.shared_organizations.filter(organization=org).exists()
        has_user_access = project.user_accesses.filter(user=request.user).exists()
        if not ((is_owner or is_shared) and has_user_access):
             return org, Transaction.objects.none(), report_type, {}, "Sin Acceso"
         
        transactions = Transaction.objects.filter(project_id=project_id)
        if selected_org_id:
            transactions = transactions.filter(organization_id=selected_org_id)
    else:
        transactions = Transaction.objects.filter(organization=org)

    if account_id:
        transactions = transactions.filter(account_id=account_id)
    
    # Filtrar por tipo de reporte: BCV o Dólares Reales (Filtro base del PDF)
    if report_type == 'real':
        transactions = transactions.exclude(models.Q(real_dollars=0) | models.Q(real_dollars__isnull=True))
    else:
        transactions = transactions.filter(models.Q(real_dollars=0) | models.Q(real_dollars__isnull=True))
    
    # Aplicar tx_filter adicional si viene de la URL (para coincidir con la vista web)
    if tx_filter == 'real' and report_type == 'bcv':
        transactions = transactions.none()
    elif tx_filter == 'bcv' and report_type == 'real':
        transactions = transactions.none()

    if category_ids:
        transactions = transactions.filter(categories__id__in=category_ids).distinct()

    if cost_center_id:
        transactions = transactions.filter(cost_center_id=cost_center_id)
    
    # Filtrar por estado (status)
    if status_filter:
        transactions = transactions.filter(status=status_filter)
    
    if search_query:
        # OJO: el lookup categories__name atraviesa una relación M2M, lo que puede
        # multiplicar filas si la transacción tiene más de una categoría (aparecería
        # duplicada en el reporte). Se aplica distinct() para evitarlo.
        transactions = transactions.filter(
            models.Q(description__icontains=search_query) |
            models.Q(reference_number__icontains=search_query) |
            models.Q(notes__icontains=search_query) |
            models.Q(categories__name__icontains=search_query) |
            models.Q(cost_center__code__icontains=search_query) |
            models.Q(cost_center__name__icontains=search_query) |
            models.Q(account__name__icontains=search_query) |
            models.Q(project__name__icontains=search_query) |
            models.Q(valuation__name__icontains=search_query) |
            models.Q(status__icontains=search_query) |
            models.Q(amount_bs__icontains=search_query) |
            models.Q(amount_usd__icontains=search_query) |
            models.Q(real_dollars__icontains=search_query) |
            models.Q(daily_rate__icontains=search_query)
        ).distinct()
    
    today = timezone.localdate()
    
    filter_parts = []
    if category_ids:
        categories_qs = Category.objects.filter(id__in=category_ids)
        if categories_qs.exists():
            names = ", ".join([c.name for c in categories_qs])
            filter_parts.append(f"Categorías: {names}")

    if cost_center_id:
        cc_filter = CostCenter.objects.filter(id=cost_center_id).first()
        if cc_filter:
            filter_parts.append(f"Centro de Costo: {cc_filter.code} - {cc_filter.name}")

    if selected_org_id:
        org_filter = Organization.objects.filter(id=selected_org_id).first()
        if org_filter:
            filter_parts.append(f"Organización: {org_filter.name}")
    
    if status_filter:
        status_display = status_filter.capitalize()
        filter_parts.append(f"Estado: {status_display}")
            
    if date_from or date_to:
        if date_from:
            transactions = transactions.filter(date__gte=date_from)
        if date_to:
            transactions = transactions.filter(date__lte=date_to)
        
        if date_from and date_to:
            filter_parts.append(f"Rango: {date_from} a {date_to}")
        elif date_from:
            filter_parts.append(f"Desde: {date_from}")
        else:
            filter_parts.append(f"Hasta: {date_to}")
    elif filter_type != 'all' and filter_type != 'custom':
        labels = {
            'day': "Hoy",
            'week': "Última semana",
            '15days': "Últimos 15 días",
            'month': "Último mes",
            'quarter': "Trimestre",
            '6months': "Últimos 6 meses",
            'year': "Último año",
        }
        if filter_type in labels:
            filter_parts.append(labels[filter_type])
            
        if filter_type == 'day':
            start_date = today
        elif filter_type == 'week':
            start_date = today - timedelta(days=7)
        elif filter_type == '15days':
            start_date = today - timedelta(days=15)
        elif filter_type == 'month':
            start_date = today - timedelta(days=30)
        elif filter_type == 'quarter':
            start_date = today - timedelta(days=90)
        elif filter_type == '6months':
            start_date = today - timedelta(days=180)
        elif filter_type == 'year':
            start_date = today - timedelta(days=365)
        transactions = transactions.filter(date__gte=start_date)
        if filter_type == 'day':
            # "Hoy" debe mostrar solo el día de hoy, no fechas futuras.
            transactions = transactions.filter(date__lte=today)

    filter_label = " | ".join(filter_parts) if filter_parts else "Todas"
        
    transactions = transactions.order_by('date', 'id')
    
    report_totals = transactions.aggregate(
        total_usd=Sum(F('amount_usd') - F('bank_fee_usd')),
        total_bs=Sum(F('amount_bs') - F('bank_fee_bs')),
        total_real_usd=Sum(F('real_dollars') - F('bank_fee_real_usd'))
    )
    
    return org, transactions, report_type, report_totals, filter_label

@login_required
def exportar_pdf_transacciones(request):
    org, transactions, report_type, report_totals, filter_label = _get_report_data(request)
    now = timezone.now()
    
    # --- Generación de PDF con ReportLab ---
    response = HttpResponse(content_type='application/pdf')
    filename = f"balance_general_{org.name}_{now.strftime('%Y%m%d')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter),
                            rightMargin=1.5*cm, leftMargin=1.5*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm,
                            title=f"Balance General - {org.name}")
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Estilos personalizados
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor("#0d6efd"),
        alignment=TA_CENTER,
        spaceAfter=10
    )
    
    info_style = ParagraphStyle(
        'InfoStyle',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_CENTER,
        spaceAfter=5
    )
    
    filter_style = ParagraphStyle(
        'FilterStyle',
        parent=styles['Normal'],
        fontSize=9,
        spaceAfter=10
    )
    
    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontSize=8,
        leading=10
    )
    
    header_cell_style = ParagraphStyle(
        'HeaderCellStyle',
        parent=styles['Normal'],
        fontSize=9,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor("#444444")
    )
    
    # Header
    elements.append(Paragraph("Balance General", title_style))
    elements.append(Paragraph(f"<b>Organización:</b> {org.name}", info_style))
    elements.append(Paragraph(f"<b>Generado el:</b> {now.strftime('%d/%m/%Y %H:%M')}", info_style))
    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph(f"<b>Filtro aplicado:</b> {filter_label}", filter_style))
    elements.append(Spacer(1, 0.5*cm))

    # Datos de la tabla
    if report_type == 'real':
        header = [
            Paragraph("Fecha", header_cell_style),
            Paragraph("Descripción", header_cell_style),
            Paragraph("Referencia", header_cell_style),
            Paragraph("Monto (Dólares)", header_cell_style),
            Paragraph("Notas", header_cell_style),
            Paragraph("Estado", header_cell_style)
        ]
        data = [header]
        for trans in transactions:
            data.append([
                trans.date.strftime("%d/%m/%Y"),
                Paragraph(trans.description or "", cell_style),
                trans.reference_number or "---",
                f"{trans.real_dollars or 0:,.2f} $",
                Paragraph(trans.notes or "", cell_style),
                trans.get_status_display()
            ])

        if transactions:
            data.append(["", "BALANCE TOTAL:", "", f"{report_totals['total_real_usd'] or 0:,.2f} $", "", ""])

        col_widths = [2.5*cm, 7.5*cm, 3.0*cm, 4.0*cm, 5.0*cm, 2.5*cm]
        estado_col = 5
    else:
        header = [
            Paragraph("Fecha", header_cell_style),
            Paragraph("Descripción", header_cell_style),
            Paragraph("Referencia", header_cell_style),
            Paragraph("Monto (BS)", header_cell_style),
            Paragraph("Tasa", header_cell_style),
            Paragraph("Monto (USD)", header_cell_style),
            Paragraph("Notas", header_cell_style),
            Paragraph("Estado", header_cell_style)
        ]
        data = [header]
        for trans in transactions:
            data.append([
                trans.date.strftime("%d/%m/%Y"),
                Paragraph(trans.description or "", cell_style),
                trans.reference_number or "---",
                f"{trans.amount_bs:,.2f}",
                f"{trans.daily_rate:,.4f}",
                f"{trans.amount_usd:,.2f}",
                Paragraph(trans.notes or "", cell_style),
                trans.get_status_display()
            ])

        if transactions:
            data.append([
                "", "", "BALANCE TOTAL:",
                f"{report_totals['total_bs'] or 0:,.2f} Bs.",
                "",
                f"{report_totals['total_usd'] or 0:,.2f} $",
                "",
                ""
            ])

        col_widths = [2.2*cm, 4.8*cm, 2.5*cm, 3.2*cm, 2.2*cm, 3.2*cm, 4.7*cm, 2.4*cm]
        estado_col = 7
    
    table = Table(data, colWidths=col_widths, repeatRows=1)
    
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f8f9fa")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (3, 1), (3, -1), 'RIGHT'), # Monto BS
        ('ALIGN', (4, 1), (4, -1), 'RIGHT'), # Tasa
        ('ALIGN', (5, 1), (5, -1), 'RIGHT'), # Monto USD
        ('FONTSIZE', (0, 1), (-1, -1), 8),
    ])
    
    # Colores condicionales y negritas
    for i, trans in enumerate(transactions):
        idx = i + 1
        if report_type == 'real':
            # Monto USD Real
            if trans.real_dollars < 0:
                table_style.add('TEXTCOLOR', (3, idx), (3, idx), colors.HexColor("#dc3545"))
            else:
                table_style.add('TEXTCOLOR', (3, idx), (3, idx), colors.HexColor("#198754"))
            table_style.add('FONTNAME', (3, idx), (3, idx), 'Helvetica-Bold')
        else:
            # Monto BS
            if trans.amount_bs < 0:
                table_style.add('TEXTCOLOR', (3, idx), (3, idx), colors.HexColor("#dc3545"))
            else:
                table_style.add('TEXTCOLOR', (3, idx), (3, idx), colors.HexColor("#198754"))
            table_style.add('FONTNAME', (3, idx), (3, idx), 'Helvetica-Bold')
            
            # Monto USD (BCV)
            if trans.amount_usd < 0:
                table_style.add('TEXTCOLOR', (5, idx), (5, idx), colors.HexColor("#dc3545"))
            else:
                table_style.add('TEXTCOLOR', (5, idx), (5, idx), colors.HexColor("#198754"))
            table_style.add('FONTNAME', (5, idx), (5, idx), 'Helvetica-Bold')

        # Estado
        estado_color = "#198754" if trans.status == 'completado' else "#fd7e14"
        table_style.add('TEXTCOLOR', (estado_col, idx), (estado_col, idx), colors.HexColor(estado_color))
        table_style.add('FONTNAME', (estado_col, idx), (estado_col, idx), 'Helvetica-Bold')

    # Estilo de la última fila (Balance)
    if transactions:
        last_row = len(data) - 1
        table_style.add('BACKGROUND', (0, last_row), (-1, last_row), colors.HexColor("#f1f1f1"))
        table_style.add('FONTNAME', (0, last_row), (-1, last_row), 'Helvetica-Bold')
        table_style.add('ALIGN', (2, last_row), (2, last_row), 'RIGHT')
        
        if report_type == 'real':
            total_real = report_totals['total_real_usd'] or 0
            if total_real < 0:
                table_style.add('TEXTCOLOR', (3, last_row), (3, last_row), colors.HexColor("#dc3545"))
            else:
                table_style.add('TEXTCOLOR', (3, last_row), (3, last_row), colors.HexColor("#198754"))
        else:
            total_bs = report_totals['total_bs'] or 0
            if total_bs < 0:
                table_style.add('TEXTCOLOR', (3, last_row), (3, last_row), colors.HexColor("#dc3545"))
            else:
                table_style.add('TEXTCOLOR', (3, last_row), (3, last_row), colors.HexColor("#198754"))
                
            total_usd = report_totals['total_usd'] or 0
            if total_usd < 0:
                table_style.add('TEXTCOLOR', (5, last_row), (5, last_row), colors.HexColor("#dc3545"))
            else:
                table_style.add('TEXTCOLOR', (5, last_row), (5, last_row), colors.HexColor("#198754"))

    table.setStyle(table_style)
    elements.append(table)
    elements.append(Spacer(1, 1*cm))

    # --- Resumen Gráfico ---
    cd = get_chart_data(transactions, mode=report_type, json_format=False)
    
    if transactions.exists():
        chart_elements = []
        
        # a) Gastos por Categoría (Pie)
        if cd['cat_series']:
            d1 = Drawing(8*cm, 6*cm)
            pc = Pie()
            pc.x = 1.5*cm
            pc.y = 0.5*cm
            pc.width = 4.5*cm
            pc.height = 4.5*cm
            pc.data = cd['cat_series']
            pc.labels = cd['cat_labels']
            pc.sideLabels = 1
            pc.slices.fontSize = 7
            for i, color in enumerate(cd['cat_colors']):
                pc.slices[i].fillColor = colors.HexColor(color)
            d1.add(pc)
            d1.add(String(4*cm, 5.5*cm, "Gastos por Categoría", textAnchor='middle', fontName='Helvetica-Bold', fontSize=10))
            chart_elements.append(d1)
        else:
            chart_elements.append(Paragraph("No hay datos de gastos por categoría", cell_style))

        # b) Ingresos vs Gastos (Bar)
        d2 = Drawing(8*cm, 6*cm)
        bc = VerticalBarChart()
        bc.x = 1*cm
        bc.y = 1*cm
        bc.width = 6*cm
        bc.height = 4*cm
        bc.data = [[cd['total_income']], [cd['total_expense']]]
        bc.categoryAxis.categoryNames = ['Balance']
        bc.bars[0].fillColor = colors.green # Ingresos
        bc.bars[1].fillColor = colors.red   # Gastos
        bc.valueAxis.valueMin = 0
        bc.valueAxis.labels.fontSize = 7
        d2.add(bc)
        # Leyenda simple manual para el gráfico de barras
        d2.add(String(1*cm, 0.2*cm, "Verde: Ingresos", fontSize=7, fillColor=colors.green))
        d2.add(String(4*cm, 0.2*cm, "Rojo: Gastos", fontSize=7, fillColor=colors.red))
        d2.add(String(4*cm, 5.5*cm, "Ingresos vs Gastos", textAnchor='middle', fontName='Helvetica-Bold', fontSize=10))
        chart_elements.append(d2)

        # c) Evolución del Saldo (Line)
        if cd['evo_series']:
            d3 = Drawing(9*cm, 6*cm)
            lc = HorizontalLineChart()
            lc.x = 1*cm
            lc.y = 1.2*cm
            lc.width = 7.5*cm
            lc.height = 3.8*cm
            lc.data = [cd['evo_series']]
            # Limitar etiquetas de fecha si hay demasiadas
            if len(cd['evo_labels']) > 10:
                step = len(cd['evo_labels']) // 10
                lc.categoryAxis.categoryNames = [label if i % step == 0 else '' for i, label in enumerate(cd['evo_labels'])]
            else:
                lc.categoryAxis.categoryNames = cd['evo_labels']
            
            lc.categoryAxis.labels.fontSize = 6
            lc.categoryAxis.labels.angle = 45
            lc.categoryAxis.labels.boxAnchor = 'ne'
            lc.valueAxis.labels.fontSize = 7
            
            # Ajustar rango del eje Y
            all_vals = cd['evo_series'] + [0]
            lc.valueAxis.valueMin = min(all_vals) * 1.1 if min(all_vals) < 0 else 0
            lc.valueAxis.valueMax = max(all_vals) * 1.1 if max(all_vals) > 0 else 10
            
            d3.add(lc)
            d3.add(String(4.5*cm, 5.5*cm, "Evolución del Saldo", textAnchor='middle', fontName='Helvetica-Bold', fontSize=10))
            chart_elements.append(d3)
        else:
            chart_elements.append(Paragraph("No hay datos de evolución", cell_style))

        # Organizar gráficos en una tabla
        charts_table = Table([chart_elements], colWidths=[8.5*cm, 8.5*cm, 9*cm])
        charts_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        elements.append(charts_table)
        elements.append(Spacer(1, 0.5*cm))

    
    # Footer
    footer_style = ParagraphStyle(
        'FooterStyle',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_RIGHT,
        spaceBefore=20
    )
    elements.append(Paragraph("Este documento es un reporte automático generado por Control de Gastos.", footer_style))
    
    doc.build(elements)
    response.write(buffer.getvalue())
    buffer.close()
    return response


@login_required
def exportar_xlsx_transacciones(request):
    org, transactions, report_type, report_totals, filter_label = _get_report_data(request)
    now = timezone.now()

    filename = f"balance_general_{org.name}_{now.strftime('%Y%m%d')}.xlsx"

    TITLE_FILL = PatternFill('solid', fgColor='0D6EFD')
    HEADER_FILL = PatternFill('solid', fgColor='F8F9FA')
    TOTAL_FILL = PatternFill('solid', fgColor='F1F1F1')
    THIN_BORDER = Border(*(Side(style='thin', color='DEE2E6'),) * 4)
    POS_FONT = Font(color='198754', bold=True)
    NEG_FONT = Font(color='DC3545', bold=True)

    wb = Workbook()
    ws = wb.active
    ws.title = 'Balance General'

    is_real = report_type == 'real'
    base_cols = 5 if is_real else 7  # columnas del reporte original (sin tocar)
    amount_col = 4 if is_real else 6  # columna usada como fuente de los gráficos (Monto Dólares / Monto USD)
    n_cols = base_cols + 3  # + Estado, Categoría, Saldo Acumulado

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n_cols)
    title_cell = ws.cell(row=1, column=1, value=f"Balance {'Dólares Reales' if is_real else 'BCV'}")
    title_cell.font = Font(size=16, bold=True, color='FFFFFF')
    title_cell.alignment = Alignment(horizontal='center')
    title_cell.fill = TITLE_FILL
    ws.row_dimensions[1].height = 24

    info_rows = [
        f"Organización: {org.name}",
        f"Generado el: {now.strftime('%d/%m/%Y %H:%M')}",
        f"Filtro aplicado: {filter_label}",
    ]
    for i, text in enumerate(info_rows, start=2):
        ws.merge_cells(start_row=i, start_column=1, end_row=i, end_column=n_cols)
        cell = ws.cell(row=i, column=1, value=text)
        cell.alignment = Alignment(horizontal='center')

    header_row = 6
    if is_real:
        headers = ['Fecha', 'Descripción', 'Referencia', 'Monto (Dólares)', 'Notas']
    else:
        headers = ['Fecha', 'Descripción', 'Referencia', 'Monto (BS)', 'Tasa', 'Monto (USD)', 'Notas']
    headers += ['Estado', 'Categoría', 'Saldo Acumulado']

    for col, text in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=col, value=text)
        cell.font = Font(bold=True, color='444444')
        cell.fill = HEADER_FILL
        cell.border = THIN_BORDER

    first_data_row = header_row + 1
    row = first_data_row
    transactions = transactions.prefetch_related('categories')
    amount_col_letter = get_column_letter(amount_col)
    for trans in transactions:
        col = 1
        date_cell = ws.cell(row=row, column=col, value=trans.date)
        date_cell.number_format = 'DD/MM/YYYY'
        date_cell.border = THIN_BORDER
        col += 1

        ws.cell(row=row, column=col, value=trans.description or '').border = THIN_BORDER
        col += 1
        ws.cell(row=row, column=col, value=trans.reference_number or '---').border = THIN_BORDER
        col += 1

        if is_real:
            amount = float(trans.real_dollars or 0)
            amount_cell = ws.cell(row=row, column=col, value=amount)
            amount_cell.number_format = '#,##0.00 "$"'
            amount_cell.font = NEG_FONT if amount < 0 else POS_FONT
            amount_cell.border = THIN_BORDER
            col += 1
            ws.cell(row=row, column=col, value=trans.notes or '').border = THIN_BORDER
            col += 1
        else:
            amount_bs = float(trans.amount_bs or 0)
            bs_cell = ws.cell(row=row, column=col, value=amount_bs)
            bs_cell.number_format = '#,##0.00'
            bs_cell.font = NEG_FONT if amount_bs < 0 else POS_FONT
            bs_cell.border = THIN_BORDER
            col += 1

            rate_cell = ws.cell(row=row, column=col, value=float(trans.daily_rate or 0))
            rate_cell.number_format = '#,##0.0000'
            rate_cell.border = THIN_BORDER
            col += 1

            amount_usd = float(trans.amount_usd or 0)
            usd_cell = ws.cell(row=row, column=col, value=amount_usd)
            usd_cell.number_format = '#,##0.00'
            usd_cell.font = NEG_FONT if amount_usd < 0 else POS_FONT
            usd_cell.border = THIN_BORDER
            col += 1

            ws.cell(row=row, column=col, value=trans.notes or '').border = THIN_BORDER
            col += 1

        estado_cell = ws.cell(row=row, column=col, value=trans.get_status_display())
        estado_cell.border = THIN_BORDER
        estado_cell.font = POS_FONT if trans.status == 'completado' else Font(color='FD7E14', bold=True)
        col += 1

        category_names = ', '.join(c.name for c in trans.categories.all()) or 'Sin categoría'
        ws.cell(row=row, column=col, value=category_names).border = THIN_BORDER
        col += 1

        saldo_cell = ws.cell(
            row=row, column=col,
            value=f'=SUM(${amount_col_letter}${first_data_row}:{amount_col_letter}{row})',
        )
        saldo_cell.number_format = '#,##0.00 "$"'
        saldo_cell.border = THIN_BORDER

        row += 1
    last_data_row = row - 1

    if transactions:
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=3)
        label_cell = ws.cell(row=row, column=2, value='BALANCE TOTAL:')
        label_cell.alignment = Alignment(horizontal='right')
        for col in range(1, n_cols + 1):
            ws.cell(row=row, column=col).fill = TOTAL_FILL
            ws.cell(row=row, column=col).border = THIN_BORDER
            ws.cell(row=row, column=col).font = Font(bold=True)

        if is_real:
            total = float(report_totals.get('total_real_usd') or 0)
            total_cell = ws.cell(row=row, column=4, value=total)
            total_cell.number_format = '#,##0.00 "$"'
            total_cell.font = Font(bold=True, color='DC3545' if total < 0 else '198754')
        else:
            total_bs = float(report_totals.get('total_bs') or 0)
            bs_cell = ws.cell(row=row, column=4, value=total_bs)
            bs_cell.number_format = '#,##0.00'
            bs_cell.font = Font(bold=True, color='DC3545' if total_bs < 0 else '198754')

            total_usd = float(report_totals.get('total_usd') or 0)
            usd_cell = ws.cell(row=row, column=6, value=total_usd)
            usd_cell.number_format = '#,##0.00 "$"'
            usd_cell.font = Font(bold=True, color='DC3545' if total_usd < 0 else '198754')
        row += 1

    column_widths = [12, 30, 16, 16, 12, 16, 30] if not is_real else [12, 34, 16, 18, 34]
    column_widths += [14, 22, 18]
    for i, width in enumerate(column_widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)

    if transactions.exists():
        _build_charts_sheet(
            wb, ws, transactions, report_type,
            amount_col=amount_col, categoria_col=base_cols + 2, saldo_col=base_cols + 3,
            header_row=header_row, first_data_row=first_data_row, last_data_row=last_data_row,
        )

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _build_charts_sheet(wb, ws, transactions, report_type, amount_col, categoria_col, saldo_col,
                         header_row, first_data_row, last_data_row):
    # cat_labels/cat_colors solo indican qué categorías existen y su color;
    # los montos de los gráficos se calculan con fórmulas que leen la tabla.
    cd = get_chart_data(transactions, mode=report_type, json_format=False)
    cs = wb.create_sheet('Gráficos')

    sheet_ref = f"'{ws.title}'"
    amount_letter = get_column_letter(amount_col)
    categoria_letter = get_column_letter(categoria_col)
    amount_range = f'{sheet_ref}!${amount_letter}${first_data_row}:${amount_letter}${last_data_row}'
    categoria_range = f'{sheet_ref}!${categoria_letter}${first_data_row}:${categoria_letter}${last_data_row}'

    anchor_row = 1

    max_data_row = anchor_row + 2  # bloque de Ingresos vs Gastos siempre ocupa hasta aquí
    if cd['cat_labels']:
        max_data_row = max(max_data_row, anchor_row + len(cd['cat_labels']))
    chart_row = max_data_row + 3

    if cd['cat_labels']:
        cs.cell(row=anchor_row, column=1, value='Categoría')
        cs.cell(row=anchor_row, column=2, value='Gasto (USD)')
        for i, label in enumerate(cd['cat_labels'], start=1):
            safe_label = label.replace('"', '""')
            cs.cell(row=anchor_row + i, column=1, value=label)
            cs.cell(row=anchor_row + i, column=2,
                    value=f'=ABS(SUMIFS({amount_range},{categoria_range},"*{safe_label}*",{amount_range},"<0"))')
        n = len(cd['cat_labels'])

        pie = PieChart()
        pie.title = 'Gastos por Categoría'
        data = Reference(cs, min_col=2, min_row=anchor_row, max_row=anchor_row + n)
        cats = Reference(cs, min_col=1, min_row=anchor_row + 1, max_row=anchor_row + n)
        pie.add_data(data, titles_from_data=True)
        pie.set_categories(cats)
        pie.varyColors = True
        pie.series[0].data_points = [
            DataPoint(idx=i, spPr=GraphicalProperties(solidFill=(color or '#000000').lstrip('#')))
            for i, color in enumerate(cd['cat_colors'])
        ]
        pie.height = 9
        pie.width = 11
        cs.add_chart(pie, f'{get_column_letter(2)}{chart_row}')

    cs.cell(row=anchor_row, column=4 + 6, value='Tipo')
    cs.cell(row=anchor_row, column=5 + 6, value='Monto (USD)')
    cs.cell(row=anchor_row + 1, column=4 + 6, value='Ingresos')
    cs.cell(row=anchor_row + 1, column=5 + 6, value=f'=SUMIF({amount_range},">0")')
    cs.cell(row=anchor_row + 2, column=4 + 6, value='Gastos')
    cs.cell(row=anchor_row + 2, column=5 + 6, value=f'=ABS(SUMIF({amount_range},"<0"))')

    bar = BarChart()
    bar.type = 'col'
    bar.title = 'Ingresos vs Gastos'
    bar_data = Reference(cs, min_col=11, min_row=anchor_row, max_row=anchor_row + 2)
    bar_cats = Reference(cs, min_col=10, min_row=anchor_row + 1, max_row=anchor_row + 2)
    bar.add_data(bar_data, titles_from_data=True)
    bar.set_categories(bar_cats)
    bar.series[0].data_points = [
        DataPoint(idx=0, spPr=GraphicalProperties(solidFill='198754')),  # Ingresos: verde
        DataPoint(idx=1, spPr=GraphicalProperties(solidFill='DC3545')),  # Gastos: rojo
    ]
    bar.legend = None
    bar.height = 9
    bar.width = 11
    cs.add_chart(bar, f'{get_column_letter(10)}{chart_row}')

    # Evolución del saldo: se lee directamente de las columnas Fecha y Saldo
    # Acumulado de la tabla de transacciones, sin ningún bloque auxiliar.
    line = LineChart()
    line.title = 'Evolución del Saldo'
    line_data = Reference(ws, min_col=saldo_col, min_row=header_row, max_row=last_data_row)
    line_cats = Reference(ws, min_col=1, min_row=first_data_row, max_row=last_data_row)
    line.add_data(line_data, titles_from_data=True)
    line.set_categories(line_cats)
    line.height = 9
    line.width = 11
    cs.add_chart(line, f'{get_column_letter(18)}{chart_row}')


def _safe_next_url(request, default):
    """Valida el parámetro 'next' (POST) para evitar open-redirects; si no es un destino local válido, usa default."""
    next_url = request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return default

@login_required
@viewer_restricted
def guardar_transaccion(request, trans_id=None):
    org_id = request.session.get('org_id')
    if not org_id:
        return redirect('dashboard')
    
    org = get_object_or_404(Organization, id=org_id)
    instance = None
    if trans_id:
        # Si es edición, buscamos la transacción original.
        # Se permite si el usuario tiene acceso a la organización de la transacción
        # O si la transacción pertenece a un proyecto al que la organización actual tiene acceso.
        projects_with_access = Project.objects.filter(
            models.Q(organization=org) | models.Q(shared_organizations__organization=org),
            user_accesses__user=request.user
        )
        
        transactions_with_access = Transaction.objects.filter(
            models.Q(organization=org) |
            models.Q(project__in=projects_with_access)
        ).distinct()
        
        transaction_to_edit = get_object_or_404(transactions_with_access, id=trans_id)
        instance = transaction_to_edit
    
    redirect_to = _safe_next_url(request, 'lista_transacciones')

    if request.method == 'POST':
        debug_event(
            "transaccion.guardar.intento",
            user_id=request.user.id,
            org_id=org.id,
            trans_id=trans_id,
            is_update=bool(instance),
        )
        # Si viene de un proyecto, necesitamos pasar el proyecto al formulario
        proj_id = request.POST.get('project')
        project_context = None
        if proj_id:
            project_context = get_object_or_404(Project, id=proj_id)
            # Verificar acceso al proyecto (dueño o compartido) Y acceso individual del usuario
            projects_owned = Project.objects.filter(organization=org)
            projects_shared = Project.objects.filter(shared_organizations__organization=org)
            if not (projects_owned | projects_shared).filter(id=proj_id, user_accesses__user=request.user).exists():
                debug_event(
                    "transaccion.guardar.acceso_denegado",
                    user_id=request.user.id,
                    org_id=org.id,
                    project_id=proj_id,
                )
                messages.error(
                    request,
                    "No tiene acceso a este proyecto: la organización actual no es propietaria del "
                    "proyecto ni lo tiene compartido con ella."
                )
                return redirect(redirect_to)

        form = TransactionForm(request.POST, instance=instance, organization=org, project=project_context)
        if form.is_valid():
            is_update = bool(instance)
            transaction = form.save()
            log_transaction_audit(
                transaction,
                transaction.organization,
                TransactionAuditLog.ACTION_UPDATED if is_update else TransactionAuditLog.ACTION_CREATED,
                request.user,
            )
            debug_event(
                "transaccion.guardada",
                user_id=request.user.id,
                org_id=org.id,
                transaction_id=transaction.id,
                account_id=transaction.account_id,
                amount_bs=transaction.amount_bs,
                amount_usd=transaction.amount_usd,
                is_update=is_update,
            )
            messages.success(request, "Transacción guardada correctamente.")
        else:
            debug_event(
                "transaccion.guardar.error",
                user_id=request.user.id,
                org_id=org.id,
                trans_id=trans_id,
                errors=form.errors.get_json_data(),
            )
            messages.error(request, f"Error al guardar la transacción: {first_form_error(form)}")

    return redirect(redirect_to)

@login_required
@viewer_restricted
def eliminar_transaccion(request, trans_id):
    org_id = request.session.get('org_id')
    if not org_id:
        return redirect('dashboard')
    
    org = get_object_or_404(Organization, id=org_id)
    
    # Verificar acceso: Directo a la org O via proyecto compartido
    projects_with_access = Project.objects.filter(
        models.Q(organization=org) | models.Q(shared_organizations__organization=org),
        user_accesses__user=request.user
    )
    
    transactions_with_access = Transaction.objects.filter(
        models.Q(organization=org) |
        models.Q(project__in=projects_with_access)
    ).distinct()
    
    transaction = get_object_or_404(transactions_with_access, id=trans_id)

    next_url = request.GET.get('next')
    redirect_to = next_url if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ) else 'lista_transacciones'

    if request.method == 'POST':
        log_transaction_audit(transaction, transaction.organization, TransactionAuditLog.ACTION_DELETED, request.user)
        transaction.delete()
        messages.success(request, "Transacción eliminada.")
    
    return redirect(redirect_to)

@login_required
def detalle_transaccion(request, trans_id):
    org_id = request.session.get('org_id')
    if not org_id:
        return redirect('dashboard')
        
    org = get_object_or_404(Organization, id=org_id)
    
    # Verificar acceso: Directo a la org O via proyecto compartido
    projects_with_access = Project.objects.filter(
        models.Q(organization=org) | models.Q(shared_organizations__organization=org),
        user_accesses__user=request.user
    )
    
    transactions_with_access = Transaction.objects.filter(
        models.Q(organization=org) |
        models.Q(project__in=projects_with_access)
    ).distinct()
    
    transaction = get_object_or_404(transactions_with_access, id=trans_id)

    created_log = transaction.audit_logs.filter(action=TransactionAuditLog.ACTION_CREATED).order_by('timestamp').first()
    last_updated_log = transaction.audit_logs.filter(action=TransactionAuditLog.ACTION_UPDATED).order_by('-timestamp').first()

    return render(request, 'organizations/partials/detalle_transaccion.html', {
        'transaction': transaction,
        'created_log': created_log,
        'last_updated_log': last_updated_log,
    })

# --- Categorías ---

@login_required
def lista_categorias(request):
    org_id = request.session.get('org_id')
    if not org_id:
        return redirect('dashboard')
    
    org = get_object_or_404(Organization, id=org_id)
    categories = Category.objects.filter(organization=org).order_by('name')
    form = CategoryForm()
    
    return render(request, 'organizations/categorias.html', {
        'categories': categories,
        'form': form,
    })

@login_required
@viewer_restricted
def guardar_categoria(request, cat_id=None):
    org_id = request.session.get('org_id')
    if not org_id:
        return redirect('dashboard')
    
    org = get_object_or_404(Organization, id=org_id)
    instance = None
    if cat_id:
        instance = get_object_or_404(Category, id=cat_id, organization=org)
    
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=instance)
        if form.is_valid():
            category = form.save(commit=False)
            category.organization = org
            category.save()
            messages.success(request, "Categoría guardada correctamente.")
        else:
            messages.error(request, f"Error al guardar la categoría: {first_form_error(form)}")
            
    return redirect('lista_categorias')

@login_required
@viewer_restricted
def eliminar_categoria(request, cat_id):
    org_id = request.session.get('org_id')
    if not org_id:
        return redirect('dashboard')
    
    org = get_object_or_404(Organization, id=org_id)
    category = get_object_or_404(Category, id=cat_id, organization=org)
    
    if request.method == 'POST':
        category.delete()
        messages.success(request, "Categoría eliminada.")
    
    return redirect('lista_categorias')

# --- Cuentas ---

@login_required
def lista_cuentas(request):
    org_id = request.session.get('org_id')
    if not org_id:
        return redirect('dashboard')
    
    org = get_object_or_404(Organization, id=org_id)
    accounts = Account.objects.filter(organization=org).annotate(
        balance_usd=Sum(F('transactions__amount_usd') - F('transactions__bank_fee_usd')),
        balance_bs=Sum(F('transactions__amount_bs') - F('transactions__bank_fee_bs')),
        balance_real_usd=Sum(F('transactions__real_dollars') - F('transactions__bank_fee_real_usd'))
    )
    
    form = AccountForm()

    bcv_rate = get_bcv_rate()

    accounts_json = json.dumps([
        {
            'id': acc.id,
            'currency': acc.currency,
            'bank_code': acc.bank_code,
            'bank_name': acc.bank_name,
            'rif': acc.rif,
            'account_number': acc.account_number,
            'holder': acc.holder,
        }
        for acc in accounts
    ])

    return render(request, 'organizations/cuentas.html', {
        'accounts': accounts,
        'accounts_json': accounts_json,
        'form': form,
        'bcv_rate': bcv_rate,
    })

@login_required
@viewer_restricted
def guardar_cuenta(request, acc_id=None):
    org_id = request.session.get('org_id')
    if not org_id:
        return redirect('dashboard')
    
    org = get_object_or_404(Organization, id=org_id)
    instance = None
    if acc_id:
        instance = get_object_or_404(Account, id=acc_id, organization=org)
    
    if request.method == 'POST':
        debug_event(
            "cuenta.guardar.intento",
            user_id=request.user.id,
            username=request.user.username,
            org_id=org.id,
            acc_id=acc_id,
            is_update=bool(instance),
            is_superuser=request.user.is_superuser,
        )
        form = AccountForm(request.POST, instance=instance)
        if form.is_valid():
            account = form.save(commit=False)
            account.organization = org
            # account.name is already handled by the form.save() or cleaned_data
            account.save()

            if not instance:
                balance = form.cleaned_data.get('initial_balance') or 0
                rate = form.cleaned_data.get('daily_rate') or get_bcv_rate()
                initial_tx = create_initial_balance_transaction(
                    organization=org,
                    account=account,
                    balance=balance,
                    daily_rate=rate,
                    created_by=request.user,
                )
                if initial_tx:
                    debug_event(
                        "cuenta.saldo_inicial_transaccion_creada",
                        user_id=request.user.id,
                        org_id=org.id,
                        account_id=account.id,
                        currency=account.currency,
                        amount_bs=initial_tx.amount_bs,
                        amount_usd=initial_tx.amount_usd,
                        daily_rate=rate,
                    )
            debug_event(
                "cuenta.guardada",
                user_id=request.user.id,
                org_id=org.id,
                account_id=account.id,
                currency=account.currency,
                bank_code=account.bank_code,
                bank_name=account.bank_name,
                is_update=bool(instance),
            )
            messages.success(request, "Cuenta guardada correctamente.")
        else:
            debug_event(
                "cuenta.guardar.error",
                user_id=request.user.id,
                username=request.user.username,
                org_id=org.id,
                acc_id=acc_id,
                is_superuser=request.user.is_superuser,
                errors=form.errors.get_json_data(),
            )
            messages.error(request, f"Error al guardar la cuenta: {first_form_error(form)}")
            
    return redirect('lista_cuentas')

@login_required
@viewer_restricted
def eliminar_cuenta(request, acc_id):
    org_id = request.session.get('org_id')
    if not org_id:
        return redirect('dashboard')
    
    org = get_object_or_404(Organization, id=org_id)
    account = get_object_or_404(Account, id=acc_id, organization=org)
    
    if request.method == 'POST':
        account.delete()
        messages.success(request, "Cuenta eliminada.")
    
    return redirect('lista_cuentas')

@login_required
def detalle_cuenta(request, acc_id):
    org_id = request.session.get('org_id')
    if not org_id:
        return redirect('dashboard')
    
    org = get_object_or_404(Organization, id=org_id)
    account = get_object_or_404(Account, id=acc_id, organization=org)
    
    # --- Lógica de Filtrado ---
    filter_type = request.GET.get('filter_type', 'all')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    category_raw = request.GET.getlist('category')
    category_ids = []
    for val in category_raw:
        if ',' in val:
            category_ids.extend([v.strip() for v in val.split(',') if v.strip()])
        else:
            category_ids.append(val)
    category_ids = [cid for cid in category_ids if cid and cid != 'None' and cid != 'null']
    search_query = request.GET.get('search', '')
    cost_center_id = request.GET.get('cost_center')
    project_id = request.GET.get('project')
    status_filter = request.GET.get('status', '')

    if date_from == 'None': date_from = None
    if date_to == 'None': date_to = None
    if cost_center_id == 'None' or cost_center_id == '': cost_center_id = None
    if project_id == 'None' or project_id == '': project_id = None

    transactions_list = Transaction.objects.filter(account=account)

    if search_query:
        # OJO: el lookup categories__name atraviesa una relación M2M, lo que puede
        # multiplicar filas si la transacción tiene más de una categoría (aparecería
        # duplicada en la tabla y en los KPIs). Se aplica distinct() para evitarlo.
        transactions_list = transactions_list.filter(
            models.Q(description__icontains=search_query) |
            models.Q(reference_number__icontains=search_query) |
            models.Q(notes__icontains=search_query) |
            models.Q(categories__name__icontains=search_query) |
            models.Q(cost_center__code__icontains=search_query) |
            models.Q(cost_center__name__icontains=search_query) |
            models.Q(project__name__icontains=search_query) |
            models.Q(valuation__name__icontains=search_query) |
            models.Q(status__icontains=search_query) |
            models.Q(amount_bs__icontains=search_query) |
            models.Q(amount_usd__icontains=search_query) |
            models.Q(real_dollars__icontains=search_query) |
            models.Q(daily_rate__icontains=search_query)
        ).distinct()

    if category_ids:
        transactions_list = transactions_list.filter(categories__id__in=category_ids).distinct()

    if cost_center_id:
        transactions_list = transactions_list.filter(cost_center_id=cost_center_id)

    if project_id:
        transactions_list = transactions_list.filter(project_id=project_id)

    if status_filter:
        transactions_list = transactions_list.filter(status=status_filter)

    today = timezone.localdate()
    
    if date_from or date_to:
        if date_from:
            transactions_list = transactions_list.filter(date__gte=date_from)
        if date_to:
            transactions_list = transactions_list.filter(date__lte=date_to)
    elif filter_type != 'all' and filter_type != 'custom':
        if filter_type == 'day':
            start_date = today
        elif filter_type == 'week':
            start_date = today - timedelta(days=7)
        elif filter_type == '15days':
            start_date = today - timedelta(days=15)
        elif filter_type == 'month':
            start_date = today - timedelta(days=30)
        elif filter_type == 'quarter':
            start_date = today - timedelta(days=90)
        elif filter_type == '6months':
            start_date = today - timedelta(days=180)
        elif filter_type == 'year':
            start_date = today - timedelta(days=365)
        transactions_list = transactions_list.filter(date__gte=start_date)
        if filter_type == 'day':
            # "Hoy" debe mostrar solo el día de hoy, no fechas futuras.
            transactions_list = transactions_list.filter(date__lte=today)

    sort = request.GET.get('sort', 'desc')
    if sort == 'asc':
        transactions_list = transactions_list.order_by('date', 'id')
    else:
        transactions_list = transactions_list.order_by('-date', '-id')
    
    totals = transactions_list.aggregate(
        balance_usd=Sum(F('amount_usd') - F('bank_fee_usd')),
        balance_bs=Sum(F('amount_bs') - F('bank_fee_bs')),
        balance_real_usd=Sum(F('real_dollars') - F('bank_fee_real_usd')),
        income_usd=Sum('amount_usd', filter=models.Q(amount_usd__gt=0)),
        expense_usd=Sum('amount_usd', filter=models.Q(amount_usd__lt=0)),
        income_bs=Sum('amount_bs', filter=models.Q(amount_bs__gt=0)),
        expense_bs=Sum('amount_bs', filter=models.Q(amount_bs__lt=0)),
        income_real_usd=Sum('real_dollars', filter=models.Q(real_dollars__gt=0)),
        expense_real_usd=Sum('real_dollars', filter=models.Q(real_dollars__lt=0)),
        fees_usd=Sum('bank_fee_usd'),
        fees_bs=Sum('bank_fee_bs'),
        fees_real_usd=Sum('bank_fee_real_usd')
    )
    
    paginator = Paginator(transactions_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    categories = Category.objects.filter(organization=org)

    filter_options = [
        ('day', 'Hoy'),
        ('week', 'Esta semana'),
        ('15days', 'Últimos 15 días'),
        ('month', 'Último mes'),
        ('quarter', 'Último trimestre'),
        ('6months', 'Últimos 6 meses'),
        ('year', 'Último año'),
        ('all', 'Todo el tiempo'),
        ('custom', 'Personalizado'),
    ]

    # Mapeo de cuentas a monedas para lógica en JS
    accounts_data = {a.id: a.currency for a in Account.objects.filter(organization=org)}

    # Mapeo de proyectos a valuaciones para filtrado dinámico en JS
    projects = Project.objects.filter(organization=org)
    projects_data = {}
    for p in projects:
        projects_data[p.id] = list(Valuation.objects.filter(project=p).values('id', 'name', 'amount_usd'))

    form = TransactionForm(organization=org)
    bcv_rate = get_bcv_rate()

    return render(request, 'organizations/detalle_cuenta.html', {
        'account': account,
        'page_obj': page_obj,
        'sort': sort,
        'search': search_query,
        'filter_type': filter_type,
        'date_from': date_from,
        'date_to': date_to,
        'categories': categories,
        'selected_category': category_ids[0] if category_ids else '',
        'selected_categories': category_ids,
        'cost_centers': CostCenter.objects.filter(organization=org),
        'selected_cost_center': cost_center_id,
        'projects': projects,
        'selected_project': project_id,
        'status_filter': status_filter,
        'status_filter_options': [
            ('', 'Todos los estados'),
            ('completado', 'Completado'),
            ('pendiente', 'Pendiente'),
        ],
        'filter_options': filter_options,
        'accounts_data': json.dumps(accounts_data),
        'projects_data': json.dumps(projects_data, cls=DecimalEncoder),
        'form': form,
        'bcv_rate': bcv_rate,
        'totals': {
            'balance_usd': totals['balance_usd'] or 0,
            'balance_bs': totals['balance_bs'] or 0,
            'balance_real_usd': totals['balance_real_usd'] or 0,
            'income_usd': totals['income_usd'] or 0,
            'expense_usd': abs(totals['expense_usd'] or 0) + (totals['fees_usd'] or 0),
            'income_bs': totals['income_bs'] or 0,
            'expense_bs': abs(totals['expense_bs'] or 0) + (totals['fees_bs'] or 0),
            'income_real_usd': totals['income_real_usd'] or 0,
            'expense_real_usd': abs(totals['expense_real_usd'] or 0) + (totals['fees_real_usd'] or 0),
        }
    })

# --- Proyectos ---

@login_required
def lista_proyectos(request):
    org_id = request.session.get('org_id')
    if not org_id:
        return redirect('dashboard')

    org = get_object_or_404(Organization, id=org_id)
    
    # Proyectos que pertenecen a la organización o a los que tiene acceso
    # Y que el usuario actual tenga acceso explícito (ProjectUserAccess)
    projects_qs = Project.objects.filter(
        models.Q(organization=org) | models.Q(shared_organizations__organization=org),
        user_accesses__user=request.user
    ).distinct()

    # Subconsultas para calcular balance TOTAL del proyecto (todas las orgs)
    total_usd_subquery = Transaction.objects.filter(
        project_id=OuterRef('pk')
    ).order_by().values('project').annotate(
        total=Sum(F('amount_usd') - F('bank_fee_usd'))
    ).values('total')

    total_bs_subquery = Transaction.objects.filter(
        project_id=OuterRef('pk')
    ).order_by().values('project').annotate(
        total=Sum(F('amount_bs') - F('bank_fee_bs'))
    ).values('total')

    total_real_usd_subquery = Transaction.objects.filter(
        project_id=OuterRef('pk')
    ).order_by().values('project').annotate(
        total=Sum(F('real_dollars') - F('bank_fee_real_usd'))
    ).values('total')

    projects = projects_qs.annotate(
        total_balance_usd=Coalesce(Subquery(total_usd_subquery), Value(0, output_field=models.DecimalField())),
        total_balance_bs=Coalesce(Subquery(total_bs_subquery), Value(0, output_field=models.DecimalField())),
        total_balance_real_usd=Coalesce(Subquery(total_real_usd_subquery), Value(0, output_field=models.DecimalField()))
    )

    form = ProjectForm()

    return render(request, 'organizations/proyectos.html', {
        'projects': projects,
        'form': form,
    })

@login_required
@viewer_restricted
def guardar_proyecto(request, proj_id=None):
    org_id = request.session.get('org_id')
    if not org_id:
        return redirect('dashboard')

    org = get_object_or_404(Organization, id=org_id)
    instance = None
    if proj_id:
        # Solo el dueño puede editar el proyecto
        instance = get_object_or_404(Project, id=proj_id, organization=org)

    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=instance)
        if form.is_valid():
            project = form.save(commit=False)
            if not instance:
                project.organization = org
            project.save()
            
            # Si es un proyecto nuevo, darle acceso al creador automáticamente
            if not instance:
                from .models import ProjectUserAccess
                ProjectUserAccess.objects.get_or_create(user=request.user, project=project)
                
            messages.success(request, "Proyecto guardado correctamente.")
        else:
            messages.error(request, f"Error al guardar el proyecto: {first_form_error(form)}")

    return redirect('lista_proyectos')

@login_required
@viewer_restricted
def eliminar_proyecto(request, proj_id):
    org_id = request.session.get('org_id')
    if not org_id:
        return redirect('dashboard')

    org = get_object_or_404(Organization, id=org_id)
    # Solo el dueño puede eliminar
    project = get_object_or_404(Project, id=proj_id, organization=org)

    if request.method == 'POST':
        project.delete()
        messages.success(request, "Proyecto eliminado.")

    return redirect('lista_proyectos')

@login_required
def detalle_proyecto(request, proj_id):
    org_id = request.session.get('org_id')
    if not org_id:
        return redirect('dashboard')

    org = get_object_or_404(Organization, id=org_id)
    
    # Verificar acceso: El proyecto debe pertenecer u estar compartido con la org, 
    # Y el usuario debe tener acceso.
    projects_owned = Project.objects.filter(organization=org)
    projects_shared = Project.objects.filter(shared_organizations__organization=org)
    project_qs = (projects_owned | projects_shared).distinct()
    
    project = get_object_or_404(project_qs, id=proj_id, user_accesses__user=request.user)

    # Organizaciones con acceso al proyecto (dueña + compartidas), usado para
    # los datos de categorías/centros de costo/cuentas disponibles en los filtros y el formulario
    orgs_with_access = (Organization.objects.filter(projects=project) | Organization.objects.filter(shared_projects__project=project)).distinct()

    # --- Lógica de Filtrado ---
    filter_type = request.GET.get('filter_type', 'all')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    category_raw = request.GET.getlist('category')
    category_ids = []
    for val in category_raw:
        if ',' in val:
            category_ids.extend([v.strip() for v in val.split(',') if v.strip()])
        else:
            category_ids.append(val)
    category_ids = [cid for cid in category_ids if cid and cid != 'None' and cid != 'null']
    cost_center_id = request.GET.get('cost_center')
    account_id = request.GET.get('account')
    search_query = request.GET.get('search', '')
    tx_filter = request.GET.get('tx_filter', 'all') # 'all', 'bcv', 'real'
    view_mode = request.GET.get('view_mode', 'bcv') # 'bcv' or 'real'
    status_filter = request.GET.get('status', '') # 'completado', 'pendiente', ''

    # Sincronización: El filtro de transacciones afecta al toggle de balance
    if tx_filter == 'real':
        view_mode = 'real'
    elif tx_filter == 'bcv':
        view_mode = 'bcv'

    if date_from == 'None': date_from = None
    if date_to == 'None': date_to = None
    if cost_center_id == 'None' or cost_center_id == '': cost_center_id = None
    if account_id == 'None' or account_id == '': account_id = None

    # Ver TODAS las transacciones del proyecto (de cualquier organización con acceso)
    transactions_list = Transaction.objects.filter(project=project)

    # Filtrar por tipo de transacción (BCV / Real Dollars)
    if tx_filter == 'real':
        transactions_list = transactions_list.exclude(models.Q(real_dollars=0) | models.Q(real_dollars__isnull=True))
    elif tx_filter == 'bcv':
        transactions_list = transactions_list.filter(models.Q(real_dollars=0) | models.Q(real_dollars__isnull=True))

    if search_query:
        # OJO: el lookup categories__name atraviesa una relación M2M, lo que puede
        # multiplicar filas si la transacción tiene más de una categoría (aparecería
        # duplicada en la tabla y en los KPIs). Se aplica distinct() para evitarlo.
        transactions_list = transactions_list.filter(
            models.Q(description__icontains=search_query) |
            models.Q(reference_number__icontains=search_query) |
            models.Q(notes__icontains=search_query) |
            models.Q(categories__name__icontains=search_query) |
            models.Q(cost_center__code__icontains=search_query) |
            models.Q(cost_center__name__icontains=search_query) |
            models.Q(account__name__icontains=search_query) |
            models.Q(project__name__icontains=search_query) |
            models.Q(valuation__name__icontains=search_query) |
            models.Q(status__icontains=search_query) |
            models.Q(amount_bs__icontains=search_query) |
            models.Q(amount_usd__icontains=search_query) |
            models.Q(real_dollars__icontains=search_query) |
            models.Q(daily_rate__icontains=search_query)
        ).distinct()

    if category_ids:
        transactions_list = transactions_list.filter(categories__id__in=category_ids).distinct()

    if cost_center_id:
        transactions_list = transactions_list.filter(cost_center_id=cost_center_id)

    if account_id:
        transactions_list = transactions_list.filter(account_id=account_id)

    # Punto de control: mismos filtros aplicados hasta aquí (tx_filter, búsqueda,
    # categorías, centro de costo, cuenta) pero sin el filtro de estado, para poder calcular
    # el saldo pendiente independientemente del estado seleccionado.
    qs_before_status = transactions_list

    if status_filter:
        transactions_list = transactions_list.filter(status=status_filter)

    today = timezone.localdate()

    def apply_date_filter(qs):
        if date_from or date_to:
            if date_from:
                qs = qs.filter(date__gte=date_from)
            if date_to:
                qs = qs.filter(date__lte=date_to)
        elif filter_type != 'all' and filter_type != 'custom':
            if filter_type == 'day':
                start_date = today
            elif filter_type == 'week':
                start_date = today - timedelta(days=7)
            elif filter_type == '15days':
                start_date = today - timedelta(days=15)
            elif filter_type == 'month':
                start_date = today - timedelta(days=30)
            elif filter_type == 'quarter':
                start_date = today - timedelta(days=90)
            elif filter_type == '6months':
                start_date = today - timedelta(days=180)
            elif filter_type == 'year':
                start_date = today - timedelta(days=365)
            else:
                start_date = None
            if start_date:
                qs = qs.filter(date__gte=start_date)
                if filter_type == 'day':
                    # "Hoy" debe mostrar solo el día de hoy, no fechas futuras.
                    qs = qs.filter(date__lte=today)
        return qs

    transactions_list = apply_date_filter(transactions_list)
    pending_qs_base = apply_date_filter(qs_before_status).filter(status='pendiente')

    sort = request.GET.get('sort', 'desc')
    if sort == 'asc':
        transactions_list = transactions_list.order_by('date', 'id')
    else:
        transactions_list = transactions_list.order_by('-date', '-id')

    # Anotar valuaciones con el monto cubierto por transacciones de crédito de TODAS las organizaciones
    # Sumamos tanto amount_usd (BCV) como real_dollars
    valuations = list(Valuation.objects.filter(project=project).annotate(
        covered_usd=Sum(
            Coalesce('transactions__amount_usd', Value(0, output_field=models.DecimalField())) + 
            Coalesce('transactions__real_dollars', Value(0, output_field=models.DecimalField())),
            filter=models.Q(transactions__amount_usd__gt=0) | models.Q(transactions__real_dollars__gt=0)
        ),
        covered_bs=Sum('transactions__amount_bs', filter=models.Q(transactions__amount_bs__gt=0))
    ))

    # Calcular porcentajes
    for val in valuations:
        val.progress = 0
        if val.amount_usd > 0:
            covered = val.covered_usd or 0
            val.progress = min(round((covered / val.amount_usd) * 100, 2), 100)
        elif val.amount_bs > 0:
            covered = val.covered_bs or 0
            val.progress = min(round((covered / val.amount_bs) * 100, 2), 100)

    # Totales FILTRADOS para el dashboard dinámico
    totals_project = transactions_list.aggregate(
        balance_usd=Sum(F('amount_usd') - F('bank_fee_usd')),
        balance_bs=Sum(F('amount_bs') - F('bank_fee_bs')),
        balance_real_usd=Sum(F('real_dollars') - F('bank_fee_real_usd')),
        income_usd=Sum('amount_usd', filter=models.Q(amount_usd__gt=0)),
        expense_usd=Sum('amount_usd', filter=models.Q(amount_usd__lt=0)),
        income_bs=Sum('amount_bs', filter=models.Q(amount_bs__gt=0)),
        expense_bs=Sum('amount_bs', filter=models.Q(amount_bs__lt=0)),
        income_real_usd=Sum('real_dollars', filter=models.Q(real_dollars__gt=0)),
        expense_real_usd=Sum('real_dollars', filter=models.Q(real_dollars__lt=0)),
        fees_usd=Sum('bank_fee_usd'),
        fees_bs=Sum('bank_fee_bs'),
        fees_real_usd=Sum('bank_fee_real_usd')
    )
    
    # Saldo pendiente: mismos filtros aplicados (excepto estado), solo transacciones 'pendiente'
    has_pending = pending_qs_base.exists()
    pending_totals_project = pending_qs_base.aggregate(
        balance_usd=Sum(F('amount_usd') - F('bank_fee_usd')),
        balance_bs=Sum(F('amount_bs') - F('bank_fee_bs')),
        balance_real_usd=Sum(F('real_dollars') - F('bank_fee_real_usd')),
        income_usd=Sum('amount_usd', filter=models.Q(amount_usd__gt=0)),
        expense_usd=Sum('amount_usd', filter=models.Q(amount_usd__lt=0)),
        income_bs=Sum('amount_bs', filter=models.Q(amount_bs__gt=0)),
        expense_bs=Sum('amount_bs', filter=models.Q(amount_bs__lt=0)),
        income_real_usd=Sum('real_dollars', filter=models.Q(real_dollars__gt=0)),
        expense_real_usd=Sum('real_dollars', filter=models.Q(real_dollars__lt=0)),
        fees_usd=Sum('bank_fee_usd'),
        fees_bs=Sum('bank_fee_bs'),
        fees_real_usd=Sum('bank_fee_real_usd')
    )

    paginator = Paginator(transactions_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    val_form = ValuationForm()
    trans_form = TransactionForm(organization=org, project=project)
    bcv_rate = get_bcv_rate()

    chart_data = get_chart_data(transactions_list, mode=view_mode)

    orgs_data = {}
    for o in orgs_with_access:
        orgs_data[o.id] = {
            'accounts': list(Account.objects.filter(organization=o).values('id', 'name', 'currency')),
            'categories': list(Category.objects.filter(organization=o).values('id', 'name', 'color')),
            'cost_centers': list(CostCenter.objects.filter(organization=o).values('id', 'name', 'code'))
        }

    filter_options = [
        ('all', 'Todo el tiempo'),
        ('day', 'Hoy'),
        ('week', 'Esta semana'),
        ('15days', 'Últimos 15 días'),
        ('month', 'Último mes'),
        ('quarter', 'Último trimestre'),
        ('6months', 'Últimos 6 meses'),
        ('year', 'Último año'),
        ('custom', 'Personalizado'),
    ]

    return render(request, 'organizations/detalle_proyecto.html', {
        'project': project,
        'valuations': valuations,
        'page_obj': page_obj,
        'val_form': val_form,
        'trans_form': trans_form,
        'orgs_data': json.dumps(orgs_data, cls=DecimalEncoder),
        'bcv_rate': bcv_rate,
        'categories': Category.objects.filter(organization__in=orgs_with_access),
        'cost_centers': CostCenter.objects.filter(organization__in=orgs_with_access),
        'selected_cost_center': cost_center_id,
        'accounts': Account.objects.filter(organization__in=orgs_with_access),
        'selected_account': account_id,
        'selected_category': category_ids[0] if category_ids else '',
        'selected_categories': category_ids,
        'filter_type': filter_type,
        'date_from': date_from,
        'date_to': date_to,
        'search': search_query,
        'filter_options': filter_options,
        'chart_data': chart_data,
        'sort': sort,
        'view_mode': view_mode,
        'tx_filter': tx_filter,
        'status_filter': status_filter,
        'has_pending': has_pending,
        'totals': {
            'balance_usd': (totals_project['balance_usd'] or 0) + (totals_project['balance_real_usd'] or 0),
            'balance_bs': totals_project['balance_bs'] or 0,
            'balance_real_usd': totals_project['balance_real_usd'] or 0,
            'income_usd': (totals_project['income_usd'] or 0) + (totals_project['income_real_usd'] or 0),
            'income_bs': totals_project['income_bs'] or 0,
            'income_real_usd': totals_project['income_real_usd'] or 0,
            'expense_usd': abs((totals_project['expense_usd'] or 0) + (totals_project['expense_real_usd'] or 0)) +
                           (totals_project['fees_usd'] or 0) + (totals_project['fees_real_usd'] or 0),
            'expense_bs': abs(totals_project['expense_bs'] or 0) + (totals_project['fees_bs'] or 0),
            'expense_real_usd': abs(totals_project['expense_real_usd'] or 0) + (totals_project['fees_real_usd'] or 0),
            'pending_balance_usd': (pending_totals_project['balance_usd'] or 0) + (pending_totals_project['balance_real_usd'] or 0),
            'pending_balance_bs': pending_totals_project['balance_bs'] or 0,
            'pending_balance_real_usd': pending_totals_project['balance_real_usd'] or 0,
            'pending_income_usd': (pending_totals_project['income_usd'] or 0) + (pending_totals_project['income_real_usd'] or 0),
            'pending_income_bs': pending_totals_project['income_bs'] or 0,
            'pending_income_real_usd': pending_totals_project['income_real_usd'] or 0,
            'pending_expense_usd': abs((pending_totals_project['expense_usd'] or 0) + (pending_totals_project['expense_real_usd'] or 0)) +
                                    (pending_totals_project['fees_usd'] or 0) + (pending_totals_project['fees_real_usd'] or 0),
            'pending_expense_bs': abs(pending_totals_project['expense_bs'] or 0) + (pending_totals_project['fees_bs'] or 0),
            'pending_expense_real_usd': abs(pending_totals_project['expense_real_usd'] or 0) + (pending_totals_project['fees_real_usd'] or 0),
        },
        'tx_filter_options': [
            ('all', 'Todas las transacciones'),
            ('bcv', 'Transacciones BCV'),
            ('real', 'Transacciones Dólares Reales'),
        ],
        'status_filter_options': [
            ('', 'Todos los estados'),
            ('completado', 'Completado'),
            ('pendiente', 'Pendiente'),
        ],
    })

# --- Compartir proyecto (enlace público de solo lectura, sin login) ---

PROJECT_SHARE_SALT = "organizations.proyecto_publico"

# Contraseña requerida para generar un enlace público. Hardcodeada a propósito
# (no es un dato sensible por-organización, solo una traba simple contra el uso
# accidental del botón "Compartir Proyecto").
PROJECT_SHARE_PASSWORD = "CashFlow-Compartir-2026"


def _get_project_for_share(request, proj_id):
    """Mismo criterio de acceso que detalle_proyecto: la org actual debe ser
    dueña o tener el proyecto compartido, y el usuario debe tener acceso
    individual. Usado tanto para generar como para administrar enlaces."""
    org_id = request.session.get('org_id')
    if not org_id:
        return None, None
    org = get_object_or_404(Organization, id=org_id)
    projects_owned = Project.objects.filter(organization=org)
    projects_shared = Project.objects.filter(shared_organizations__organization=org)
    project_qs = (projects_owned | projects_shared).distinct()
    project = get_object_or_404(project_qs, id=proj_id, user_accesses__user=request.user)
    return org, project


@login_required
def compartir_proyecto(request, proj_id):
    """Genera un enlace público firmado (sin necesidad de login) con información
    de solo lectura del proyecto, previa verificación de una contraseña compartida.
    El token se firma criptográficamente y además queda registrado en
    ProjectShareLink, de modo que eliminarlo revoca el acceso al enlace."""
    org, project = _get_project_for_share(request, proj_id)
    if org is None:
        return JsonResponse({'ok': False, 'error': 'No hay organización seleccionada.'}, status=400)

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido.'}, status=405)

    password = request.POST.get('password', '')
    if password != PROJECT_SHARE_PASSWORD:
        debug_event(
            "proyecto.compartir.acceso_denegado",
            user_id=request.user.id,
            org_id=org.id,
            project_id=project.id,
        )
        return JsonResponse({'ok': False, 'error': 'Contraseña incorrecta.'}, status=403)

    token = signing.dumps({'proj_id': project.id}, salt=PROJECT_SHARE_SALT)
    link = ProjectShareLink.objects.create(project=project, token=token, created_by=request.user)
    public_url = request.build_absolute_uri(reverse('proyecto_publico', kwargs={'token': token}))

    debug_event(
        "proyecto.compartir.generado",
        user_id=request.user.id,
        org_id=org.id,
        project_id=project.id,
    )

    return JsonResponse({
        'ok': True,
        'url': public_url,
        'link': {
            'id': link.id,
            'url': public_url,
            'project_name': project.name,
            'created_at': link.created_at.strftime('%d/%m/%Y %H:%M'),
            'created_by': request.user.username,
        },
    })


@login_required
def listar_enlaces_compartidos(request):
    """Verifica la contraseña compartida y, si es correcta, devuelve TODOS los
    enlaces públicos generados para los proyectos a los que el usuario tiene
    acceso individual (ProjectUserAccess), sin importar la organización
    seleccionada actualmente ni el proyecto desde el que se abrió el modal."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido.'}, status=405)

    password = request.POST.get('password', '')
    if password != PROJECT_SHARE_PASSWORD:
        debug_event(
            "proyecto.compartir.listado.acceso_denegado",
            user_id=request.user.id,
        )
        return JsonResponse({'ok': False, 'error': 'Contraseña incorrecta.'}, status=403)

    links_qs = ProjectShareLink.objects.filter(
        project__user_accesses__user=request.user
    ).distinct().select_related('project', 'created_by').order_by('-created_at')

    links = [{
        'id': link.id,
        'url': request.build_absolute_uri(reverse('proyecto_publico', kwargs={'token': link.token})),
        'project_name': link.project.name,
        'created_at': link.created_at.strftime('%d/%m/%Y %H:%M'),
        'created_by': link.created_by.username if link.created_by else '',
    } for link in links_qs]

    return JsonResponse({'ok': True, 'links': links})


@login_required
def eliminar_enlace_compartido(request, link_id):
    """Elimina (revoca) un enlace público de proyecto previamente generado.
    Permitido para cualquier proyecto al que el usuario tenga acceso individual,
    sin depender de la organización seleccionada en ese momento (la tabla de
    enlaces ahora abarca todos los proyectos del usuario, no solo el actual)."""
    link = get_object_or_404(
        ProjectShareLink.objects.filter(project__user_accesses__user=request.user),
        id=link_id,
    )

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido.'}, status=405)

    debug_event(
        "proyecto.compartir.eliminado",
        user_id=request.user.id,
        project_id=link.project_id,
        link_id=link.id,
    )
    link.delete()

    return JsonResponse({'ok': True})


def proyecto_publico(request, token):
    """Vista pública (sin login) de solo lectura de un proyecto, accesible solo
    mediante un enlace firmado generado desde compartir_proyecto. No requiere
    sesión ni organización seleccionada: expone datos de TODAS las organizaciones
    con acceso al proyecto, igual que detalle_proyecto."""
    def enlace_invalido():
        return render(request, 'organizations/enlace_publico_invalido.html', {
            'hide_navbar': True,
            'hide_sidebar': True,
            'wide_layout': True,
        }, status=404)

    try:
        data = signing.loads(token, salt=PROJECT_SHARE_SALT)
    except signing.BadSignature:
        return enlace_invalido()

    # Además de la firma, el token debe seguir registrado: esto es lo que
    # permite revocar el enlace al eliminarlo desde "Compartir Proyecto".
    if not ProjectShareLink.objects.filter(token=token).exists():
        return enlace_invalido()

    project = get_object_or_404(Project, id=data.get('proj_id'))

    orgs_with_access = (Organization.objects.filter(projects=project) | Organization.objects.filter(shared_projects__project=project)).distinct()

    # --- Lógica de Filtrado (misma que detalle_proyecto, sin dependencia de sesión/org) ---
    filter_type = request.GET.get('filter_type', 'all')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    category_raw = request.GET.getlist('category')
    category_ids = []
    for val in category_raw:
        if ',' in val:
            category_ids.extend([v.strip() for v in val.split(',') if v.strip()])
        else:
            category_ids.append(val)
    category_ids = [cid for cid in category_ids if cid and cid != 'None' and cid != 'null']
    cost_center_id = request.GET.get('cost_center')
    account_id = request.GET.get('account')
    search_query = request.GET.get('search', '')
    tx_filter = request.GET.get('tx_filter', 'all')
    view_mode = request.GET.get('view_mode', 'bcv')
    status_filter = request.GET.get('status', '')

    if tx_filter == 'real':
        view_mode = 'real'
    elif tx_filter == 'bcv':
        view_mode = 'bcv'

    if date_from == 'None': date_from = None
    if date_to == 'None': date_to = None
    if cost_center_id == 'None' or cost_center_id == '': cost_center_id = None
    if account_id == 'None' or account_id == '': account_id = None

    transactions_list = Transaction.objects.filter(project=project)

    if tx_filter == 'real':
        transactions_list = transactions_list.exclude(models.Q(real_dollars=0) | models.Q(real_dollars__isnull=True))
    elif tx_filter == 'bcv':
        transactions_list = transactions_list.filter(models.Q(real_dollars=0) | models.Q(real_dollars__isnull=True))

    if search_query:
        transactions_list = transactions_list.filter(
            models.Q(description__icontains=search_query) |
            models.Q(reference_number__icontains=search_query) |
            models.Q(notes__icontains=search_query) |
            models.Q(categories__name__icontains=search_query) |
            models.Q(cost_center__code__icontains=search_query) |
            models.Q(cost_center__name__icontains=search_query) |
            models.Q(account__name__icontains=search_query) |
            models.Q(project__name__icontains=search_query) |
            models.Q(valuation__name__icontains=search_query) |
            models.Q(status__icontains=search_query) |
            models.Q(amount_bs__icontains=search_query) |
            models.Q(amount_usd__icontains=search_query) |
            models.Q(real_dollars__icontains=search_query) |
            models.Q(daily_rate__icontains=search_query)
        ).distinct()

    if category_ids:
        transactions_list = transactions_list.filter(categories__id__in=category_ids).distinct()

    if cost_center_id:
        transactions_list = transactions_list.filter(cost_center_id=cost_center_id)

    if account_id:
        transactions_list = transactions_list.filter(account_id=account_id)

    qs_before_status = transactions_list

    if status_filter:
        transactions_list = transactions_list.filter(status=status_filter)

    today = timezone.localdate()

    def apply_date_filter(qs):
        if date_from or date_to:
            if date_from:
                qs = qs.filter(date__gte=date_from)
            if date_to:
                qs = qs.filter(date__lte=date_to)
        elif filter_type != 'all' and filter_type != 'custom':
            if filter_type == 'day':
                start_date = today
            elif filter_type == 'week':
                start_date = today - timedelta(days=7)
            elif filter_type == '15days':
                start_date = today - timedelta(days=15)
            elif filter_type == 'month':
                start_date = today - timedelta(days=30)
            elif filter_type == 'quarter':
                start_date = today - timedelta(days=90)
            elif filter_type == '6months':
                start_date = today - timedelta(days=180)
            elif filter_type == 'year':
                start_date = today - timedelta(days=365)
            else:
                start_date = None
            if start_date:
                qs = qs.filter(date__gte=start_date)
                if filter_type == 'day':
                    qs = qs.filter(date__lte=today)
        return qs

    transactions_list = apply_date_filter(transactions_list)
    pending_qs_base = apply_date_filter(qs_before_status).filter(status='pendiente')

    sort = request.GET.get('sort', 'desc')
    if sort == 'asc':
        transactions_list = transactions_list.order_by('date', 'id')
    else:
        transactions_list = transactions_list.order_by('-date', '-id')

    valuations = list(Valuation.objects.filter(project=project).annotate(
        covered_usd=Sum(
            Coalesce('transactions__amount_usd', Value(0, output_field=models.DecimalField())) +
            Coalesce('transactions__real_dollars', Value(0, output_field=models.DecimalField())),
            filter=models.Q(transactions__amount_usd__gt=0) | models.Q(transactions__real_dollars__gt=0)
        ),
        covered_bs=Sum('transactions__amount_bs', filter=models.Q(transactions__amount_bs__gt=0))
    ))

    for val in valuations:
        val.progress = 0
        if val.amount_usd > 0:
            covered = val.covered_usd or 0
            val.progress = min(round((covered / val.amount_usd) * 100, 2), 100)
        elif val.amount_bs > 0:
            covered = val.covered_bs or 0
            val.progress = min(round((covered / val.amount_bs) * 100, 2), 100)

    totals_project = transactions_list.aggregate(
        balance_usd=Sum(F('amount_usd') - F('bank_fee_usd')),
        balance_bs=Sum(F('amount_bs') - F('bank_fee_bs')),
        balance_real_usd=Sum(F('real_dollars') - F('bank_fee_real_usd')),
        income_usd=Sum('amount_usd', filter=models.Q(amount_usd__gt=0)),
        expense_usd=Sum('amount_usd', filter=models.Q(amount_usd__lt=0)),
        income_bs=Sum('amount_bs', filter=models.Q(amount_bs__gt=0)),
        expense_bs=Sum('amount_bs', filter=models.Q(amount_bs__lt=0)),
        income_real_usd=Sum('real_dollars', filter=models.Q(real_dollars__gt=0)),
        expense_real_usd=Sum('real_dollars', filter=models.Q(real_dollars__lt=0)),
        fees_usd=Sum('bank_fee_usd'),
        fees_bs=Sum('bank_fee_bs'),
        fees_real_usd=Sum('bank_fee_real_usd')
    )

    has_pending = pending_qs_base.exists()
    pending_totals_project = pending_qs_base.aggregate(
        balance_usd=Sum(F('amount_usd') - F('bank_fee_usd')),
        balance_bs=Sum(F('amount_bs') - F('bank_fee_bs')),
        balance_real_usd=Sum(F('real_dollars') - F('bank_fee_real_usd')),
        income_usd=Sum('amount_usd', filter=models.Q(amount_usd__gt=0)),
        expense_usd=Sum('amount_usd', filter=models.Q(amount_usd__lt=0)),
        income_bs=Sum('amount_bs', filter=models.Q(amount_bs__gt=0)),
        expense_bs=Sum('amount_bs', filter=models.Q(amount_bs__lt=0)),
        income_real_usd=Sum('real_dollars', filter=models.Q(real_dollars__gt=0)),
        expense_real_usd=Sum('real_dollars', filter=models.Q(real_dollars__lt=0)),
        fees_usd=Sum('bank_fee_usd'),
        fees_bs=Sum('bank_fee_bs'),
        fees_real_usd=Sum('bank_fee_real_usd')
    )

    paginator = Paginator(transactions_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    chart_data = get_chart_data(transactions_list, mode=view_mode)

    filter_options = [
        ('all', 'Todo el tiempo'),
        ('day', 'Hoy'),
        ('week', 'Esta semana'),
        ('15days', 'Últimos 15 días'),
        ('month', 'Último mes'),
        ('quarter', 'Último trimestre'),
        ('6months', 'Últimos 6 meses'),
        ('year', 'Último año'),
        ('custom', 'Personalizado'),
    ]

    return render(request, 'organizations/proyecto_publico.html', {
        'project': project,
        'valuations': valuations,
        'page_obj': page_obj,
        'token': token,
        'categories': Category.objects.filter(organization__in=orgs_with_access),
        'cost_centers': CostCenter.objects.filter(organization__in=orgs_with_access),
        'selected_cost_center': cost_center_id,
        'accounts': Account.objects.filter(organization__in=orgs_with_access),
        'selected_account': account_id,
        'selected_category': category_ids[0] if category_ids else '',
        'selected_categories': category_ids,
        'filter_type': filter_type,
        'date_from': date_from,
        'date_to': date_to,
        'search': search_query,
        'filter_options': filter_options,
        'chart_data': chart_data,
        'sort': sort,
        'view_mode': view_mode,
        'tx_filter': tx_filter,
        'status_filter': status_filter,
        'has_pending': has_pending,
        'totals': {
            'balance_usd': (totals_project['balance_usd'] or 0) + (totals_project['balance_real_usd'] or 0),
            'balance_bs': totals_project['balance_bs'] or 0,
            'balance_real_usd': totals_project['balance_real_usd'] or 0,
            'income_usd': (totals_project['income_usd'] or 0) + (totals_project['income_real_usd'] or 0),
            'income_bs': totals_project['income_bs'] or 0,
            'income_real_usd': totals_project['income_real_usd'] or 0,
            'expense_usd': abs((totals_project['expense_usd'] or 0) + (totals_project['expense_real_usd'] or 0)) +
                           (totals_project['fees_usd'] or 0) + (totals_project['fees_real_usd'] or 0),
            'expense_bs': abs(totals_project['expense_bs'] or 0) + (totals_project['fees_bs'] or 0),
            'expense_real_usd': abs(totals_project['expense_real_usd'] or 0) + (totals_project['fees_real_usd'] or 0),
            'pending_balance_usd': (pending_totals_project['balance_usd'] or 0) + (pending_totals_project['balance_real_usd'] or 0),
            'pending_balance_bs': pending_totals_project['balance_bs'] or 0,
            'pending_balance_real_usd': pending_totals_project['balance_real_usd'] or 0,
            'pending_income_usd': (pending_totals_project['income_usd'] or 0) + (pending_totals_project['income_real_usd'] or 0),
            'pending_income_bs': pending_totals_project['income_bs'] or 0,
            'pending_income_real_usd': pending_totals_project['income_real_usd'] or 0,
            'pending_expense_usd': abs((pending_totals_project['expense_usd'] or 0) + (pending_totals_project['expense_real_usd'] or 0)) +
                                    (pending_totals_project['fees_usd'] or 0) + (pending_totals_project['fees_real_usd'] or 0),
            'pending_expense_bs': abs(pending_totals_project['expense_bs'] or 0) + (pending_totals_project['fees_bs'] or 0),
            'pending_expense_real_usd': abs(pending_totals_project['expense_real_usd'] or 0) + (pending_totals_project['fees_real_usd'] or 0),
        },
        'tx_filter_options': [
            ('all', 'Todas las transacciones'),
            ('bcv', 'Transacciones BCV'),
            ('real', 'Transacciones Dólares Reales'),
        ],
        'status_filter_options': [
            ('', 'Todos los estados'),
            ('completado', 'Completado'),
            ('pendiente', 'Pendiente'),
        ],
        # Se ocultan navbar y sidebar siempre (incluso si quien abre el enlace
        # público resulta estar logueado en su propia sesión). wide_layout evita
        # que base.html use el layout angosto "auth-container" (pensado para
        # login) cuando ambos hide_navbar/hide_sidebar están activos.
        'hide_navbar': True,
        'hide_sidebar': True,
        'wide_layout': True,
    })

# --- Valuaciones ---

@login_required
@viewer_restricted
def guardar_valuacion(request, proj_id, val_id=None):
    org_id = request.session.get('org_id')
    if not org_id:
        return redirect('dashboard')
    org = get_object_or_404(Organization, id=org_id)
    
    # Permitir si es dueño O si tiene acceso compartido, Y el usuario tiene acceso individual al proyecto
    project = get_object_or_404(
        Project.objects.filter(
            models.Q(organization=org) | models.Q(shared_organizations__organization=org)
        ).distinct(),
        id=proj_id,
        user_accesses__user=request.user
    )
    
    instance = None
    if val_id:
        instance = get_object_or_404(Valuation, id=val_id, project=project)

    if request.method == 'POST':
        form = ValuationForm(request.POST, instance=instance)
        if form.is_valid():
            valuation = form.save(commit=False)
            valuation.project = project
            valuation.save()
            messages.success(request, "Valuación guardada correctamente.")
        else:
            messages.error(request, f"Error al guardar la valuación: {first_form_error(form)}")

    return redirect('detalle_proyecto', proj_id=project.id)

@login_required
@viewer_restricted
def eliminar_valuacion(request, val_id):
    org_id = request.session.get('org_id')
    if not org_id:
        return redirect('dashboard')
    org = get_object_or_404(Organization, id=org_id)
    
    # Buscar la valuación y verificar que la organización tenga acceso al proyecto
    valuation = get_object_or_404(Valuation, id=val_id)
    project = valuation.project
    
    # Verificar acceso (Dueño o Compartido) Y que el usuario tenga acceso individual al proyecto
    is_owner = project.organization == org
    is_shared = project.shared_organizations.filter(organization=org).exists()
    has_user_access = project.user_accesses.filter(user=request.user).exists()

    if not ((is_owner or is_shared) and has_user_access):
        messages.error(
            request,
            "No tiene permiso para eliminar esta valuación: la organización actual no es propietaria "
            "del proyecto ni lo tiene compartido con ella."
        )
        return redirect('lista_proyectos')

    proj_id = project.id

    if request.method == 'POST':
        valuation.delete()
        messages.success(request, "Valuación eliminada.")

    return redirect('detalle_proyecto', proj_id=proj_id)
