from django.contrib import admin
from .models import Tenant, TenantSettings


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "subdomain", "active", "created_at")
    list_filter = ("active", "created_at")
    search_fields = ("name", "subdomain")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(TenantSettings)
class TenantSettingsAdmin(admin.ModelAdmin):
    list_display = ("tenant", "get_tenant_name")
    readonly_fields = ("tenant",)
    
    def get_tenant_name(self, obj):
        return obj.tenant.name
    get_tenant_name.short_description = "Tenant Name"