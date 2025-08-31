import uuid
from django.db import models
from django.utils import timezone
from django.conf import settings


class LoyaltyProgram(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE, related_name="loyalty_programs")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "loyalty_program"

    def __str__(self):
        return f"{self.name} ({self.tenant.name})"

    def activate(self):
        self.active = True
        self.save()

    def deactivate(self):
        self.active = False
        self.save()

    def get_active_rules(self):
        return self.rules.filter(active=True, start_date__lte=timezone.now(), end_date__gte=timezone.now())


class Tier(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    program = models.ForeignKey(LoyaltyProgram, on_delete=models.CASCADE, related_name="tiers")
    name = models.CharField(max_length=255)
    points_threshold = models.IntegerField(default=0)
    benefits = models.JSONField(default=dict, blank=True)
    icon = models.ImageField(upload_to="tier_icons/", blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "loyalty_tier"
        ordering = ["points_threshold"]

    def __str__(self):
        return f"{self.name} ({self.points_threshold} pts)"

    def get_customers(self):
        return self.loyalty_accounts.all()


class Rule(models.Model):
    RULE_TYPES = [
        ("earn", "Point Earning"),
        ("redeem", "Point Redemption"),
        ("bonus", "Bonus Points"),
        ("location", "Location-based"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    program = models.ForeignKey(LoyaltyProgram, on_delete=models.CASCADE, related_name="rules")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    rule_type = models.CharField(max_length=20, choices=RULE_TYPES, default="earn")
    conditions = models.JSONField(default=dict, blank=True)
    actions = models.JSONField(default=dict, blank=True)
    points = models.IntegerField(default=0)
    location_based = models.BooleanField(default=False)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)
    priority = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "loyalty_rule"
        ordering = ["-priority", "created_at"]

    def __str__(self):
        return f"{self.name} ({self.rule_type})"

    def is_applicable(self, customer, action_data=None, location=None):
        """Check if rule applies to customer and action"""
        if not self.active:
            return False
        
        now = timezone.now()
        if self.start_date > now or (self.end_date and self.end_date < now):
            return False
            
        if self.location_based and not location:
            return False
            
        # Check conditions against customer data and action
        # This would contain business logic for rule evaluation
        return True

    def execute_action(self, customer, action_data=None, location=None):
        """Execute the rule's action"""
        if not self.is_applicable(customer, action_data, location):
            return None
            
        # Execute the action defined in self.actions
        # This would contain the business logic for point allocation
        return self.points


class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ("earn", "Points Earned"),
        ("redeem", "Points Redeemed"),
        ("expire", "Points Expired"),
        ("adjust", "Manual Adjustment"),
        ("bonus", "Bonus Points"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loyalty_account = models.ForeignKey("customers.LoyaltyAccount", on_delete=models.CASCADE, related_name="transactions")
    points = models.IntegerField()
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    description = models.TextField(blank=True)
    reference = models.CharField(max_length=255, blank=True)
    location = models.ForeignKey("locations.Location", on_delete=models.SET_NULL, null=True, blank=True)
    rule_applied = models.ForeignKey(Rule, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="completed")

    class Meta:
        db_table = "loyalty_transaction"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.transaction_type}: {self.points} pts"

    def verify(self):
        """Verify transaction integrity"""
        self.status = "completed"
        self.save()

    def cancel(self):
        """Cancel transaction"""
        self.status = "cancelled"
        self.save()

    def get_location_data(self):
        """Get location data if available"""
        if self.location:
            return {
                "name": self.location.name,
                "coordinates": [self.location.point.x, self.location.point.y] if self.location.point else None
            }
        return None