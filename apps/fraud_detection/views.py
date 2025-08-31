"""
Fraud detection API views
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required

from apps.customers.models import Customer
from apps.loyalty.models import Transaction
from utils.security import rate_limit, validate_request_data
from .ml_fraud_detector import FraudDetectionEngine


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@rate_limit(limit=20, window=60)
def analyze_transaction_risk(request):
    """Analyze fraud risk for a transaction"""
    
    try:
        tenant = request.user.tenant
        transaction_id = request.data.get('transaction_id')
        customer_id = request.data.get('customer_id')
        
        if not transaction_id or not customer_id:
            return Response({
                'success': False,
                'error': 'transaction_id and customer_id are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        customer = get_object_or_404(Customer, id=customer_id, tenant=tenant)
        transaction = get_object_or_404(Transaction, id=transaction_id, loyalty_account=customer.loyalty_account)
        
        # Initialize fraud detection engine
        fraud_engine = FraudDetectionEngine()
        
        # Analyze transaction risk
        risk_analysis = fraud_engine.analyze_transaction_risk(customer, transaction)
        
        return Response({
            'success': True,
            'transaction_id': transaction_id,
            'customer_id': customer_id,
            'risk_analysis': risk_analysis
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@rate_limit(limit=5, window=60)
def initialize_fraud_models(request):
    """Initialize fraud detection models for tenant"""
    
    try:
        tenant = request.user.tenant
        
        # Initialize fraud detection engine
        fraud_engine = FraudDetectionEngine()
        
        # Train models on tenant data
        initialization_results = fraud_engine.initialize_models(tenant.id)
        
        return Response({
            'success': True,
            'tenant_id': tenant.id,
            'initialization_results': initialization_results
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@rate_limit(limit=10, window=60)
def fraud_detection_report(request):
    """Generate fraud detection report"""
    
    try:
        tenant = request.user.tenant
        days = int(request.GET.get('days', 30))
        
        # Initialize fraud detection engine
        fraud_engine = FraudDetectionEngine()
        
        # Generate report
        report = fraud_engine.generate_fraud_report(tenant.id, days)
        
        return Response({
            'success': True,
            'report': report
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@rate_limit(limit=30, window=60)
def customer_risk_profile(request, customer_id):
    """Get risk profile for specific customer"""
    
    try:
        tenant = request.user.tenant
        customer = get_object_or_404(Customer, id=customer_id, tenant=tenant)
        
        # Initialize fraud detection engine
        fraud_engine = FraudDetectionEngine()
        
        # Get customer's recent transactions for analysis
        recent_transactions = Transaction.objects.filter(
            loyalty_account=customer.loyalty_account
        ).order_by('-timestamp')[:10]
        
        risk_analyses = []
        for transaction in recent_transactions:
            risk_analysis = fraud_engine.analyze_transaction_risk(customer, transaction)
            risk_analyses.append({
                'transaction_id': transaction.id,
                'timestamp': transaction.timestamp.isoformat(),
                'points': transaction.points,
                'risk_analysis': risk_analysis
            })
        
        # Calculate overall risk profile
        high_risk_count = sum(1 for ra in risk_analyses if ra['risk_analysis']['risk_level'] == 'high')
        medium_risk_count = sum(1 for ra in risk_analyses if ra['risk_analysis']['risk_level'] == 'medium')
        
        overall_risk_level = 'high' if high_risk_count > 2 else 'medium' if medium_risk_count > 3 else 'low'
        
        return Response({
            'success': True,
            'customer_id': customer_id,
            'overall_risk_level': overall_risk_level,
            'recent_transactions_analysis': risk_analyses,
            'risk_summary': {
                'high_risk_transactions': high_risk_count,
                'medium_risk_transactions': medium_risk_count,
                'low_risk_transactions': len(risk_analyses) - high_risk_count - medium_risk_count
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# UI Views

@login_required
def fraud_detection_dashboard(request):
    """Fraud detection dashboard UI"""
    return render(request, 'fraud_detection/dashboard.html', {
        'page_title': 'Fraud Detection Dashboard'
    })


@login_required
def fraud_reports(request):
    """Fraud reports UI"""
    return render(request, 'fraud_detection/reports.html', {
        'page_title': 'Fraud Detection Reports'
    })
