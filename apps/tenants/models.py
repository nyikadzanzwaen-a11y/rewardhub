import uuid
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()


class Industry(models.Model):
    """Industry categories for tenant classification"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "tenants_industry"
        verbose_name_plural = "Industries"

    def __str__(self):
        return self.name


class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    business_name = models.CharField(max_length=255)
    subdomain = models.CharField(max_length=100, unique=True)
    industry = models.ForeignKey(Industry, on_delete=models.SET_NULL, null=True, blank=True)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    website = models.URLField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_tenants')
    active = models.BooleanField(default=True)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tenants_tenant"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return f"https://{self.subdomain}.rewardhub.com"

    def activate(self):
        self.active = True
        self.save()

    def deactivate(self):
        self.active = False
        self.save()


class Branch(models.Model):
    """Branch/Location model for multi-location businesses"""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='branches')
    name = models.CharField(max_length=255)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default='USA')
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    manager_name = models.CharField(max_length=255, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tenants_branch"
        unique_together = ['tenant', 'name']

    def __str__(self):
        return f"{self.tenant.name} - {self.name}"


class TenantSettings(models.Model):
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name="settings")
    branding_settings = models.JSONField(default=dict, blank=True)
    loyalty_settings = models.JSONField(default=dict, blank=True)
    security_settings = models.JSONField(default=dict, blank=True)
    notification_settings = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "tenants_tenantsettings"

    def __str__(self):
        return f"Settings for {self.tenant.name}"

    def update_settings(self, key, value):
        """Update a specific setting category"""
        if hasattr(self, f"{key}_settings"):
            current_settings = getattr(self, f"{key}_settings")
            current_settings.update(value)
            setattr(self, f"{key}_settings", current_settings)
            self.save()