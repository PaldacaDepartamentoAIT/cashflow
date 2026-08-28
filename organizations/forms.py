from django import forms
from django.core.exceptions import ValidationError
from django.db import models
from .models import Transaction, Category, Account, Project, Valuation, Organization, CostCenter
from .amounts import apply_dual_currency_amounts, zero_foreign_currency_fields
from .photos import max_fotos, validar_foto

class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = [
            'date', 'organization', 'account', 'reference_number', 'description', 
            'notes', 'categories', 'cost_center', 'project', 'valuation', 
            'status', 'amount_bs', 'amount_usd', 'daily_rate',
            'bank_fee_bs', 'bank_fee_usd', 'real_dollars', 'bank_fee_real_usd',
            'amount_eur', 'bank_fee_eur'
        ]
        widgets = {
            'date': forms.DateInput(attrs={'class': 'cf-input', 'type': 'date', 'required': 'required'}),
            'organization': forms.Select(attrs={'class': 'cf-input', 'required': 'required'}),
            'account': forms.Select(attrs={'class': 'cf-input', 'required': 'required'}),
            'reference_number': forms.TextInput(attrs={'class': 'cf-input', 'placeholder': 'Nro. Referencia'}),
            'description': forms.Textarea(attrs={'class': 'cf-input', 'rows': 2, 'placeholder': 'Descripción de la transacción', 'required': 'required'}),
            'notes': forms.Textarea(attrs={'class': 'cf-input', 'rows': 2, 'placeholder': 'Notas adicionales'}),
            'categories': forms.SelectMultiple(attrs={'class': 'cf-input cf-select', 'style': 'height: auto; min-height: 80px;'}),
            'cost_center': forms.Select(attrs={'class': 'cf-input'}),
            'project': forms.Select(attrs={'class': 'cf-input'}),
            'valuation': forms.Select(attrs={'class': 'cf-input'}),
            'status': forms.Select(attrs={'class': 'cf-input', 'required': 'required'}),
            'amount_bs': forms.NumberInput(attrs={'class': 'cf-input', 'step': '0.01', 'type': 'number', 'required': 'required'}),
            'amount_usd': forms.NumberInput(attrs={'class': 'cf-input', 'step': '0.01', 'type': 'number', 'required': 'required'}),
            'daily_rate': forms.NumberInput(attrs={'class': 'cf-input', 'step': '0.0001', 'type': 'number', 'required': 'required'}),
            'bank_fee_bs': forms.NumberInput(attrs={'class': 'cf-input', 'step': '0.01', 'type': 'number'}),
            'bank_fee_usd': forms.NumberInput(attrs={'class': 'cf-input', 'step': '0.01', 'type': 'number'}),
            'real_dollars': forms.NumberInput(attrs={'class': 'cf-input', 'step': '0.01', 'type': 'number'}),
            'bank_fee_real_usd': forms.NumberInput(attrs={'class': 'cf-input', 'step': '0.01', 'type': 'number'}),
            'amount_eur': forms.NumberInput(attrs={'class': 'cf-input', 'step': '0.01', 'type': 'number'}),
            'bank_fee_eur': forms.NumberInput(attrs={'class': 'cf-input', 'step': '0.01', 'type': 'number'}),
        }

    def clean_bank_fee_eur(self):
        # La comisión en euros es opcional: no obligamos a escribir un 0 en cada
        # transacción que no la tenga (el modelo tampoco acepta NULL).
        return self.cleaned_data.get('bank_fee_eur') or 0

    def clean(self):
        cleaned_data = super().clean()
        account = cleaned_data.get('account')
        if not account:
            return cleaned_data

        real_dollars = cleaned_data.get('real_dollars') or 0
        bank_fee_real_usd = cleaned_data.get('bank_fee_real_usd') or 0
        amount_eur = cleaned_data.get('amount_eur') or 0
        bank_fee_eur = cleaned_data.get('bank_fee_eur') or 0

        # Si la cuenta es en dólares, forzar el uso de real_dollars
        if account.currency == Account.CURRENCY_USD:
            amount_usd_bcv = cleaned_data.get('amount_usd') or 0

            # Si el usuario mandó el monto en el campo BCV por error, lo movemos a real_dollars
            if real_dollars == 0 and amount_usd_bcv != 0:
                real_dollars = amount_usd_bcv
                cleaned_data['real_dollars'] = real_dollars

            if real_dollars == 0:
                raise ValidationError(
                    "Esta cuenta está denominada en dólares: solo puede recibir o registrar movimientos "
                    "en el campo 'Dólares'. Los campos de Bolívares, Dólares BCV o Euros no aplican "
                    "para este tipo de cuenta."
                )

            # Cera Bs., USD-BCV y euros; conserva real_dollars/bank_fee_real_usd.
            zero_foreign_currency_fields(cleaned_data, Account.CURRENCY_USD)
            cleaned_data['real_dollars'] = real_dollars
            cleaned_data['bank_fee_real_usd'] = bank_fee_real_usd

        elif account.currency == Account.CURRENCY_EUR:
            amount_usd_bcv = cleaned_data.get('amount_usd') or 0

            # Mismo rescate que en dólares: monto puesto en el campo BCV por error
            if amount_eur == 0 and amount_usd_bcv != 0:
                amount_eur = amount_usd_bcv
                cleaned_data['amount_eur'] = amount_eur

            if amount_eur == 0:
                raise ValidationError(
                    "Esta cuenta está denominada en euros: solo puede recibir o registrar movimientos "
                    "en el campo 'Euros'. Los campos de Bolívares, Dólares BCV o Dólares no aplican "
                    "para este tipo de cuenta."
                )

            zero_foreign_currency_fields(cleaned_data, Account.CURRENCY_EUR)
            cleaned_data['amount_eur'] = amount_eur
            cleaned_data['bank_fee_eur'] = bank_fee_eur

        else:
            # CUENTA EN BOLÍVARES: Solo BCV
            if real_dollars != 0 or bank_fee_real_usd != 0:
                raise ValidationError(
                    "Esta cuenta está denominada en bolívares: los movimientos deben registrarse "
                    "mediante el tipo de cambio BCV (campos de Bolívares o Dólares BCV). El campo "
                    "'Dólares' solo aplica a cuentas en dólares."
                )

            if amount_eur != 0 or bank_fee_eur != 0:
                raise ValidationError(
                    "Esta cuenta está denominada en bolívares: los movimientos deben registrarse "
                    "mediante el tipo de cambio BCV (campos de Bolívares o Dólares BCV). El campo "
                    "'Euros' solo aplica a cuentas en euros."
                )

            cleaned_data['real_dollars'] = 0
            cleaned_data['bank_fee_real_usd'] = 0
            cleaned_data['amount_eur'] = 0
            cleaned_data['bank_fee_eur'] = 0

            amount_bs = cleaned_data.get('amount_bs') or 0
            amount_usd = cleaned_data.get('amount_usd') or 0
            daily_rate = cleaned_data.get('daily_rate') or 1
            
            # Validate that daily_rate is positive
            if daily_rate <= 0:
                self.add_error('daily_rate', 'La tasa de cambio debe ser mayor a cero: ingrese la tasa BCV vigente para calcular el equivalente en la otra moneda.')
                return cleaned_data
            
            # Validate that daily_rate is not negative (additional safety check)
            if daily_rate < 0:
                self.add_error('daily_rate', 'La tasa de cambio no puede ser un valor negativo: ingrese un número positivo.')
                return cleaned_data
            
            amount_bs, amount_usd = apply_dual_currency_amounts(amount_bs, amount_usd, daily_rate)
            cleaned_data['amount_bs'] = amount_bs
            cleaned_data['amount_usd'] = amount_usd

            # Comisión bancaria BCV
            bank_fee_bs = cleaned_data.get('bank_fee_bs') or 0
            bank_fee_usd = cleaned_data.get('bank_fee_usd') or 0
            bank_fee_bs, bank_fee_usd = apply_dual_currency_amounts(bank_fee_bs, bank_fee_usd, daily_rate)
            cleaned_data['bank_fee_bs'] = bank_fee_bs
            cleaned_data['bank_fee_usd'] = bank_fee_usd

        return cleaned_data

    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        project = kwargs.pop('project', None)
        super().__init__(*args, **kwargs)
        
        # Estado por defecto: Completado
        self.fields['status'].initial = 'completado'

        # La comisión en euros solo aplica a cuentas en euros; se omite en el
        # resto de los formularios en lugar de exigir un 0 explícito.
        self.fields['bank_fee_eur'].required = False
        
        if project:
            # Si estamos en un proyecto, restringir organizaciones a las que tienen acceso
            orgs_owned = Organization.objects.filter(projects=project)
            orgs_shared = Organization.objects.filter(shared_projects__project=project)
            self.fields['organization'].queryset = (orgs_owned | orgs_shared).distinct()
            
            # Valuaciones del proyecto
            self.fields['valuation'].queryset = Valuation.objects.filter(project=project)
            
            # Filtrar cuentas y categorías por la organización seleccionada (o la actual si no hay post)
            selected_org = self.data.get('organization') or (self.instance.organization_id if self.instance.pk else organization.id if organization else None)
            if selected_org:
                self.fields['organization'].initial = selected_org
                self.fields['account'].queryset = Account.objects.filter(organization_id=selected_org)
                self.fields['categories'].queryset = Category.objects.filter(organization_id=selected_org)
                self.fields['cost_center'].queryset = CostCenter.objects.filter(organization_id=selected_org)
            else:
                self.fields['account'].queryset = Account.objects.none()
                self.fields['categories'].queryset = Category.objects.none()
                self.fields['cost_center'].queryset = CostCenter.objects.none()
        elif organization:
            # Comportamiento original para la vista de transacciones
            self.fields['organization'].queryset = Organization.objects.filter(id=organization.id)
            self.fields['organization'].initial = organization
            self.fields['organization'].widget = forms.HiddenInput()
            
            self.fields['categories'].queryset = Category.objects.filter(organization=organization)
            self.fields['account'].queryset = Account.objects.filter(organization=organization)
            self.fields['cost_center'].queryset = CostCenter.objects.filter(organization=organization)
            self.fields['project'].queryset = Project.objects.filter(
                models.Q(organization=organization) | models.Q(shared_organizations__organization=organization)
            ).distinct()
            self.fields['valuation'].queryset = Valuation.objects.filter(
                models.Q(project__organization=organization) | models.Q(project__shared_organizations__organization=organization)
            ).distinct()

