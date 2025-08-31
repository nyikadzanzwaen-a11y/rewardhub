from rest_framework import serializers
from .models import LoyaltyProgram, Tier, Rule, Transaction


class TierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tier
        fields = ['id', 'name', 'points_threshold', 'benefits', 'icon']
        read_only_fields = ['id']


class LoyaltyProgramSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    tiers = TierSerializer(many=True, read_only=True)
    
    class Meta:
        model = LoyaltyProgram
        fields = ['id', 'name', 'description', 'active', 'tenant_name', 'tiers', 'created_at']
        read_only_fields = ['id', 'tenant_name', 'created_at']


class RuleSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source='program.name', read_only=True)
    
    class Meta:
        model = Rule
        fields = ['id', 'name', 'description', 'rule_type', 'conditions', 'actions', 
                 'points', 'location_based', 'start_date', 'end_date', 'active', 
                 'priority', 'program_name']
        read_only_fields = ['id', 'program_name']


class TransactionSerializer(serializers.ModelSerializer):
    customer_email = serializers.CharField(source='loyalty_account.customer.user.email', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    rule_name = serializers.CharField(source='rule_applied.name', read_only=True)
    
    class Meta:
        model = Transaction
        fields = ['id', 'customer_email', 'points', 'transaction_type', 'description', 
                 'location_name', 'rule_name', 'timestamp', 'status']
        read_only_fields = ['id', 'customer_email', 'location_name', 'rule_name', 'timestamp']