from django.db import models
from django.contrib.auth.models import User

class Organization(models.Model):
    name = models.CharField(max_length=255, verbose_name="Nombre de la organización")

    class Meta:
        verbose_name = "Organización"
        verbose_name_plural = "Organizaciones"

    def __str__(self):
        return self.name

class OrganizationAccess(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='organization_accesses', verbose_name="Usuario")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='user_accesses', verbose_name="Organización")

    class Meta:
        verbose_name = "Acceso a organización"
        verbose_name_plural = "Accesos a organizaciones"
        unique_together = ('user', 'organization')

    def __str__(self):
        return f"{self.user.username} - {self.organization.name}"

class Account(models.Model):
    CURRENCY_BS = 'BS'
    CURRENCY_USD = 'USD'
    CURRENCY_EUR = 'EUR'
    CURRENCY_CHOICES = [
        (CURRENCY_BS, 'Bolívares'),
        (CURRENCY_USD, 'Dólares'),
        (CURRENCY_EUR, 'Euros'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='accounts', verbose_name="Organización")
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default=CURRENCY_BS, verbose_name="Moneda")
    bank_code = models.CharField(max_length=10, blank=True, verbose_name="Código de banco")
    bank_name = models.CharField(max_length=255, verbose_name="Banco")
    rif = models.CharField(max_length=15, verbose_name="RIF")
    account_number = models.CharField(max_length=30, verbose_name="Número de cuenta")
    holder = models.CharField(max_length=255, verbose_name="Titular")
    name = models.CharField(max_length=255, verbose_name="Nombre de la cuenta", default="Cuenta Principal")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")

    class Meta:
        verbose_name = "Cuenta"
        verbose_name_plural = "Cuentas"

    def __str__(self):
        return f"{self.name} - {self.organization.name}"

class Category(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='categories', verbose_name="Organización")
    name = models.CharField(max_length=100, verbose_name="Nombre")
    description = models.TextField(blank=True, null=True, verbose_name="Descripción")
    color = models.CharField(max_length=7, default="#000000", verbose_name="Color (Hex)")

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"

    def __str__(self):
        return self.name

class Project(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='projects', verbose_name="Organización")
    name = models.CharField(max_length=200, verbose_name="Nombre")
    description = models.TextField(blank=True, null=True, verbose_name="Descripción")

    class Meta:
        verbose_name = "Proyecto"
        verbose_name_plural = "Proyectos"

    def __str__(self):
        return self.name

class ProjectOrganizationAccess(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='shared_organizations', verbose_name="Proyecto")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='shared_projects', verbose_name="Organización")

    class Meta:
        verbose_name = "Acceso de organización a proyecto"
        verbose_name_plural = "Accesos de organizaciones a proyectos"
        unique_together = ('project', 'organization')

    def __str__(self):
        return f"{self.organization.name} - {self.project.name}"

class ProjectUserAccess(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='project_accesses', verbose_name="Usuario")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='user_accesses', verbose_name="Proyecto")

    class Meta:
        verbose_name = "Acceso de usuario a proyecto"
        verbose_name_plural = "Accesos de usuarios a proyectos"
        unique_together = ('user', 'project')

    def __str__(self):
        return f"{self.user.username} - {self.project.name}"

class Valuation(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='valuations', verbose_name="Proyecto")
    name = models.CharField(max_length=255, verbose_name="Nombre de la valuación", default="Valuación")
    amount_usd = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="Monto en Dólares", default=0)
    amount_bs = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="Monto en Bolívares", default=0)
    daily_rate = models.DecimalField(max_digits=20, decimal_places=4, verbose_name="Tasa del día", default=1)

    class Meta:
        verbose_name = "Valuación"
        verbose_name_plural = "Valuaciones"

    def __str__(self):
        return f"{self.name} - {self.project.name} ({self.amount_usd} $)"

class CostCenter(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='cost_centers', verbose_name="Organización")
    code = models.CharField(max_length=50, verbose_name="Código")
    name = models.CharField(max_length=255, verbose_name="Nombre")

    class Meta:
        verbose_name = "Centro de Costo"
        verbose_name_plural = "Centros de Costo"
        unique_together = ('organization', 'code')

    def __str__(self):
        return f"{self.code} - {self.name}"

