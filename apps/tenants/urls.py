from django.urls import path
from . import views

app_name = 'tenants'

urlpatterns = [
    # Existing URLs
    path('register/', views.tenant_register, name='tenant_register'),
    path('onboarding/', views.tenant_onboarding, name='tenant_onboarding'),
    path('dashboard/', views.tenant_dashboard, name='tenant_dashboard'),
    path('branches/', views.manage_branches, name='manage_branches'),
    path('branches/add/', views.add_branch, name='add_branch'),
    path('customers/', views.customer_management, name='customer_management'),
    path('api/customers/', views.customer_management_api, name='customer_management_api'),
    path('api/customers/<int:customer_id>/', views.customer_detail_api, name='customer_detail_api'),
    path('api/customers/bulk-action/', views.bulk_customer_action, name='bulk_customer_action'),
    
    # New Analytics URLs
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),
    path('analytics/customers/', views.customer_analytics, name='customer_analytics'),
    path('analytics/transactions/', views.transaction_analytics, name='transaction_analytics'),
    path('analytics/points/', views.points_analytics, name='points_analytics'),
    
    # Loyalty Rule Management
    path('loyalty/rules/', views.manage_loyalty_rules, name='manage_loyalty_rules'),
    path('loyalty/rules/create/', views.create_loyalty_rule, name='create_loyalty_rule'),
    path('loyalty/rules/<uuid:rule_id>/edit/', views.edit_loyalty_rule, name='edit_loyalty_rule'),
    path('loyalty/rules/<uuid:rule_id>/delete/', views.delete_loyalty_rule, name='delete_loyalty_rule'),
    path('api/loyalty/rules/', views.loyalty_rules_api, name='loyalty_rules_api'),
]