from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg, Sum, F, ExpressionWrapper, DurationField, DateTimeField, Case, When, Value, IntegerField
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncYear, Coalesce, ExtractWeekDay
from django.utils import timezone
from datetime import timedelta, datetime, date
import json
from decimal import Decimal
from collections import defaultdict

from .models import Tenant, Industry, Branch
from apps.loyalty.models import Tier as LoyaltyTier, LoyaltyProgram, Transaction, Rule
from .forms import TenantRegistrationForm, BranchForm, LoyaltyRuleForm
from apps.accounts.models import User
from apps.customers.models import Customer, CustomerTenantMembership, LoyaltyAccount


@login_required
def customer_analytics(request):
    """Customer analytics and segmentation view"""
    tenant = get_object_or_404(Tenant, owner=request.user)
    
    # Get date range for analytics (last 30 days by default)
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)
    
    # Get all customer memberships for this tenant
    memberships = CustomerTenantMembership.objects.filter(tenant=tenant)
    
    # Basic customer counts
    total_customers = memberships.count()
    
    # Active customers (active in last 30 days)
    active_customers = memberships.filter(
        last_activity__gte=timezone.now() - timedelta(days=30)
    ).count()
    
    # New customers (joined in last 30 days)
    new_customers = memberships.filter(
        join_date__gte=timezone.now() - timedelta(days=30)
    ).count()
    
    # Get customer growth data
    customer_growth = memberships.annotate(
        join_week=TruncWeek('join_date')
    ).values('join_week').annotate(
        count=Count('id')
    ).order_by('join_week')
    
    # Prepare growth chart data
    growth_dates = []
    growth_counts = []
    running_total = 0
    
    # Calculate running total for each week
    for week in customer_growth:
        if week['join_week']:
            growth_dates.append(week['join_week'].strftime('%b %d, %Y'))
            running_total += week['count']
            growth_counts.append(running_total)
    
    # Get customer segments
    segments = memberships.values('segment').annotate(
        count=Count('id'),
        percentage=Count('id') * 100.0 / total_customers if total_customers > 0 else 0
    ).order_by('-count')
    
    # Get top customers by points
    top_customers = memberships.select_related('loyalty_account').order_by(
        '-loyalty_account__points_balance'
    )[:10]
    
    # Get customer activity by day of week
    activity_by_day = memberships.annotate(
        weekday=ExtractWeekDay('last_activity')
    ).values('weekday').annotate(
        count=Count('id')
    ).order_by('weekday')
    
    # Map weekday numbers to day names
    day_names = ['', 'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    activity_days = [day_names[day['weekday']] for day in activity_by_day if day['weekday'] is not None]
    activity_counts = [day['count'] for day in activity_by_day if day['weekday'] is not None]
    
    context = {
        'tenant': tenant,
        'total_customers': total_customers,
        'active_customers': active_customers,
        'new_customers': new_customers,
        'growth_dates': json.dumps(growth_dates),
        'growth_counts': json.dumps(growth_counts),
        'segments': segments,
        'top_customers': top_customers,
        'activity_days': json.dumps(activity_days),
        'activity_counts': json.dumps(activity_counts),
        'start_date': start_date.date(),
        'end_date': end_date.date(),
    }
    
    return render(request, 'tenants/analytics/customer_analytics.html', context)


@login_required
def analytics_dashboard(request):
    """Analytics dashboard view"""
    tenant = get_object_or_404(Tenant, owner=request.user)
    
    # Get date range for analytics (last 30 days by default)
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)
    
    # Get basic stats
    total_customers = CustomerTenantMembership.objects.filter(tenant=tenant).count()
    active_customers = CustomerTenantMembership.objects.filter(
        tenant=tenant,
        last_activity__gte=timezone.now() - timedelta(days=30)
    ).count()
    
    # Get transaction stats
    transactions = Transaction.objects.filter(
        loyalty_account__tenant=tenant,
        created_at__range=[start_date, end_date]
    )
    
    total_transactions = transactions.count()
    total_points_earned = transactions.filter(
        transaction_type__in=['earn', 'bonus']
    ).aggregate(total=Coalesce(Sum('points'), 0))['total']
    
    # Get recent transactions for the activity feed
    recent_transactions = transactions.select_related(
        'loyalty_account__customer'
    ).order_by('-created_at')[:10]
    
    # Get daily transaction counts for the chart
    daily_transactions = transactions.annotate(
        date=TruncDay('created_at')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    # Prepare data for the chart
    date_series = []
    transaction_counts = []
    
    # Fill in missing dates with zeros
    current_date = start_date.date()
    while current_date <= end_date.date():
        date_series.append(current_date.strftime('%b %d'))
        
        # Find transactions for this date
        count = 0
        for day in daily_transactions:
            if day['date'].date() == current_date:
                count = day['count']
                break
                
        transaction_counts.append(count)
        current_date += timedelta(days=1)
    
    context = {
        'tenant': tenant,
        'total_customers': total_customers,
        'active_customers': active_customers,
        'total_transactions': total_transactions,
        'total_points_earned': total_points_earned,
        'recent_transactions': recent_transactions,
        'date_series': json.dumps(date_series),
        'transaction_counts': json.dumps(transaction_counts),
        'start_date': start_date.date(),
        'end_date': end_date.date(),
    }
    
    return render(request, 'tenants/analytics/dashboard.html', context)


@login_required
def loyalty_rules_api(request):
    """API endpoint for loyalty rules"""
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    tenant = get_object_or_404(Tenant, owner=request.user)
    
    if request.method == 'GET':
        # Return list of all rules for the tenant
        rules = Rule.objects.filter(tenant=tenant).order_by('name')
        rules_data = [{
            'id': str(rule.id),
            'name': rule.name,
            'description': rule.description,
            'points': rule.points,
            'rule_type': rule.rule_type,
            'is_active': rule.is_active,
            'created_at': rule.created_at.isoformat(),
            'updated_at': rule.updated_at.isoformat()
        } for rule in rules]
        
        return JsonResponse({
            'success': True,
            'rules': rules_data
        })
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def delete_loyalty_rule(request, rule_id):
    """Delete a loyalty rule via AJAX"""
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    tenant = get_object_or_404(Tenant, owner=request.user)
    rule = get_object_or_404(Rule, id=rule_id, tenant=tenant)
    
    if request.method == 'POST':
        rule_id = str(rule.id)
        rule.delete()
        return JsonResponse({
            'success': True,
            'message': 'Loyalty rule deleted successfully',
            'rule_id': rule_id
        })
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def edit_loyalty_rule(request, rule_id):
    """Edit an existing loyalty rule via AJAX"""
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    tenant = get_object_or_404(Tenant, owner=request.user)
    rule = get_object_or_404(Rule, id=rule_id, tenant=tenant)
    
    if request.method == 'POST':
        form = LoyaltyRuleForm(request.POST, instance=rule, tenant=tenant)
        if form.is_valid():
            rule = form.save()
            return JsonResponse({
                'success': True,
                'message': 'Loyalty rule updated successfully',
                'rule': {
                    'id': rule.id,
                    'name': rule.name,
                    'description': rule.description,
                    'points': rule.points,
                    'rule_type': rule.rule_type,
                    'is_active': rule.is_active,
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def create_loyalty_rule(request):
    """Create a new loyalty rule via AJAX"""
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    tenant = get_object_or_404(Tenant, owner=request.user)
    
    if request.method == 'POST':
        form = LoyaltyRuleForm(request.POST, tenant=tenant)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.tenant = tenant
            rule.save()
            return JsonResponse({
                'success': True,
                'message': 'Loyalty rule created successfully',
                'rule': {
                    'id': rule.id,
                    'name': rule.name,
                    'description': rule.description,
                    'points': rule.points,
                    'rule_type': rule.rule_type,
                    'is_active': rule.is_active,
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def manage_loyalty_rules(request):
    """Manage loyalty rules for a tenant"""
    tenant = get_object_or_404(Tenant, owner=request.user)
    
    # Get all rules for this tenant's loyalty programs
    rules = Rule.objects.filter(program__tenant=tenant).select_related('program').order_by('name')
    
    # Get or create a default loyalty program for the tenant
    program, created = LoyaltyProgram.objects.get_or_create(
        tenant=tenant,
        defaults={
            'name': f"{tenant.name}'s Loyalty Program",
            'description': f"Default loyalty program for {tenant.name}",
            'active': True
        }
    )
    
    # Handle form submission
    if request.method == 'POST':
        form = LoyaltyRuleForm(request.POST, program=program)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.program = program
            rule.save()
            messages.success(request, 'Loyalty rule saved successfully.')
            return redirect('tenants:manage_loyalty_rules')
    else:
        form = LoyaltyRuleForm(program=program)
    
    context = {
        'tenant': tenant,
        'rules': rules,
        'form': form,
        'loyalty_program': program,
    }
    
    return render(request, 'tenants/loyalty_rules/manage.html', context)


def tenant_register(request):
    """Tenant self-registration view"""
    # If user already has a tenant, redirect to dashboard
    if request.user.is_authenticated and hasattr(request.user, 'owned_tenants') and request.user.owned_tenants.exists():
        return redirect('tenants:tenant_dashboard')
    if request.method == 'POST':
        form = TenantRegistrationForm(request.POST)
        if form.is_valid():
            try:
                tenant = form.save()
                # Log the user in automatically
                login(request, tenant.owner)
                messages.success(request, f'Welcome to RewardHub! Your business "{tenant.business_name}" has been registered successfully.')
                return redirect('tenants:tenant_onboarding')
            except Exception as e:
                messages.error(request, f'Registration failed: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = TenantRegistrationForm()
    
    industries = Industry.objects.all()
    return render(request, 'tenants/register.html', {
        'form': form,
        'industries': industries
    })


@login_required
def tenant_onboarding(request):
    """Tenant onboarding flow after registration"""
    try:
        tenant = request.user.owned_tenants.first()
        if not tenant:
            messages.info(request, 'Please register your business first.')
            return render(request, 'tenants/register.html', {
                'form': TenantRegistrationForm(),
                'industries': Industry.objects.all()
            })
        
        branches = tenant.branches.all()
        
        if request.method == 'POST':
            branch_form = BranchForm(request.POST)
            if branch_form.is_valid():
                branch = branch_form.save(commit=False)
                branch.tenant = tenant
                branch.save()
                messages.success(request, f'Branch "{branch.name}" added successfully!')
                return redirect('tenants:tenant_onboarding')
        else:
            branch_form = BranchForm()
        
        return render(request, 'tenants/onboarding.html', {
            'tenant': tenant,
            'branches': branches,
            'branch_form': branch_form
        })
    except Exception as e:
        messages.error(request, f'Error during onboarding: {str(e)}')
        return render(request, 'tenants/onboarding.html', {
            'tenant': None,
            'branches': [],
            'branch_form': BranchForm()
        })


@login_required
def tenant_dashboard(request):
    """Main tenant dashboard"""
    try:
        tenant = request.user.owned_tenants.first()
        if not tenant:
            messages.info(request, 'Please register your business to access the dashboard.')
            return render(request, 'tenants/register.html', {
                'form': TenantRegistrationForm(),
                'industries': Industry.objects.all()
            })
        
        branches = tenant.branches.all()
        
        context = {
            'tenant': tenant,
            'branches': branches,
            'total_branches': branches.count(),
            'active_branches': branches.filter(active=True).count(),
        }
        
        return render(request, 'tenants/dashboard.html', context)
    except Exception as e:
        messages.error(request, f'Error loading dashboard: {str(e)}')
        return render(request, 'tenants/register.html', {
            'form': TenantRegistrationForm(),
            'industries': Industry.objects.all()
        })


@login_required
@require_http_methods(["POST"])
def add_branch(request):
    """Add a new branch via AJAX"""
    try:
        tenant = request.user.owned_tenants.first()
        if not tenant:
            return JsonResponse({'success': False, 'error': 'No tenant found'})
        
        form = BranchForm(request.POST)
        if form.is_valid():
            branch = form.save(commit=False)
            branch.tenant = tenant
            branch.save()
            return JsonResponse({
                'success': True,
                'message': f'Branch "{branch.name}" added successfully!',
                'branch': {
                    'id': branch.id,
                    'name': branch.name,
                    'address': branch.address,
                    'city': branch.city,
                    'state': branch.state,
                    'active': branch.active
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def manage_branches(request):
    """Branch management page"""
    try:
        tenant = request.user.owned_tenants.first()
        if not tenant:
            messages.info(request, 'Please register your business first.')
            return render(request, 'tenants/register.html', {
                'form': TenantRegistrationForm(),
                'industries': Industry.objects.all()
            })
        
        branches = tenant.branches.all().order_by('-created_at')
        
        return render(request, 'tenants/manage_branches.html', {
            'tenant': tenant,
            'branches': branches
        })
    except Exception as e:
        messages.error(request, f'Error loading branches: {str(e)}')
        return redirect('tenants:tenant_dashboard')


@login_required
def points_analytics(request):
    """Points analytics and trends"""
    try:
        tenant = request.user.owned_tenants.first()
        if not tenant:
            return redirect('tenants:tenant_register')
        
        # Date range for analytics (last 30 days by default)
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)
        
        # Get date filter from request
        date_range = request.GET.get('date_range', '30d')
        if date_range == '7d':
            start_date = end_date - timedelta(days=7)
        elif date_range == '90d':
            start_date = end_date - timedelta(days=90)
        
        # Get points data
        points_earned = Transaction.objects.filter(
            loyalty_account__tenant=tenant,
            points__gt=0,
            created_at__range=[start_date, end_date]
        ).select_related('loyalty_account__customer')
        
        points_redeemed = Transaction.objects.filter(
            loyalty_account__tenant=tenant,
            points__lt=0,
            created_at__range=[start_date, end_date]
        ).select_related('loyalty_account__customer')
        
        # Total metrics
        total_points_earned = points_earned.aggregate(
            total=Coalesce(Sum('points'), 0)
        )['total']
        
        total_points_redeemed = abs(points_redeemed.aggregate(
            total=Coalesce(Sum('points'), 0)
        )['total'])
        
        active_customers = CustomerTenantMembership.objects.filter(
            tenant=tenant,
            last_activity__range=[start_date, end_date]
        ).count()
        
        # Points breakdown by type
        points_by_type = points_earned.values('transaction_type').annotate(
            total_points=Coalesce(Sum('points'), 0),
            transaction_count=Count('id')
        ).order_by('-total_points')
        
        # Points over time
        date_series = []
        earned_data = []
        redeemed_data = []
        
        # Group by time period based on date range
        if date_range == '7d':
            period = 'day'
            date_format = '%b %d'
            group_by = TruncDay('created_at')
        elif date_range == '90d':
            period = 'week'
            date_format = '%b %d'
            group_by = TruncWeek('created_at')
        else:  # 30d
            period = 'day'
            date_format = '%b %d'
            group_by = TruncDay('created_at')
        
        # Get points earned by period
        earned_by_period = points_earned.annotate(
            period=group_by
        ).values('period').annotate(
            points=Coalesce(Sum('points'), 0)
        ).order_by('period')
        
        # Get points redeemed by period
        redeemed_by_period = points_redeemed.annotate(
            period=group_by
        ).values('period').annotate(
            points=Coalesce(Sum('points') * -1, 0)  # Convert to positive for display
        ).order_by('period')
        
        # Fill in missing dates with zeros
        earned_dict = {item['period'].date(): item['points'] for item in earned_by_period}
        redeemed_dict = {item['period'].date(): item['points'] for item in redeemed_by_period}
        
        all_dates = set(earned_dict.keys()).union(set(redeemed_dict.keys()))
        if not all_dates:  # If no data, add start and end dates
            all_dates = {start_date.date(), end_date.date()}
        
        # Sort dates and fill in the series
        current_date = start_date.date()
        while current_date <= end_date.date():
            date_str = current_date.strftime(date_format)
            date_series.append(date_str)
            
            earned_data.append(earned_dict.get(current_date, 0))
            redeemed_data.append(redeemed_dict.get(current_date, 0))
            
            if period == 'day':
                current_date += timedelta(days=1)
            else:  # week
                current_date += timedelta(weeks=1)
        
        # Top earners and redeemers
        top_earners = CustomerTenantMembership.objects.filter(
            tenant=tenant
        ).annotate(
            points_earned=Coalesce(Sum(
                Case(
                    When(transactions__points__gt=0, then='transactions__points'),
                    default=0,
                    output_field=IntegerField()
                )
            ), 0),
            points_redeemed=Coalesce(Sum(
                Case(
                    When(transactions__points__lt=0, then=-F('transactions__points')),
                    default=0,
                    output_field=IntegerField()
                )
            ), 0)
        ).filter(
            points_earned__gt=0  # Only include customers who have earned points
        ).order_by('-points_earned')[:10]
        
        # Points distribution by tier
        points_by_tier = CustomerTenantMembership.objects.filter(
            tenant=tenant,
            tier__isnull=False
        ).values(
            'tier__name',
            'tier__level'
        ).annotate(
            total_points=Coalesce(Sum('points_balance'), 0),
            customer_count=Count('id')
        ).order_by('tier__level')
        
        context = {
            'tenant': tenant,
            'total_points_earned': total_points_earned,
            'total_points_redeemed': total_points_redeemed,
            'active_customers': active_customers,
            'points_by_type': list(points_by_type),
            'date_series': json.dumps(date_series),
            'earned_data': json.dumps(earned_data),
            'redeemed_data': json.dumps(redeemed_data),
            'top_earners': top_earners,
            'points_by_tier': list(points_by_tier),
            'start_date': start_date.date(),
            'end_date': end_date.date(),
            'selected_date_range': date_range,
            'period': period
        }
        
        return render(request, 'tenants/analytics/points_analytics.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading points analytics: {str(e)}')
        return redirect('tenants:analytics_dashboard')


@login_required
def transaction_analytics(request):
    """Transaction analytics and trends"""
    try:
        tenant = request.user.owned_tenants.first()
        if not tenant:
            return redirect('tenants:tenant_register')
        
        # Date range for analytics (last 30 days by default)
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)
        
        # Get date filter from request
        date_range = request.GET.get('date_range', '30d')
        if date_range == '7d':
            start_date = end_date - timedelta(days=7)
        elif date_range == '90d':
            start_date = end_date - timedelta(days=90)
        
        # Get transaction data
        transactions = Transaction.objects.filter(
            loyalty_account__tenant=tenant,
            created_at__range=[start_date, end_date]
        ).select_related('loyalty_account__customer')
        
        # Total metrics
        total_transactions = transactions.count()
        total_points_earned = transactions.filter(points__gt=0).aggregate(
            total=Coalesce(Sum('points'), 0)
        )['total']
        
        total_points_redeemed = abs(transactions.filter(points__lt=0).aggregate(
            total=Coalesce(Sum('points'), 0)
        )['total'])
        
        # Transaction volume over time
        date_series = []
        volume_data = []
        points_earned_data = []
        points_redeemed_data = []
        
        # Group by time period based on date range
        if date_range == '7d':
            period = 'day'
            date_format = '%b %d'
            group_by = TruncDay('created_at')
        elif date_range == '90d':
            period = 'week'
            date_format = '%b %d'
            group_by = TruncWeek('created_at')
        else:  # 30d
            period = 'day'
            date_format = '%b %d'
            group_by = TruncDay('created_at')
        
        # Get transaction volume by period
        volume_by_period = transactions.annotate(
            period=group_by
        ).values('period').annotate(
            count=Count('id'),
            points_earned=Coalesce(Sum(Case(
                When(points__gt=0, then='points'),
                default=0,
                output_field=IntegerField()
            )), 0),
            points_redeemed=Coalesce(Sum(Case(
                When(points__lt=0, then=-F('points')),
                default=0,
                output_field=IntegerField()
            )), 0)
        ).order_by('period')
        
        # Fill in missing dates with zeros
        date_dict = {item['period'].date(): item for item in volume_by_period}
        
        current_date = start_date.date()
        while current_date <= end_date.date():
            date_str = current_date.strftime(date_format)
            date_series.append(date_str)
            
            if current_date in date_dict:
                volume_data.append(date_dict[current_date]['count'])
                points_earned_data.append(date_dict[current_date]['points_earned'])
                points_redeemed_data.append(date_dict[current_date]['points_redeemed'])
            else:
                volume_data.append(0)
                points_earned_data.append(0)
                points_redeemed_data.append(0)
            
            if period == 'day':
                current_date += timedelta(days=1)
            else:  # week
                current_date += timedelta(weeks=1)
        
        # Transaction types breakdown
        transaction_types = transactions.values('transaction_type').annotate(
            count=Count('id'),
            total_points=Coalesce(Sum('points'), 0)
        ).order_by('-count')
        
        # Top transactions (by points)
        top_transactions = transactions.order_by('-points')[:10]
        
        # Average transaction value
        avg_points_per_transaction = transactions.aggregate(
            avg=Avg('points')
        )['avg'] or 0
        
        context = {
            'tenant': tenant,
            'total_transactions': total_transactions,
            'total_points_earned': total_points_earned,
            'total_points_redeemed': total_points_redeemed,
            'date_series': json.dumps(date_series),
            'volume_data': json.dumps(volume_data),
            'points_earned_data': json.dumps(points_earned_data),
            'points_redeemed_data': json.dumps(points_redeemed_data),
            'transaction_types': list(transaction_types),
            'top_transactions': top_transactions,
            'avg_points_per_transaction': round(avg_points_per_transaction, 1),
            'start_date': start_date.date(),
            'end_date': end_date.date(),
            'selected_date_range': date_range,
            'period': period
        }
        
        return render(request, 'tenants/analytics/transaction_analytics.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading transaction analytics: {str(e)}')
        return redirect('tenants:analytics_dashboard')


@login_required
def customer_management(request):
    """Scalable customer management with pagination and search"""
    try:
        tenant = request.user.owned_tenants.first()
        if not tenant:
            messages.info(request, 'Please register your business first.')
            return render(request, 'tenants/register.html', {
                'form': TenantRegistrationForm(),
                'industries': Industry.objects.all()
            })
        
        # Get all customer memberships for this tenant
        customers_queryset = CustomerTenantMembership.objects.filter(
            tenant=tenant
        ).select_related('customer', 'customer__user').prefetch_related('loyalty_accounts__transactions')
        
        # Search functionality
        search_query = request.GET.get('search', '')
        if search_query:
            customers_queryset = customers_queryset.filter(
                Q(customer__user__first_name__icontains=search_query) |
                Q(customer__user__last_name__icontains=search_query) |
                Q(customer__user__email__icontains=search_query) |
                Q(customer__phone__icontains=search_query)
            )
        
        # Filter by tier
        tier_filter = request.GET.get('tier', '')
        if tier_filter:
            customers_queryset = customers_queryset.filter(loyalty_accounts__tier__name__iexact=tier_filter)
        
        # Filter by status
        status_filter = request.GET.get('status', '')
        if status_filter == 'active':
            customers_queryset = customers_queryset.filter(active=True)
        elif status_filter == 'inactive':
            customers_queryset = customers_queryset.filter(active=False)
        
        # Filter by branch - skip for now as branch relationship needs to be defined
        branch_filter = request.GET.get('branch', '')
        # if branch_filter:
        #     customers_queryset = customers_queryset.filter(branch__id=branch_filter)
        
        # Filter by points range
        min_points = request.GET.get('min_points', '')
        max_points = request.GET.get('max_points', '')
        if min_points:
            customers_queryset = customers_queryset.filter(loyalty_accounts__points_balance__gte=int(min_points))
        if max_points:
            customers_queryset = customers_queryset.filter(loyalty_accounts__points_balance__lte=int(max_points))
        
        # Filter by join date
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        if date_from:
            customers_queryset = customers_queryset.filter(joined_at__gte=date_from)
        if date_to:
            customers_queryset = customers_queryset.filter(joined_at__lte=date_to)
        
        # Sorting
        sort_by = request.GET.get('sort', 'joined_at')
        sort_order = request.GET.get('order', 'desc')
        
        if sort_order == 'desc':
            sort_by = f'-{sort_by}'
        
        # Map frontend sort fields to model fields
        sort_mapping = {
            'name': 'customer__user__first_name',
            '-name': '-customer__user__first_name',
            'email': 'customer__user__email',
            '-email': '-customer__user__email',
            'points': 'loyalty_accounts__points_balance',
            '-points': '-loyalty_accounts__points_balance',
            'tier': 'loyalty_accounts__tier__name',
            '-tier': '-loyalty_accounts__tier__name',
            'joined_at': 'joined_at',
            '-joined_at': '-joined_at',
        }
        
        actual_sort = sort_mapping.get(sort_by, 'joined_at')
        customers_queryset = customers_queryset.order_by(actual_sort)
        
        # Pagination
        page_size = int(request.GET.get('page_size', 25))
        paginator = Paginator(customers_queryset, page_size)
        page_number = request.GET.get('page', 1)
        customers_page = paginator.get_page(page_number)
        
        # Calculate stats
        total_customers = CustomerTenantMembership.objects.filter(tenant=tenant).count()
        active_customers = CustomerTenantMembership.objects.filter(tenant=tenant, active=True).count()
        
        # At-risk customers (no activity in 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        at_risk_customers = CustomerTenantMembership.objects.filter(
            tenant=tenant,
            last_activity__lt=thirty_days_ago
        ).count()
        
        # Average points from loyalty accounts
        from django.db.models import Sum
        avg_points = CustomerTenantMembership.objects.filter(tenant=tenant).aggregate(
            avg=Avg('loyalty_accounts__points_balance')
        )['avg'] or 0
        
        # Get branches for filter dropdown
        branches = tenant.branches.all()
        
        context = {
            'tenant': tenant,
            'customers': customers_page,
            'branches': branches,
            'total_customers': total_customers,
            'active_customers': active_customers,
            'at_risk_customers': at_risk_customers,
            'avg_points': round(avg_points),
            'search_query': search_query,
            'tier_filter': tier_filter,
            'status_filter': status_filter,
            'branch_filter': branch_filter,
            'page_size': page_size,
        }
        
        return render(request, 'tenants/customer_management.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading customer management: {str(e)}')
        return redirect('tenants:tenant_dashboard')


@login_required
def customer_management_api(request):
    """API endpoint for customer data with pagination and search"""
    try:
        tenant = request.user.owned_tenants.first()
        if not tenant:
            return JsonResponse({'error': 'No tenant found'}, status=400)
        
        # Get parameters
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 25))
        search = request.GET.get('search', '')
        tier_filter = request.GET.get('tier', '')
        status_filter = request.GET.get('status', '')
        sort_by = request.GET.get('sort', 'customer__first_name')
        sort_order = request.GET.get('order', 'asc')
        
        # Build queryset
        customers_queryset = CustomerTenantMembership.objects.filter(
            tenant=tenant
        ).select_related('customer', 'customer__user').prefetch_related('loyalty_accounts__tier')
        
        # Apply filters
        if search:
            customers_queryset = customers_queryset.filter(
                Q(customer__user__first_name__icontains=search) |
                Q(customer__user__last_name__icontains=search) |
                Q(customer__user__email__icontains=search) |
                Q(customer__phone__icontains=search)
            )
        
        if tier_filter:
            customers_queryset = customers_queryset.filter(loyalty_accounts__tier__name__iexact=tier_filter)
        
        if status_filter == 'active':
            customers_queryset = customers_queryset.filter(active=True)
        elif status_filter == 'inactive':
            customers_queryset = customers_queryset.filter(active=False)
        
        # Sort - map to correct field names
        sort_mapping = {
            'customer__first_name': 'customer__user__first_name',
            'customer__last_name': 'customer__user__last_name',
            'customer__email': 'customer__user__email',
            'points_balance': 'loyalty_accounts__points_balance',
            'tier__name': 'loyalty_accounts__tier__name'
        }
        
        actual_sort = sort_mapping.get(sort_by, sort_by)
        if sort_order == 'desc':
            actual_sort = f'-{actual_sort}'
        
        customers_queryset = customers_queryset.order_by(actual_sort)
        
        # Paginate
        paginator = Paginator(customers_queryset, page_size)
        customers_page = paginator.get_page(page)
        
        # Serialize data
        customers_data = []
        for membership in customers_page:
            customer = membership.customer
            last_transaction = Transaction.objects.filter(
                loyalty_account__membership=membership
            ).order_by('-created_at').first()
            
            customers_data.append({
                'id': membership.id,
                'customer_id': customer.id,
                'name': f"{customer.user.first_name} {customer.user.last_name}",
                'email': customer.user.email,
                'phone': customer.phone or '',
                'tier': membership.get_current_tier().name if membership.get_current_tier() else 'None',
                'points': membership.get_points_balance(),
                'status': 'Active' if membership.active else 'Inactive',
                'last_activity': last_transaction.created_at.strftime('%Y-%m-%d') if last_transaction else 'Never',
                'churn_risk': 'High' if not last_transaction or 
                    (timezone.now() - last_transaction.created_at).days > 30 else 'Low'
            })
        
        return JsonResponse({
            'results': customers_data,
            'count': paginator.count,
            'num_pages': paginator.num_pages,
            'current_page': customers_page.number,
            'has_next': customers_page.has_next(),
            'has_previous': customers_page.has_previous(),
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def customer_detail_api(request, customer_id):
    """Get detailed customer information"""
    try:
        tenant = request.user.owned_tenants.first()
        if not tenant:
            return JsonResponse({'error': 'No tenant found'}, status=400)
        
        membership = get_object_or_404(
            CustomerTenantMembership.objects.select_related('customer', 'customer__user').prefetch_related('loyalty_accounts__tier'),
            id=customer_id,
            tenant=tenant
        )
        
        customer = membership.customer
        
        # Get recent transactions from loyalty accounts
        recent_transactions = Transaction.objects.filter(
            loyalty_account__membership=membership
        ).order_by('-created_at')[:10]
        
        transactions_data = [{
            'id': t.id,
            'type': t.transaction_type,
            'points': t.points,
            'description': t.description,
            'date': t.created_at.strftime('%Y-%m-%d %H:%M'),
            'location': t.location.name if t.location else 'Online'
        } for t in recent_transactions]
        
        # Calculate activity metrics
        total_transactions = Transaction.objects.filter(
            loyalty_account__membership=membership
        ).count()
        total_points_earned = Transaction.objects.filter(
            loyalty_account__membership=membership,
            transaction_type='earn'
        ).aggregate(total=models.Sum('points'))['total'] or 0
        
        last_activity = recent_transactions[0].created_at if recent_transactions else None
        
        return JsonResponse({
            'customer': {
                'id': customer.id,
                'name': f"{customer.user.first_name} {customer.user.last_name}",
                'email': customer.user.email,
                'phone': customer.phone or '',
                'date_joined': customer.created_at.strftime('%Y-%m-%d'),
                'tier': membership.get_current_tier().name if membership.get_current_tier() else 'None',
                'points': membership.get_points_balance(),
                'status': 'Active' if membership.active else 'Inactive',
                'total_transactions': total_transactions,
                'total_points_earned': total_points_earned,
                'last_activity': last_activity.strftime('%Y-%m-%d %H:%M') if last_activity else 'Never',
            },
            'transactions': transactions_data
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def bulk_customer_action(request):
    """Handle bulk actions on customers"""
    try:
        tenant = request.user.owned_tenants.first()
        if not tenant:
            return JsonResponse({'error': 'No tenant found'}, status=400)
        
        action = request.POST.get('action')
        customer_ids = request.POST.getlist('customer_ids')
        
        if not customer_ids:
            return JsonResponse({'error': 'No customers selected'}, status=400)
        
        memberships = CustomerTenantMembership.objects.filter(
            id__in=customer_ids,
            tenant=tenant
        )
        
        if action == 'adjust_points':
            points_adjustment = int(request.POST.get('points_adjustment', 0))
            reason = request.POST.get('reason', 'Bulk adjustment')
            
            updated_count = 0
            for membership in memberships:
                old_balance = membership.get_points_balance()
                loyalty_account = membership.get_loyalty_account()
                if loyalty_account:
                    if points_adjustment > 0:
                        loyalty_account.add_points(points_adjustment, reason)
                    else:
                        loyalty_account.deduct_points(abs(points_adjustment), reason)
                    updated_count += 1
                # Transaction is already created by add_points/deduct_points methods
            
            return JsonResponse({
                'success': True,
                'message': f'Points adjusted for {updated_count} customers'
            })
        
        elif action == 'change_tier':
            new_tier_id = request.POST.get('new_tier_id')
            if not new_tier_id:
                return JsonResponse({'error': 'No tier specified'}, status=400)
            
            updated_count = memberships.update(tier_id=new_tier_id)
            
            return JsonResponse({
                'success': True,
                'message': f'Tier updated for {updated_count} customers'
            })
        
        elif action == 'toggle_status':
            active_status = request.POST.get('active') == 'true'
            updated_count = memberships.update(active=active_status)
            
            status_text = 'activated' if active_status else 'deactivated'
            return JsonResponse({
                'success': True,
                'message': f'{updated_count} customers {status_text}'
            })
        
        else:
            return JsonResponse({'error': 'Invalid action'}, status=400)
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)