class TransactionPhotosForm(forms.Form):
    """Valida las fotos adjuntas de una transacción: cantidad total, tamaño,
    extensión, tipo de contenido y que cada archivo sea realmente una imagen.

    Va aparte de TransactionForm a propósito: guardar_transaccion() nunca
    re-renderiza el formulario (siempre redirige), así que un formset sería peso
    muerto; y esta validación necesita datos que el ModelForm no tiene (las fotos
    ya existentes y los ids que se están borrando en el mismo request).
    """

    def __init__(self, data=None, files=None, *, transaction=None, **kwargs):
        self.transaction = transaction
        self.nuevas = files.getlist('photos') if files else []
        self.ids_a_eliminar = []
        self._ids_solicitados = data.getlist('delete_photo_ids') if data else []
        super().__init__(data=data, files=files, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        existentes = self.transaction.photos.count() if self.transaction else 0

        # Solo se pueden marcar para borrar fotos de ESTA transacción: la
        # intersección se hace antes de contar, así nadie amplía su cupo
        # enviando ids de otra transacción.
        if self.transaction and self._ids_solicitados:
            ids = {int(v) for v in self._ids_solicitados if str(v).isdigit()}
            self.ids_a_eliminar = list(
                self.transaction.photos.filter(id__in=ids).values_list('id', flat=True)
            )

        total = existentes - len(self.ids_a_eliminar) + len(self.nuevas)
        if total > max_fotos():
            raise ValidationError(
                "Solo puede adjuntar hasta %d fotos por transacción: actualmente "
                "tiene %d, está eliminando %d y agregando %d (total %d). Quite "
                "algunas fotos antes de guardar."
                % (max_fotos(), existentes, len(self.ids_a_eliminar), len(self.nuevas), total)
            )

        for archivo in self.nuevas:
            validar_foto(archivo)

        return cleaned_data


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'cf-input', 'placeholder': 'Nombre de la categoría'}),
            'description': forms.Textarea(attrs={'class': 'cf-input', 'rows': 2, 'placeholder': 'Breve descripción'}),
            'color': forms.TextInput(attrs={'class': 'cf-input', 'type': 'color', 'style': 'height: 38px; width: 60px; padding: 2px;'}),
        }

