# Required imports
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from utils.security import rate_limit, validate_request_data
from .models import Customer, CustomerTenantMembership, LoyaltyAccount
from .forms import CustomerRegistrationForm, TenantSelectionForm, CustomerProfileForm
from apps.tenants.models import Tenant
from apps.loyalty.models import LoyaltyProgram, Transaction
from apps.locations.models import Location, CheckIn
from apps.rewards.models import Reward, Redemption
import json
import math

# Customer Registration and Multi-Wallet Views
def customer_register(request):
    """Customer self-registration"""
    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                login(request, user)
                messages.success(request, 'Welcome to RewardHub! Please select businesses to join.')
                return redirect('customers:customer_select_tenants')
            except Exception as e:
                messages.error(request, f'Registration failed: {str(e)}')
    else:
        form = CustomerRegistrationForm()
    
    return render(request, 'customers/register.html', {'form': form})


@login_required
def customer_select_tenants(request):
    """Customer tenant selection for multi-wallet system"""
    try:
        customer = request.user.customer_profile
    except Customer.DoesNotExist:
        messages.error(request, 'Customer profile not found.')
        return redirect('customers:customer_register')
    
    if request.method == 'POST':
        form = TenantSelectionForm(request.POST, customer=customer)
        if form.is_valid():
            selected_tenant_ids = form.get_selected_tenants()
            created_count = 0
            
            for tenant_id in selected_tenant_ids:
                tenant = get_object_or_404(Tenant, id=tenant_id, active=True, verified=True)
                membership, created = CustomerTenantMembership.objects.get_or_create(
                    customer=customer,
                    tenant=tenant,
                    defaults={'member_id': f'CUST{customer.id.hex[:8].upper()}'}
                )
                
                if created:
                    # Create loyalty account for this membership
                    default_program = tenant.loyalty_programs.filter(active=True).first()
                    if default_program:
                        LoyaltyAccount.objects.create(
                            membership=membership,
                            program=default_program
                        )
                    created_count += 1
            
            if created_count > 0:
                messages.success(request, f'Successfully joined {created_count} business(es)!')
            return redirect('customers:customer_dashboard')
    else:
        form = TenantSelectionForm(customer=customer)
    
    # Get available tenants for display
    available_tenants = Tenant.objects.filter(active=True, verified=True)
    if customer:
        joined_tenant_ids = customer.tenant_memberships.values_list('tenant_id', flat=True)
        available_tenants = available_tenants.exclude(id__in=joined_tenant_ids)
    
    return render(request, 'customers/select_tenants.html', {
        'form': form,
        'available_tenants': available_tenants,
        'customer': customer
    })


@login_required
def customer_dashboard(request):
    """Multi-wallet customer dashboard"""
    try:
        customer = request.user.customer_profile
        memberships = customer.get_active_memberships().select_related('tenant')
        
        # Get wallet data for each membership
        wallets = []
        for membership in memberships:
            loyalty_account = membership.get_loyalty_account()
            wallets.append({
                'membership': membership,
                'tenant': membership.tenant,
                'points_balance': membership.get_points_balance(),
                'tier': membership.get_current_tier(),
                'recent_transactions': membership.get_recent_transactions(5)
            })
        
        context = {
            'customer': customer,
            'wallets': wallets,
            'total_wallets': len(wallets)
        }
        
        return render(request, 'customers/dashboard.html', context)
    except Customer.DoesNotExist:
        messages.error(request, 'Please complete your registration first.')
        return redirect('customers:customer_register')


@login_required
def wallet_detail(request, tenant_id):
    """Individual wallet/tenant membership detail"""
    try:
        customer = request.user.customer_profile
        membership = get_object_or_404(
            CustomerTenantMembership,
            customer=customer,
            tenant_id=tenant_id,
            active=True
        )
        
        loyalty_account = membership.get_loyalty_account()
        transactions = membership.get_recent_transactions(20)
        
        context = {
            'membership': membership,
            'tenant': membership.tenant,
            'loyalty_account': loyalty_account,
            'transactions': transactions,
            'points_balance': membership.get_points_balance(),
            'tier': membership.get_current_tier()
        }
        
        return render(request, 'customers/wallet_detail.html', context)
    except Customer.DoesNotExist:
        messages.error(request, 'Customer profile not found.')
        return redirect('customers:customer_register')


# Legacy API views (to be updated for multi-tenant)
from rest_framework import generics
from .serializers import CustomerSerializer, LoyaltyAccountSerializer, PointsBalanceSerializer, PointAdjustmentSerializer

# Placeholder API views - these need to be updated for multi-tenant architecture
class CustomerProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        customer, created = Customer.objects.get_or_create(
            user=self.request.user
        )
        return customer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def points_balance(request):
    """Get customer's points balance - placeholder for multi-tenant update"""
    return Response({'message': 'API endpoint needs multi-tenant update'}, 
                   status=status.HTTP_501_NOT_IMPLEMENTED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def points_history(request):
    """Get customer's points history - placeholder for multi-tenant update"""
    return Response({'message': 'API endpoint needs multi-tenant update'}, 
                   status=status.HTTP_501_NOT_IMPLEMENTED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def adjust_points(request):
    """Adjust points - placeholder for multi-tenant update"""
    return Response({'message': 'API endpoint needs multi-tenant update'}, 
                   status=status.HTTP_501_NOT_IMPLEMENTED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def customer_rewards(request):
    """Get rewards - placeholder for multi-tenant update"""
    return Response({'message': 'API endpoint needs multi-tenant update'}, 
                   status=status.HTTP_501_NOT_IMPLEMENTED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def redeem_reward(request):
    """Redeem reward - placeholder for multi-tenant update"""
    return Response({'message': 'API endpoint needs multi-tenant update'}, 
                   status=status.HTTP_501_NOT_IMPLEMENTED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def customer_checkin(request):
    """Customer check-in - placeholder for multi-tenant update"""
    return Response({'message': 'API endpoint needs multi-tenant update'}, 
                   status=status.HTTP_501_NOT_IMPLEMENTED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_recommendations(request):
    """AI recommendations - placeholder for multi-tenant update"""
    return Response({'message': 'API endpoint needs multi-tenant update'}, 
                   status=status.HTTP_501_NOT_IMPLEMENTED)


# Legacy UI Views - to be updated
@login_required
def customer_history_view(request):
    """Legacy customer history view"""
    messages.info(request, 'Please use the new multi-wallet dashboard')
    return redirect('customers:customer_dashboard')


@login_required
def customer_rewards_view(request):
    """Legacy customer rewards view"""
    messages.info(request, 'Please use the new multi-wallet dashboard')
    return redirect('customers:customer_dashboard')


@rate_limit(limit=50, window=3600)
def transaction_history(request):
    """Transaction history view"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    try:
        customer = Customer.objects.get(user=request.user)
        transactions = customer.loyalty_account.transactions.all()[:50]
        
        context = {
            'transactions': transactions,
            'points_balance': customer.loyalty_account.points_balance,
        }
        
        return render(request, 'customers/history.html', context)
        
    except (Customer.DoesNotExist, LoyaltyAccount.DoesNotExist):
        return redirect('customers:customer_dashboard')