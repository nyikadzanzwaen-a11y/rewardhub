"""
Analytics app URL patterns
"""
from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    # API endpoints
    path('api/clv-prediction/', views.customer_lifetime_value_prediction, name='clv_prediction'),
    path('api/customer/<int:customer_id>/behavior/', views.customer_behavior_prediction, name='customer_behavior'),
    path('api/spending-patterns/', views.spending_patterns_analysis, name='spending_patterns'),
    path('api/program-trends/', views.program_trends_analysis, name='program_trends'),
    path('api/performance-forecast/', views.performance_forecast, name='performance_forecast'),
    path('api/dashboard/', views.comprehensive_analytics_dashboard, name='analytics_dashboard_api'),
    
    # UI views
    path('dashboard/', views.analytics_dashboard, name='dashboard'),
    path('insights/', views.predictive_insights, name='insights'),
    path('customers/', views.customer_analytics, name='customer_analytics'),
]