class AccountForm(forms.ModelForm):
    currency = forms.ChoiceField(
        choices=Account.CURRENCY_CHOICES,
        label='Moneda de la cuenta',
        widget=forms.Select(attrs={'class': 'cf-select', 'id': 'id_account_currency'}),
    )
    name = forms.CharField(
        label='Nombre de la cuenta',
        required=True,
        widget=forms.TextInput(attrs={'class': 'cf-input', 'placeholder': 'Ej. Cuenta Principal, Nómina, etc.'}),
    )
    initial_balance = forms.DecimalField(
        max_digits=20,
        decimal_places=2,
        required=False,
        label='Saldo inicial',
        widget=forms.NumberInput(attrs={'class': 'cf-input', 'step': '0.01', 'type': 'number', 'placeholder': '0.00'}),
    )
    daily_rate = forms.DecimalField(
        max_digits=20,
        decimal_places=4,
        required=False,
        label='Tasa BCV del día',
        widget=forms.NumberInput(attrs={'class': 'cf-input', 'step': '0.0001', 'type': 'number'}),
    )

    class Meta:
        model = Account
        fields = ['currency', 'name']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['currency'].disabled = True

    def clean(self):
        cleaned_data = super().clean()

        balance = cleaned_data.get('initial_balance') or 0
        if balance < 0:
            self.add_error('initial_balance', 'El saldo inicial no puede ser un valor negativo: ingrese 0 o un monto positivo.')

        return cleaned_data

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'cf-input', 'placeholder': 'Nombre del proyecto'}),
            'description': forms.Textarea(attrs={'class': 'cf-input', 'rows': 3, 'placeholder': 'Descripción del proyecto'}),
        }

