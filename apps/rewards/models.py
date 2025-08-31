import uuid
from django.db import models
from django.utils import timezone


class Reward(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    program = models.ForeignKey("loyalty.LoyaltyProgram", on_delete=models.CASCADE, related_name="rewards")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="reward_images/", blank=True, null=True)
    point_cost = models.IntegerField()
    quantity_available = models.IntegerField(null=True, blank=True, help_text="Leave blank for unlimited")
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rewards_reward"
        ordering = ["point_cost", "name"]

    def __str__(self):
        return f"{self.name} ({self.point_cost} pts)"

    def is_available(self):
        """Check if reward is currently available"""
        if not self.active:
            return False
            
        now = timezone.now()
        if self.start_date > now or (self.end_date and self.end_date < now):
            return False
            
        if self.quantity_available is not None and self.quantity_available <= 0:
            return False
            
        return True

    def reduce_inventory(self):
        """Reduce available quantity by 1"""
        if self.quantity_available is not None:
            if self.quantity_available > 0:
                self.quantity_available -= 1
                self.save()
                return True
            return False
        return True  # Unlimited quantity

    def is_eligible_for_customer(self, customer):
        """Check if customer is eligible for this reward"""
        if not self.is_available():
            return False
            
        try:
            # Check if customer has enough points
            if customer.loyalty_account.points_balance < self.point_cost:
                return False
        except:
            return False
            
        # Could add tier restrictions, etc. here
        return True


class Redemption(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("fulfilled", "Fulfilled"),
        ("cancelled", "Cancelled"),
        ("expired", "Expired"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey("customers.Customer", on_delete=models.CASCADE, related_name="redemptions")
    reward = models.ForeignKey(Reward, on_delete=models.CASCADE, related_name="redemptions")
    points_used = models.IntegerField()
    redemption_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    fulfillment_details = models.JSONField(default=dict, blank=True)
    location = models.ForeignKey("locations.Location", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = "rewards_redemption"
        ordering = ["-redemption_date"]

    def __str__(self):
        return f"{self.customer.user.email} - {self.reward.name}"

    def fulfill(self):
        """Mark redemption as fulfilled"""
        self.status = "fulfilled"
        self.fulfillment_details["fulfilled_at"] = timezone.now().isoformat()
        self.save()

    def cancel(self):
        """Cancel redemption and refund points"""
        if self.status == "pending":
            self.status = "cancelled"
            self.save()
            
            # Refund points to customer
            try:
                self.customer.loyalty_account.add_points(
                    points=self.points_used,
                    description=f"Refund for cancelled redemption: {self.reward.name}"
                )
                
                # Restore inventory if applicable
                if self.reward.quantity_available is not None:
                    self.reward.quantity_available += 1
                    self.reward.save()
                    
            except Exception:
                pass
                
            return True
        return False

    def expire(self):
        """Mark redemption as expired"""
        self.status = "expired"
        self.save()