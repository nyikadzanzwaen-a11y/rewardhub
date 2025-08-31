from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta, datetime
import json

from ..models import Tenant, Industry
from apps.accounts.models import User
from apps.customers.models import Customer, LoyaltyAccount, CustomerTenantMembership
from apps.loyalty.models import Rule, LoyaltyProgram, Tier as LoyaltyTier, Transaction

class AnalyticsViewsTestCase(TestCase):
    def setUp(self):
        # Create test user and tenant
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        # Create industry
        self.industry = Industry.objects.create(
            name='Retail',
            description='Retail business industry'
        )
        self.tenant = Tenant.objects.create(
            name='Test Business',
            business_name='Test Business Inc',
            subdomain='test',
            industry=self.industry,
            contact_email='test@example.com',
            owner=self.user
        )
        
        # Create test customer
        self.customer_user = User.objects.create_user(
            email='customer@example.com',
            password='testpass123',
            first_name='John',
            last_name='Doe'
        )
        self.customer = Customer.objects.create(
            user=self.customer_user,
            phone='+1234567890'
        )
        
        # Create loyalty program first (required for Tier)
        self.program = LoyaltyProgram.objects.create(
            tenant=self.tenant,
            name='Test Program',
            description='Test program description',
            active=True
        )
        
        # Create loyalty tier with correct fields
        self.tier = LoyaltyTier.objects.create(
            program=self.program,
            name='Gold',
            points_threshold=1000,
            benefits={'description': 'Test benefits'}
        )
        
        # Create customer membership
        self.membership = CustomerTenantMembership.objects.create(
            customer=self.customer,
            tenant=self.tenant,
            tier=self.tier,
            points_balance=500,
            last_activity=timezone.now()
        )
        
        # Create test transactions
        now = timezone.now()
        Transaction.objects.create(
            loyalty_account=self.membership,
            points=100,
            transaction_type='purchase',
            description='Test purchase',
            created_at=now - timedelta(days=1)
        )
        Transaction.objects.create(
            loyalty_account=self.membership,
            points=50,
            transaction_type='bonus',
            description='Test bonus',
            created_at=now - timedelta(days=2)
        )
        Transaction.objects.create(
            loyalty_account=self.membership,
            points=-25,
            transaction_type='redemption',
            description='Test redemption',
            created_at=now - timedelta(days=3)
        )
        
        # Set up request factory
        self.factory = RequestFactory()
        
        # Login the user
        self.client.login(email='test@example.com', password='testpass123')
    
    def test_analytics_dashboard_view(self):
        """Test the analytics dashboard view"""
        url = reverse('tenants:analytics_dashboard')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tenants/analytics/dashboard.html')
        self.assertIn('total_customers', response.context)
        self.assertIn('active_customers', response.context)
        self.assertIn('total_transactions', response.context)
        self.assertIn('total_points_earned', response.context)
        self.assertIn('recent_transactions', response.context)
    
    def test_customer_analytics_view(self):
        """Test the customer analytics view"""
        url = reverse('tenants:customer_analytics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tenants/analytics/customer_analytics.html')
        self.assertIn('segment_data', response.context)
        self.assertIn('growth_data', response.context)
        self.assertIn('top_customers', response.context)
        self.assertIn('weekday_activity', response.context)
        
        # Test with date range parameter
        response = self.client.get(url, {'date_range': '7d'})
        self.assertEqual(response.status_code, 200)
    
    def test_transaction_analytics_view(self):
        """Test the transaction analytics view"""
        url = reverse('tenants:transaction_analytics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tenants/analytics/transaction_analytics.html')
        self.assertIn('total_transactions', response.context)
        self.assertIn('total_points_earned', response.context)
        self.assertIn('total_points_redeemed', response.context)
        self.assertIn('transaction_types', response.context)
        self.assertIn('top_transactions', response.context)
        
        # Test with date range parameter
        response = self.client.get(url, {'date_range': '90d'})
        self.assertEqual(response.status_code, 200)
    
    def test_points_analytics_view(self):
        """Test the points analytics view"""
        url = reverse('tenants:points_analytics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tenants/analytics/points_analytics.html')
        self.assertIn('total_points_earned', response.context)
        self.assertIn('total_points_redeemed', response.context)
        self.assertIn('active_customers', response.context)
        self.assertIn('points_by_type', response.context)
        self.assertIn('top_earners', response.context)
        self.assertIn('points_by_tier', response.context)
        
        # Test with date range parameter
        response = self.client.get(url, {'date_range': '30d'})
        self.assertEqual(response.status_code, 200)
    
    def test_analytics_views_require_login(self):
        """Test that analytics views require authentication"""
        self.client.logout()
        
        urls = [
            reverse('tenants:analytics_dashboard'),
            reverse('tenants:customer_analytics'),
            reverse('tenants:transaction_analytics'),
            reverse('tenants:points_analytics'),
        ]
        
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)  # Redirect to login
            self.assertIn('/accounts/login/', response.url)
    
    def test_analytics_views_require_tenant_owner(self):
        """Test that only tenant owners can access analytics"""
        # Create a non-owner user
        non_owner = User.objects.create_user(
            email='nonowner@example.com',
            password='testpass123'
        )
        self.client.login(email='nonowner@example.com', password='testpass123')
        
        urls = [
            reverse('tenants:analytics_dashboard'),
            reverse('tenants:customer_analytics'),
            reverse('tenants:transaction_analytics'),
            reverse('tenants:points_analytics'),
        ]
        
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)  # Redirect to tenant registration
            self.assertIn(reverse('tenants:tenant_register'), response.url)
    
    def test_analytics_dashboard_data(self):
        """Test the data returned by the analytics dashboard"""
        # Create more test data
        customer2 = Customer.objects.create(
            user=User.objects.create_user(
                email='customer2@example.com',
                password='testpass123',
                first_name='Jane',
                last_name='Smith'
            ),
            phone='+1234567891'
        )
        
        # Create another membership for the second customer
        CustomerTenantMembership.objects.create(
            customer=customer2,
            tenant=self.tenant,
            tier=self.tier,
            points_balance=300,
            last_activity=timezone.now() - timedelta(days=15)
        )
        
        # Create more transactions
        now = timezone.now()
        Transaction.objects.create(
            loyalty_account=self.membership,
            points=75,
            transaction_type='purchase',
            description='Additional purchase',
            created_at=now - timedelta(days=5)
        )
        
        url = reverse('tenants:analytics_dashboard')
        response = self.client.get(url)
        
        # Check that the context contains the expected data
        self.assertEqual(response.context['total_customers'], 2)
        self.assertEqual(response.context['active_customers'], 2)  # Both active in last 30 days
        self.assertEqual(response.context['total_transactions'], 4)  # 3 original + 1 new
        self.assertEqual(response.context['total_points_earned'], 225)  # 100 + 50 + 75
    
    def test_customer_analytics_segmentation(self):
        """Test customer segmentation in the customer analytics view"""
        url = reverse('tenants:customer_analytics')
        response = self.client.get(url)
        
        # Check that the customer is properly segmented
        segment_data = response.context['segment_data']
        active_segment = next((s for s in segment_data if s['name'] == 'Active'), None)
        self.assertIsNotNone(active_segment)
        self.assertEqual(active_segment['count'], 1)
        self.assertEqual(active_segment['percentage'], 100.0)
    
    def test_points_analytics_by_tier(self):
        """Test points distribution by tier in the points analytics view"""
        url = reverse('tenants:points_analytics')
        response = self.client.get(url)
        
        # Check that the points by tier data is correct
        points_by_tier = response.context['points_by_tier']
        self.assertEqual(len(points_by_tier), 1)
        self.assertEqual(points_by_tier[0]['tier__name'], 'Gold')
        self.assertEqual(points_by_tier[0]['total_points'], 500)  # Points balance of the membership
        self.assertEqual(points_by_tier[0]['customer_count'], 1)

    def test_transaction_analytics_by_type(self):
        """Test transaction type breakdown in the transaction analytics view"""
        url = reverse('tenants:transaction_analytics')
        response = self.client.get(url)
        
        # Check that the transaction types are properly aggregated
        transaction_types = response.context['transaction_types']
        self.assertEqual(len(transaction_types), 3)  # purchase, bonus, redemption
        
        # Check that the points for each type are correct
        purchase_tx = next((t for t in transaction_types if t['transaction_type'] == 'purchase'), None)
        self.assertIsNotNone(purchase_tx)
        self.assertEqual(purchase_tx['total_points'], 100)
        
        bonus_tx = next((t for t in transaction_types if t['transaction_type'] == 'bonus'), None)
        self.assertIsNotNone(bonus_tx)
        self.assertEqual(bonus_tx['total_points'], 50)
        
        redemption_tx = next((t for t in transaction_types if t['transaction_type'] == 'redemption'), None)
        self.assertIsNotNone(redemption_tx)
        self.assertEqual(redemption_tx['total_points'], -25)
