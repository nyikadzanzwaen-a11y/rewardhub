"""
Admin Dashboard views for comprehensive system management
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from apps.customers.models import Customer
from apps.loyalty.models import LoyaltyProgram, Tier, Rule, Transaction
from apps.locations.models import Location
from apps.rewards.models import Reward
from apps.tenants.models import Tenant
from apps.analytics.customer_segmentation import CustomerSegmentationEngine
from apps.analytics.churn_prediction import ChurnPredictionEngine
from apps.analytics.predictive_analytics import PredictiveAnalyticsEngine
from apps.gamification.models import Badge, Challenge
from utils.security import rate_limit


def is_admin_user(user):
    """Check if user has admin privileges"""
    return user.is_staff or user.is_superuser


@login_required
@user_passes_test(is_admin_user)
def admin_dashboard_home(request):
    """Main admin dashboard"""
    
    tenant = request.user.tenant if hasattr(request.user, 'tenant') else None
    
    # Get key metrics
    total_customers = Customer.objects.filter(tenant=tenant).count() if tenant else Customer.objects.count()
    total_transactions = Transaction.objects.filter(
        loyalty_account__customer__tenant=tenant
    ).count() if tenant else Transaction.objects.count()
    
    active_programs = LoyaltyProgram.objects.filter(
        tenant=tenant, is_active=True
    ).count() if tenant else LoyaltyProgram.objects.filter(is_active=True).count()
    
    total_rewards = Reward.objects.filter(
        tenant=tenant
    ).count() if tenant else Reward.objects.count()
    
    # Recent activity
    recent_transactions = Transaction.objects.filter(
        loyalty_account__customer__tenant=tenant
    ).order_by('-timestamp')[:10] if tenant else Transaction.objects.order_by('-timestamp')[:10]
    
    context = {
        'page_title': 'Admin Dashboard',
        'total_customers': total_customers,
        'total_transactions': total_transactions,
        'active_programs': active_programs,
        'total_rewards': total_rewards,
        'recent_transactions': recent_transactions,
        'tenant': tenant
    }
    
    return render(request, 'admin_dashboard/home.html', context)


@login_required
@user_passes_test(is_admin_user)
def program_configuration(request):
    """Program configuration interface"""
    
    tenant = request.user.tenant if hasattr(request.user, 'tenant') else None
    
    # Get programs, tiers, and rules
    programs = LoyaltyProgram.objects.filter(tenant=tenant) if tenant else LoyaltyProgram.objects.all()
    tiers = Tier.objects.filter(program__tenant=tenant) if tenant else Tier.objects.all()
    rules = Rule.objects.filter(program__tenant=tenant) if tenant else Rule.objects.all()
    
    context = {
        'page_title': 'Program Configuration',
        'programs': programs,
        'tiers': tiers,
        'rules': rules,
        'tenant': tenant
    }
    
    return render(request, 'admin_dashboard/program_config.html', context)


@login_required
@user_passes_test(is_admin_user)
def customer_management(request):
    """Customer management interface"""
    
    tenant = request.user.tenant if hasattr(request.user, 'tenant') else None
    
    # Get customers with pagination
    customers = Customer.objects.filter(tenant=tenant).select_related(
        'loyalty_account', 'loyalty_account__tier'
    ) if tenant else Customer.objects.select_related('loyalty_account', 'loyalty_account__tier')
    
    # Filter options
    search_query = request.GET.get('search', '')
    tier_filter = request.GET.get('tier', '')
    status_filter = request.GET.get('status', '')
    
    if search_query:
        customers = customers.filter(
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )
    
    if tier_filter:
        customers = customers.filter(loyalty_account__tier__name=tier_filter)
    
    if status_filter == 'active':
        customers = customers.filter(is_active=True)
    elif status_filter == 'inactive':
        customers = customers.filter(is_active=False)
    
    # Get available tiers for filter
    available_tiers = Tier.objects.filter(
        program__tenant=tenant
    ).values_list('name', flat=True).distinct() if tenant else Tier.objects.values_list('name', flat=True).distinct()
    
    context = {
        'page_title': 'Customer Management',
        'customers': customers[:100],  # Limit for performance
        'search_query': search_query,
        'tier_filter': tier_filter,
        'status_filter': status_filter,
        'available_tiers': available_tiers,
        'tenant': tenant
    }
    
    return render(request, 'admin_dashboard/customer_management.html', context)


@login_required
@user_passes_test(is_admin_user)
def analytics_reporting(request):
    """Analytics and reporting dashboard"""
    
    tenant = request.user.tenant if hasattr(request.user, 'tenant') else None
    
    context = {
        'page_title': 'Analytics & Reporting',
        'tenant': tenant
    }
    
    return render(request, 'admin_dashboard/analytics_reporting.html', context)


@login_required
@user_passes_test(is_admin_user)
def campaign_management(request):
    """Location-based campaign management"""
    
    tenant = request.user.tenant if hasattr(request.user, 'tenant') else None
    
    # Get locations
    locations = Location.objects.filter(tenant=tenant) if tenant else Location.objects.all()
    
    context = {
        'page_title': 'Campaign Management',
        'locations': locations,
        'tenant': tenant
    }
    
    return render(request, 'admin_dashboard/campaign_management.html', context)


@login_required
@user_passes_test(is_admin_user)
def ai_insights_panel(request):
    """AI insights and recommendations panel"""
    
    tenant = request.user.tenant if hasattr(request.user, 'tenant') else None
    
    context = {
        'page_title': 'AI Insights Panel',
        'tenant': tenant
    }
    
    return render(request, 'admin_dashboard/ai_insights.html', context)


@login_required
@user_passes_test(is_admin_user)
def security_audit_controls(request):
    """Security and audit controls"""
    
    tenant = request.user.tenant if hasattr(request.user, 'tenant') else None
    
    context = {
        'page_title': 'Security & Audit Controls',
        'tenant': tenant
    }
    
    return render(request, 'admin_dashboard/security_audit.html', context)


@login_required
@user_passes_test(is_admin_user)
def multitenant_management(request):
    """Multi-tenant management interface"""
    
    # Only superusers can access multi-tenant management
    if not request.user.is_superuser:
        messages.error(request, 'Access denied. Superuser privileges required.')
        return redirect('admin_dashboard:home')
    
    tenants = Tenant.objects.all().annotate(
        customer_count=Count('customers'),
        program_count=Count('loyalty_programs')
    )
    
    context = {
        'page_title': 'Multi-Tenant Management',
        'tenants': tenants
    }
    
    return render(request, 'admin_dashboard/multitenant_management.html', context)


# API Endpoints for Admin Dashboard

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@rate_limit(limit=30, window=60)
def dashboard_metrics_api(request):
    """Get dashboard metrics via API"""
    
    try:
        tenant = request.user.tenant if hasattr(request.user, 'tenant') else None
        
        # Basic metrics
        if tenant:
            customers = Customer.objects.filter(tenant=tenant)
            transactions = Transaction.objects.filter(loyalty_account__customer__tenant=tenant)
            programs = LoyaltyProgram.objects.filter(tenant=tenant)
        else:
            customers = Customer.objects.all()
            transactions = Transaction.objects.all()
            programs = LoyaltyProgram.objects.all()
        
        # Calculate metrics
        total_customers = customers.count()
        active_customers = customers.filter(is_active=True).count()
        total_transactions = transactions.count()
        total_points_issued = transactions.filter(transaction_type='earn').aggregate(
            total=Sum('points'))['total'] or 0
        total_points_redeemed = transactions.filter(transaction_type='redeem').aggregate(
            total=Sum('points'))['total'] or 0
        
        # Recent activity
        last_30_days = timezone.now() - timezone.timedelta(days=30)
        recent_customers = customers.filter(created_at__gte=last_30_days).count()
        recent_transactions = transactions.filter(timestamp__gte=last_30_days).count()
        
        # Program metrics
        active_programs = programs.filter(is_active=True).count()
        
        return Response({
            'success': True,
            'metrics': {
                'customers': {
                    'total': total_customers,
                    'active': active_customers,
                    'new_last_30_days': recent_customers
                },
                'transactions': {
                    'total': total_transactions,
                    'last_30_days': recent_transactions,
                    'points_issued': total_points_issued,
                    'points_redeemed': total_points_redeemed
                },
                'programs': {
                    'total': programs.count(),
                    'active': active_programs
                }
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@rate_limit(limit=20, window=60)
def ai_insights_api(request):
    """Get AI insights via API"""
    
    try:
        tenant = request.user.tenant if hasattr(request.user, 'tenant') else None
        
        if not tenant:
            return Response({
                'success': False,
                'error': 'Tenant required for AI insights'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Initialize AI engines
        segmentation_engine = CustomerSegmentationEngine()
        churn_engine = ChurnPredictionEngine()
        predictive_engine = PredictiveAnalyticsEngine()
        
        # Get AI insights
        customer_segments = segmentation_engine.segment_customers(tenant.id)
        churn_analysis = churn_engine.analyze_churn_risk(tenant.id)
        
        # Get sample customers for CLV prediction
        sample_customers = Customer.objects.filter(tenant=tenant)[:20]
        clv_predictions = predictive_engine.predict_customer_lifetime_value(list(sample_customers))
        
        return Response({
            'success': True,
            'insights': {
                'customer_segmentation': customer_segments,
                'churn_analysis': churn_analysis,
                'clv_predictions': clv_predictions,
                'generated_at': timezone.now().isoformat()
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@rate_limit(limit=10, window=60)
def customer_action_api(request):
    """Perform actions on customers (adjust points, change tier, etc.)"""
    
    try:
        tenant = request.user.tenant if hasattr(request.user, 'tenant') else None
        
        customer_id = request.data.get('customer_id')
        action = request.data.get('action')
        value = request.data.get('value')
        
        if not all([customer_id, action]):
            return Response({
                'success': False,
                'error': 'customer_id and action are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        customer = get_object_or_404(Customer, id=customer_id, tenant=tenant)
        
        if action == 'adjust_points':
            points = int(value)
            Transaction.objects.create(
                loyalty_account=customer.loyalty_account,
                transaction_type='earn' if points > 0 else 'redeem',
                points=abs(points),
                description=f'Admin adjustment: {points} points',
                metadata={'admin_user': request.user.email, 'manual_adjustment': True}
            )
            
            # Update balance
            customer.loyalty_account.points_balance += points
            customer.loyalty_account.save()
            
            return Response({
                'success': True,
                'message': f'Adjusted {customer.email} points by {points}'
            })
        
        elif action == 'toggle_status':
            customer.is_active = not customer.is_active
            customer.save()
            
            return Response({
                'success': True,
                'message': f'Customer {customer.email} status changed to {"active" if customer.is_active else "inactive"}'
            })
        
        else:
            return Response({
                'success': False,
                'error': 'Invalid action'
            }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
