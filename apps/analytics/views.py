"""
Analytics API views for predictive analytics and insights
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from apps.customers.models import Customer
from apps.tenants.models import Tenant
from utils.security import rate_limit, validate_request_data
from .predictive_analytics import (
    PredictiveAnalyticsEngine, 
    BehaviorPredictionEngine, 
    TrendAnalyzer
)
from .customer_segmentation import CustomerSegmentationEngine
from .churn_prediction import ChurnPredictionEngine


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@rate_limit(limit=30, window=60)
def customer_lifetime_value_prediction(request):
    """Predict customer lifetime value for all customers"""
    
    try:
        tenant = request.user.tenant
        customers = Customer.objects.filter(tenant=tenant)
        
        engine = PredictiveAnalyticsEngine()
        predictions = engine.predict_customer_lifetime_value(list(customers))
        
        return Response({
            'success': True,
            'data': predictions
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@rate_limit(limit=60, window=60)
@validate_request_data(['customer_id'])
def customer_behavior_prediction(request):
    """Predict specific customer behaviors"""
    
    try:
        tenant = request.user.tenant
        customer_id = request.data.get('customer_id')
        customer = get_object_or_404(Customer, id=customer_id, tenant=tenant)
        
        engine = BehaviorPredictionEngine()
        
        # Get all predictions for this customer
        predictions = {
            'redemption_likelihood': engine.predict_redemption_likelihood(customer),
            'tier_advancement': engine.predict_tier_advancement(customer),
        }
        
        # Add next visit prediction
        analytics_engine = PredictiveAnalyticsEngine()
        predictions['next_visit'] = analytics_engine.predict_next_visit(customer)
        
        return Response({
            'success': True,
            'customer_id': customer_id,
            'predictions': predictions
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@rate_limit(limit=20, window=60)
def spending_patterns_analysis(request):
    """Analyze spending patterns and trends"""
    
    try:
        tenant = request.user.tenant
        
        engine = PredictiveAnalyticsEngine()
        patterns = engine.analyze_spending_patterns(tenant.id)
        
        return Response({
            'success': True,
            'patterns': patterns
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@rate_limit(limit=15, window=60)
def program_trends_analysis(request):
    """Analyze program trends and performance"""
    
    try:
        tenant = request.user.tenant
        months = int(request.GET.get('months', 6))
        
        analyzer = TrendAnalyzer()
        trends = analyzer.analyze_program_trends(tenant.id, months)
        
        return Response({
            'success': True,
            'trends': trends
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@rate_limit(limit=10, window=60)
def performance_forecast(request):
    """Forecast future program performance"""
    
    try:
        tenant = request.user.tenant
        forecast_months = int(request.GET.get('months', 3))
        
        analyzer = TrendAnalyzer()
        forecast = analyzer.forecast_future_performance(tenant.id, forecast_months)
        
        return Response({
            'success': True,
            'forecast': forecast
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@rate_limit(limit=20, window=60)
def comprehensive_analytics_dashboard(request):
    """Get comprehensive analytics for dashboard"""
    
    try:
        tenant = request.user.tenant
        
        # Initialize engines
        predictive_engine = PredictiveAnalyticsEngine()
        behavior_engine = BehaviorPredictionEngine()
        trend_analyzer = TrendAnalyzer()
        segmentation_engine = CustomerSegmentationEngine()
        churn_engine = ChurnPredictionEngine()
        
        # Get customers
        customers = Customer.objects.filter(tenant=tenant)
        
        # Comprehensive analytics
        analytics_data = {
            'overview': {
                'total_customers': customers.count(),
                'analysis_date': timezone.now().isoformat()
            },
            'clv_predictions': predictive_engine.predict_customer_lifetime_value(list(customers[:50])),
            'spending_patterns': predictive_engine.analyze_spending_patterns(tenant.id),
            'program_trends': trend_analyzer.analyze_program_trends(tenant.id, 3),
            'customer_segments': segmentation_engine.segment_customers(tenant.id),
            'churn_analysis': churn_engine.analyze_churn_risk(tenant.id)
        }
        
        return Response({
            'success': True,
            'analytics': analytics_data
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# UI Views for Analytics Dashboard

@login_required
def analytics_dashboard(request):
    """Analytics dashboard UI"""
    return render(request, 'analytics/dashboard.html', {
        'page_title': 'Analytics Dashboard'
    })


@login_required
def predictive_insights(request):
    """Predictive insights UI"""
    return render(request, 'analytics/predictive_insights.html', {
        'page_title': 'Predictive Insights'
    })


@login_required
def customer_analytics(request):
    """Customer analytics UI"""
    return render(request, 'analytics/customer_analytics.html', {
        'page_title': 'Customer Analytics'
    })