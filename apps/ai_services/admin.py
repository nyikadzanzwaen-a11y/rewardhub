from django.contrib import admin
from .models import AIRecommendation, ChurnPrediction


@admin.register(AIRecommendation)
class AIRecommendationAdmin(admin.ModelAdmin):
    list_display = ("customer", "recommendation_type", "confidence_score", "viewed", "accepted", "created_at")
    list_filter = ("recommendation_type", "viewed", "accepted", "created_at")
    search_fields = ("customer__user__email", "content")
    readonly_fields = ("id", "created_at")
    ordering = ("-created_at",)


@admin.register(ChurnPrediction)
class ChurnPredictionAdmin(admin.ModelAdmin):
    list_display = ("customer", "churn_risk", "risk_level", "created_at", "updated_at")
    list_filter = ("risk_level", "created_at")
    search_fields = ("customer__user__email",)
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-churn_risk",)