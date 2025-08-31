from rest_framework import serializers
from .models import AIRecommendation, ChurnPrediction


class AIRecommendationSerializer(serializers.ModelSerializer):
    customer_email = serializers.CharField(source='customer.user.email', read_only=True)
    
    class Meta:
        model = AIRecommendation
        fields = ['id', 'customer_email', 'content', 'recommendation_type', 'confidence_score', 
                 'viewed', 'accepted', 'created_at']
        read_only_fields = ['id', 'customer_email', 'created_at']


class ChurnPredictionSerializer(serializers.ModelSerializer):
    customer_email = serializers.CharField(source='customer.user.email', read_only=True)
    
    class Meta:
        model = ChurnPrediction
        fields = ['id', 'customer_email', 'churn_risk', 'risk_level', 'factors', 
                 'suggested_actions', 'created_at', 'updated_at']
        read_only_fields = ['id', 'customer_email', 'created_at', 'updated_at']