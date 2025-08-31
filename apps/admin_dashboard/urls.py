"""
Admin Dashboard URL patterns
"""
from django.urls import path
from . import views

app_name = 'admin_dashboard'

urlpatterns = [
    # Main dashboard
    path('', views.admin_dashboard_home, name='home'),
    
    # Management interfaces
    path('program-config/', views.program_configuration, name='program_config'),
    path('customers/', views.customer_management, name='customer_management'),
    path('analytics/', views.analytics_reporting, name='analytics_reporting'),
    path('campaigns/', views.campaign_management, name='campaign_management'),
    path('ai-insights/', views.ai_insights_panel, name='ai_insights'),
    path('security/', views.security_audit_controls, name='security_audit'),
    path('tenants/', views.multitenant_management, name='multitenant_management'),
    
    # API endpoints
    path('api/metrics/', views.dashboard_metrics_api, name='metrics_api'),
    path('api/ai-insights/', views.ai_insights_api, name='ai_insights_api'),
    path('api/customer-action/', views.customer_action_api, name='customer_action_api'),
]
