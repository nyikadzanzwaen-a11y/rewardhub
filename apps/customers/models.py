import uuid
from django.db import models
from django.utils import timezone
from django.conf import settings


class Customer(models.Model):
    """Base customer profile - one per user"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="customer_profile")
    phone = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default='USA')
    preferences = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "customers_customer"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.email}"

    def get_tenant_memberships(self):
        """Get all tenant memberships for this customer"""
        return self.tenant_memberships.all()

    def get_active_memberships(self):
        """Get active tenant memberships"""
        return self.tenant_memberships.filter(active=True)


class CustomerTenantMembership(models.Model):
    """Many-to-many relationship between customers and tenants - like separate wallets"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="tenant_memberships")
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE, related_name="customer_memberships")
    member_id = models.CharField(max_length=50, blank=True)  # Custom member ID for this tenant
    profile_data = models.JSONField(default=dict, blank=True)  # Tenant-specific profile data
    segment_tags = models.JSONField(default=list, blank=True)
    ai_insights = models.JSONField(default=dict, blank=True)
    active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(default=timezone.now)
    last_activity = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "customers_tenantmembership"
        unique_together = ["customer", "tenant"]

    def __str__(self):
        return f"{self.customer.user.email} @ {self.tenant.name}"

    def get_loyalty_account(self):
        """Get loyalty account for this tenant membership"""
        return self.loyalty_accounts.first()

    def get_current_tier(self):
        """Get customer's current tier for this tenant"""
        loyalty_account = self.get_loyalty_account()
        return loyalty_account.tier if loyalty_account else None

    def get_points_balance(self):
        """Get points balance for this tenant"""
        loyalty_account = self.get_loyalty_account()
        return loyalty_account.points_balance if loyalty_account else 0

    def get_recent_transactions(self, limit=10):
        """Get recent transactions for this tenant"""
        loyalty_account = self.get_loyalty_account()
        if loyalty_account:
            return loyalty_account.transactions.all()[:limit]
        return []


class LoyaltyAccount(models.Model):
    """Loyalty account for a specific customer-tenant membership"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    membership = models.ForeignKey(CustomerTenantMembership, on_delete=models.CASCADE, related_name="loyalty_accounts")
    program = models.ForeignKey("loyalty.LoyaltyProgram", on_delete=models.CASCADE, related_name="loyalty_accounts")
    points_balance = models.IntegerField(default=0)
    lifetime_points = models.IntegerField(default=0)
    tier = models.ForeignKey("loyalty.Tier", on_delete=models.SET_NULL, null=True, blank=True, related_name="loyalty_accounts")
    last_activity = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "customers_loyaltyaccount"
        unique_together = ["membership", "program"]

    def __str__(self):
        return f"{self.membership.customer.user.email} @ {self.membership.tenant.name} - {self.points_balance} pts"

    def add_points(self, points, description="", location=None, rule=None):
        """Add points to account"""
        from apps.loyalty.models import Transaction
        
        self.points_balance += points
        self.lifetime_points += points
        self.last_activity = timezone.now()
        self.save()
        
        # Create transaction record
        Transaction.objects.create(
            loyalty_account=self,
            points=points,
            transaction_type="earn",
            description=description,
            location=location,
            rule_applied=rule
        )
        
        # Check for tier upgrade
        self.check_tier_eligibility()
        
        return self.points_balance

    def deduct_points(self, points, description="", location=None):
        """Deduct points from account"""
        from apps.loyalty.models import Transaction
        
        if self.points_balance < points:
            raise ValueError("Insufficient points balance")
            
        self.points_balance -= points
        self.last_activity = timezone.now()
        self.save()
        
        # Create transaction record
        Transaction.objects.create(
            loyalty_account=self,
            points=-points,
            transaction_type="redeem",
            description=description,
            location=location
        )
        
        return self.points_balance

    def check_tier_eligibility(self):
        """Check and upgrade tier if eligible"""
        eligible_tiers = self.program.tiers.filter(
            points_threshold__lte=self.lifetime_points
        ).order_by("-points_threshold")
        
        if eligible_tiers.exists():
            new_tier = eligible_tiers.first()
            if self.tier != new_tier:
                self.upgrade_tier(new_tier)

    def upgrade_tier(self, new_tier):
        """Upgrade customer to new tier"""
        old_tier = self.tier
        self.tier = new_tier
        self.save()
        
        # Could trigger notifications here
        return {"old_tier": old_tier, "new_tier": new_tier}