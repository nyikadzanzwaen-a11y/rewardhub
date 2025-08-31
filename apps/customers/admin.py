from django.contrib import admin
from .models import Customer, CustomerTenantMembership, LoyaltyAccount


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("user", "get_email", "get_memberships_count", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__email", "user__first_name", "user__last_name")
    readonly_fields = ("id", "created_at", "updated_at")
    
    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = "Email"
    
    def get_memberships_count(self, obj):
        return obj.tenant_memberships.count()
    get_memberships_count.short_description = "Active Memberships"


@admin.register(CustomerTenantMembership)
class CustomerTenantMembershipAdmin(admin.ModelAdmin):
    list_display = ("customer", "tenant", "member_id", "get_points_balance", "joined_at", "active")
    list_filter = ("tenant", "active", "joined_at")
    search_fields = ("customer__user__email", "tenant__business_name", "member_id")
    readonly_fields = ("id", "member_id", "joined_at", "updated_at")
    
    def get_points_balance(self, obj):
        return obj.get_points_balance()
    get_points_balance.short_description = "Points Balance"


@admin.register(LoyaltyAccount)
class LoyaltyAccountAdmin(admin.ModelAdmin):
    list_display = ("get_customer", "get_tenant", "program", "points_balance", "lifetime_points", "tier", "last_activity")
    list_filter = ("program", "tier", "created_at")
    search_fields = ("membership__customer__user__email", "membership__tenant__business_name", "program__name")
    readonly_fields = ("id", "created_at", "updated_at")
    
    def get_customer(self, obj):
        return obj.membership.customer.user.email
    get_customer.short_description = "Customer"
    
    def get_tenant(self, obj):
        return obj.membership.tenant.business_name
    get_tenant.short_description = "Tenant"
    
    actions = ["adjust_points"]
    
    def adjust_points(self, request, queryset):
        # This would open a form to adjust points
        # For now, just a placeholder
        self.message_user(request, f"Selected {queryset.count()} accounts for point adjustment")
    adjust_points.short_description = "Adjust points for selected accounts"