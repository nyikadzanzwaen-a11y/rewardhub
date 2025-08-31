"""
Fraud detection app URL patterns
"""
from django.urls import path
from . import views

app_name = 'fraud_detection'

urlpatterns = [
    # API endpoints
    path('api/analyze-transaction/', views.analyze_transaction_risk, name='analyze_transaction'),
    path('api/initialize-models/', views.initialize_fraud_models, name='initialize_models'),
    path('api/report/', views.fraud_detection_report, name='fraud_report'),
    path('api/customer/<int:customer_id>/risk-profile/', views.customer_risk_profile, name='customer_risk_profile'),
    
    # UI views
    path('dashboard/', views.fraud_detection_dashboard, name='dashboard'),
    path('reports/', views.fraud_reports, name='reports'),
]