class ValuationForm(forms.ModelForm):
    class Meta:
        model = Valuation
        fields = ['name', 'amount_usd', 'amount_bs', 'daily_rate']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'cf-input', 'placeholder': 'Ej. Valuación 01, Fundaciones...', 'required': 'required'}),
            'amount_usd': forms.NumberInput(attrs={'class': 'cf-input', 'step': '0.01', 'type': 'number', 'required': 'required'}),
            'amount_bs': forms.NumberInput(attrs={'class': 'cf-input', 'step': '0.01', 'type': 'number', 'required': 'required'}),
            'daily_rate': forms.NumberInput(attrs={'class': 'cf-input', 'step': '0.0001', 'type': 'number', 'required': 'required'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        usd = cleaned_data.get('amount_usd')
        bs = cleaned_data.get('amount_bs')
        rate = cleaned_data.get('daily_rate') or 1
        
        # Validate that daily_rate is positive
        if rate is not None and rate <= 0:
            self.add_error('daily_rate', 'La tasa de cambio debe ser mayor a cero: ingrese la tasa BCV vigente para calcular el equivalente en la otra moneda.')
            return cleaned_data
        
        # Validate that daily_rate is not negative (additional safety check)
        if rate is not None and rate < 0:
            self.add_error('daily_rate', 'La tasa de cambio no puede ser un valor negativo: ingrese un número positivo.')
            return cleaned_data
        
        if (usd and usd != 0) and (not bs or bs == 0):
            cleaned_data['amount_bs'] = round(usd * rate, 2)
        elif (bs and bs != 0) and (not usd or usd == 0):
            cleaned_data['amount_usd'] = round(bs / rate, 2) if rate != 0 else 0
            
        return cleaned_data
