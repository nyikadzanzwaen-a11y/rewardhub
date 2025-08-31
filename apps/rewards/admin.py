from django.contrib import admin
from .models import Reward, Redemption


@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    list_display = ("name", "program", "point_cost", "quantity_available", "active", "start_date", "end_date")
    list_filter = ("active", "program", "start_date", "end_date")
    search_fields = ("name", "program__name", "description")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("program", "point_cost")


@admin.register(Redemption)
class RedemptionAdmin(admin.ModelAdmin):
    list_display = ("customer", "reward", "points_used", "status", "redemption_date")
    list_filter = ("status", "redemption_date", "reward__program")
    search_fields = ("customer__user__email", "reward__name")
    readonly_fields = ("id", "redemption_date")
    ordering = ("-redemption_date",)
    
    actions = ["fulfill_redemptions", "cancel_redemptions"]
    
    def fulfill_redemptions(self, request, queryset):
        fulfilled_count = 0
        for redemption in queryset.filter(status="pending"):
            redemption.fulfill()
            fulfilled_count += 1
        self.message_user(request, f"Fulfilled {fulfilled_count} redemptions")
    fulfill_redemptions.short_description = "Fulfill selected redemptions"
    
    def cancel_redemptions(self, request, queryset):
        cancelled_count = 0
        for redemption in queryset.filter(status="pending"):
            if redemption.cancel():
                cancelled_count += 1
        self.message_user(request, f"Cancelled {cancelled_count} redemptions")
    cancel_redemptions.short_description = "Cancel selected redemptions"