class Transaction(models.Model):
    STATUS_CHOICES = [
        ('completado', 'Completado'),
        ('pendiente', 'Pendiente'),
        ('parcial', 'Parcial'),
    ]

    date = models.DateField(verbose_name="Fecha")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='transactions', verbose_name="Organización")
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transactions', verbose_name="Cuenta")
    reference_number = models.CharField(max_length=100, blank=True, null=True, verbose_name="Número de referencia")
    description = models.TextField(verbose_name="Descripción")
    notes = models.TextField(blank=True, null=True, verbose_name="Notas")
    
    categories = models.ManyToManyField(Category, blank=True, related_name='transactions', verbose_name="Categorías")
    cost_center = models.ForeignKey(CostCenter, on_delete=models.SET_NULL, blank=True, null=True, related_name='transactions', verbose_name="Centro de Costo")
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=True, null=True, related_name='transactions', verbose_name="Proyecto")
    valuation = models.ForeignKey(Valuation, on_delete=models.SET_NULL, blank=True, null=True, related_name='transactions', verbose_name="Valuación")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completado', verbose_name="Estado")
    
    amount_bs = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="Monto en Bolívares")
    amount_usd = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="Monto en Dólares")
    daily_rate = models.DecimalField(max_digits=20, decimal_places=4, verbose_name="Tasa del día")
    
    bank_fee_bs = models.DecimalField(max_digits=20, decimal_places=2, default=0, verbose_name="Comisión bancaria (Bs)")
    bank_fee_usd = models.DecimalField(max_digits=20, decimal_places=2, default=0, verbose_name="Comisión bancaria ($)")
    
    real_dollars = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True, verbose_name="Dólares")
    bank_fee_real_usd = models.DecimalField(max_digits=20, decimal_places=2, default=0, verbose_name="Comisión dólares ($)")

    amount_eur = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True, verbose_name="Euros")
    bank_fee_eur = models.DecimalField(max_digits=20, decimal_places=2, default=0, verbose_name="Comisión euros (€)")

    class Meta:
        verbose_name = "Transacción"
        verbose_name_plural = "Transacciones"

    def __str__(self):
        return f"{self.date} - {self.description[:50]}"


class TransactionAuditLog(models.Model):
    ACTION_CREATED = 'created'
    ACTION_UPDATED = 'updated'
    ACTION_DELETED = 'deleted'
    ACTION_CHOICES = [
        (ACTION_CREATED, 'Creada'),
        (ACTION_UPDATED, 'Editada'),
        (ACTION_DELETED, 'Eliminada'),
    ]

    transaction = models.ForeignKey(Transaction, on_delete=models.SET_NULL, blank=True, null=True, related_name='audit_logs', verbose_name="Transacción")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='transaction_audit_logs', verbose_name="Organización")
    transaction_description = models.CharField(max_length=255, blank=True, verbose_name="Descripción (registro histórico)")
    action = models.CharField(max_length=10, choices=ACTION_CHOICES, verbose_name="Acción")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='transaction_audit_logs', verbose_name="Usuario")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Fecha y hora")
    snapshot = models.JSONField(blank=True, null=True, verbose_name="Instantánea de la transacción")

    class Meta:
        verbose_name = "Registro de auditoría de transacción"
        verbose_name_plural = "Registros de auditoría de transacciones"
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.get_action_display()} · {self.transaction_description} · {self.timestamp:%d/%m/%Y %H:%M}"


class ProjectShareLink(models.Model):
    """Enlace público (sin login) de solo lectura hacia un proyecto. El token
    incluye una firma criptográfica (django.core.signing), pero además se
    valida contra este registro para poder revocar el enlace al eliminarlo."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='share_links', verbose_name="Proyecto")
    token = models.CharField(max_length=255, unique=True, verbose_name="Token")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='project_share_links', verbose_name="Creado por")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")

    class Meta:
        verbose_name = "Enlace público de proyecto"
        verbose_name_plural = "Enlaces públicos de proyecto"
        ordering = ['-created_at']

    def __str__(self):
        return f"Enlace de {self.project.name} ({self.created_at:%d/%m/%Y %H:%M})"
