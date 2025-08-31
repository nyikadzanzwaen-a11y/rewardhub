from rest_framework import serializers
from .models import Reward, Redemption


class RewardSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source='program.name', read_only=True)
    is_available = serializers.SerializerMethodField()
    
    class Meta:
        model = Reward
        fields = ['id', 'name', 'description', 'image', 'point_cost', 'quantity_available', 
                 'start_date', 'end_date', 'active', 'program_name', 'is_available']
        read_only_fields = ['id', 'program_name', 'is_available']
    
    def get_is_available(self, obj):
        return obj.is_available()


class RedemptionSerializer(serializers.ModelSerializer):
    customer_email = serializers.CharField(source='customer.user.email', read_only=True)
    reward_name = serializers.CharField(source='reward.name', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    
    class Meta:
        model = Redemption
        fields = ['id', 'customer_email', 'reward_name', 'points_used', 'redemption_date', 
                 'status', 'location_name', 'fulfillment_details']
        read_only_fields = ['id', 'customer_email', 'reward_name', 'location_name', 'redemption_date']


class RedeemRewardSerializer(serializers.Serializer):
    reward_id = serializers.UUIDField()
    location_id = serializers.UUIDField(required=False)