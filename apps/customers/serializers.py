from rest_framework import serializers
from .models import Customer, CustomerTenantMembership, LoyaltyAccount
from apps.accounts.serializers import UserSerializer


class CustomerSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    active_memberships_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Customer
        fields = ['id', 'user', 'phone', 'date_of_birth', 'address', 'city', 'state', 'postal_code', 'country', 'active_memberships_count', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_active_memberships_count(self, obj):
        return obj.get_active_memberships().count()


class CustomerTenantMembershipSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source='tenant.business_name', read_only=True)
    points_balance = serializers.SerializerMethodField()
    tier_name = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomerTenantMembership
        fields = ['id', 'tenant', 'tenant_name', 'member_id', 'points_balance', 'tier_name', 'joined_at', 'active']
        read_only_fields = ['id', 'member_id', 'joined_at']
    
    def get_points_balance(self, obj):
        return obj.get_points_balance()
    
    def get_tier_name(self, obj):
        tier = obj.get_current_tier()
        return tier.name if tier else None


class LoyaltyAccountSerializer(serializers.ModelSerializer):
    customer_email = serializers.CharField(source='membership.customer.user.email', read_only=True)
    tenant_name = serializers.CharField(source='membership.tenant.business_name', read_only=True)
    tier_name = serializers.CharField(source='tier.name', read_only=True)
    
    class Meta:
        model = LoyaltyAccount
        fields = ['id', 'customer_email', 'tenant_name', 'program', 'points_balance', 'lifetime_points', 'tier_name', 'last_activity']
        read_only_fields = ['id', 'customer_email', 'tenant_name', 'tier_name', 'last_activity']


class PointsBalanceSerializer(serializers.Serializer):
    points_balance = serializers.IntegerField()
    lifetime_points = serializers.IntegerField()
    tier = serializers.CharField()
    
    
class PointAdjustmentSerializer(serializers.Serializer):
    points = serializers.IntegerField()
    description = serializers.CharField(max_length=255, required=False, default="Manual adjustment")