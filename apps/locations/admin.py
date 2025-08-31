from django.contrib import admin
from .models import Location, CheckIn


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "address", "radius_m", "created_at")
    list_filter = ("tenant", "created_at")
    search_fields = ("name", "address", "tenant__name")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(CheckIn)
class CheckInAdmin(admin.ModelAdmin):
    list_display = ("customer", "location", "verified", "timestamp")
    list_filter = ("verified", "location", "timestamp")
    search_fields = ("customer__user__email", "location__name")
    readonly_fields = ("id", "timestamp")
    ordering = ("-timestamp",)
    
    actions = ["verify_checkins"]
    
    def verify_checkins(self, request, queryset):
        verified_count = 0
        for checkin in queryset:
            if checkin.verify():
                verified_count += 1
        self.message_user(request, f"Verified {verified_count} check-ins")
    verify_checkins.short_description = "Verify selected check-ins"