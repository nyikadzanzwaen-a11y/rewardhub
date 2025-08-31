from django.contrib import admin
from .models import LoyaltyProgram, Tier, Rule, Transaction


@admin.register(LoyaltyProgram)
class LoyaltyProgramAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "active", "created_at")
    list_filter = ("active", "tenant", "created_at")
    search_fields = ("name", "tenant__name")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Tier)
class TierAdmin(admin.ModelAdmin):
    list_display = ("name", "program", "points_threshold", "created_at")
    list_filter = ("program", "created_at")
    search_fields = ("name", "program__name")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("program", "points_threshold")


@admin.register(Rule)
class RuleAdmin(admin.ModelAdmin):
    list_display = ("name", "program", "rule_type", "points", "location_based", "active", "priority")
    list_filter = ("rule_type", "location_based", "active", "program")
    search_fields = ("name", "program__name")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-priority", "created_at")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("loyalty_account", "points", "transaction_type", "status", "timestamp")
    list_filter = ("transaction_type", "status", "timestamp")
    search_fields = ("loyalty_account__customer__user__email", "description")
    readonly_fields = ("id", "timestamp")
    ordering = ("-timestamp",)