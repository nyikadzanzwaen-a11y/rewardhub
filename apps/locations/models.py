import uuid
import math
from django.db import models
from django.utils import timezone


class Location(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE, related_name="locations")
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    radius_m = models.FloatField(default=100.0, help_text="Geofence radius in meters")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "locations_location"
        indexes = [
            models.Index(fields=["latitude", "longitude"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.tenant.name})"

    def is_point_within(self, lat, lng):
        """Check if a point is within this location's geofence using Haversine formula"""
        return self.calculate_distance(lat, lng) <= self.radius_m

    def calculate_distance(self, lat, lng):
        """Calculate distance between two points using Haversine formula"""
        R = 6371000  # Earth's radius in meters
        lat1_rad = math.radians(self.latitude)
        lat2_rad = math.radians(lat)
        delta_lat = math.radians(lat - self.latitude)
        delta_lng = math.radians(lng - self.longitude)
        
        a = (math.sin(delta_lat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * 
             math.sin(delta_lng / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    @classmethod
    def get_nearby_locations(cls, lat, lng, distance_m=1000, tenant=None):
        """Get locations within distance of a point"""
        queryset = cls.objects.all()
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        
        nearby = []
        for location in queryset:
            if location.calculate_distance(lat, lng) <= distance_m:
                nearby.append(location)
        return nearby


class CheckIn(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey("customers.Customer", on_delete=models.CASCADE, related_name="checkins")
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="checkins")
    latitude = models.FloatField()
    longitude = models.FloatField()
    timestamp = models.DateTimeField(default=timezone.now)
    verified = models.BooleanField(default=False)
    device_info = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "locations_checkin"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.customer.user.email} @ {self.location.name}"

    def verify(self):
        """Verify check-in is within location geofence"""
        if self.location.is_point_within(self.latitude, self.longitude):
            self.verified = True
            self.save()
            return True
        return False

    def process_rules(self):
        """Process applicable loyalty rules for this check-in"""
        from apps.loyalty.models import Rule
        
        # Get active location-based rules for this tenant
        rules = Rule.objects.filter(
            program__tenant=self.customer.tenant,
            active=True,
            location_based=True,
            start_date__lte=timezone.now()
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=timezone.now())
        )
        
        points_earned = 0
        for rule in rules:
            if rule.is_applicable(self.customer, {"checkin": self}, self.location):
                points = rule.execute_action(self.customer, {"checkin": self}, self.location)
                if points:
                    try:
                        self.customer.loyalty_account.add_points(
                            points=points,
                            description=f"Check-in at {self.location.name}",
                            location=self.location,
                            rule=rule
                        )
                        points_earned += points
                    except Exception:
                        # Handle case where customer doesn't have loyalty account
                        pass
        
        return points_earned