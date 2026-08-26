from django.contrib import admin
from .models import (
    Organization, OrganizationAccess, Account, Category, 
    Project, Valuation, Transaction, ProjectOrganizationAccess, ProjectUserAccess, CostCenter
)

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)

@admin.register(OrganizationAccess)
class OrganizationAccessAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'organization')
    list_filter = ('organization', 'user')
    search_fields = ('user__username', 'organization__name')

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('id', 'organization', 'name', 'currency', 'created_at')
    list_filter = ('organization', 'currency')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'organization', 'color')
    list_filter = ('organization',)
    search_fields = ('name',)

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'organization')
    list_filter = ('organization',)
    search_fields = ('name',)

@admin.register(ProjectOrganizationAccess)
class ProjectOrganizationAccessAdmin(admin.ModelAdmin):
    list_display = ('id', 'project', 'organization')
    list_filter = ('project', 'organization')
    search_fields = ('project__name', 'organization__name')

@admin.register(ProjectUserAccess)
class ProjectUserAccessAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'project')
    list_filter = ('user', 'project')
    search_fields = ('user__username', 'project__name')

@admin.register(Valuation)
class ValuationAdmin(admin.ModelAdmin):
    list_display = ('id', 'project', 'name', 'amount_usd', 'amount_bs')
    list_filter = ('project__organization',)

@admin.register(CostCenter)
class CostCenterAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'name', 'organization')
    list_filter = ('organization',)
    search_fields = ('code', 'name')

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'date', 'organization', 'account', 'cost_center', 'amount_bs', 'amount_usd', 'status')
    list_filter = ('organization', 'status', 'date', 'cost_center')
    search_fields = ('description', 'reference_number')
    date_hierarchy = 'date'
