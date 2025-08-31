from django.urls import path, include
from . import views

app_name = 'customers'

urlpatterns = [
    # Customer Registration and Multi-Wallet URLs
    path('register/', views.customer_register, name='customer_register'),
    path('select-tenants/', views.customer_select_tenants, name='customer_select_tenants'),
    path('dashboard/', views.customer_dashboard, name='customer_dashboard'),
    path('wallet/<uuid:tenant_id>/', views.wallet_detail, name='wallet_detail'),
    
    # API endpoints
    path('api/', include([
        path('profile/', views.CustomerProfileView.as_view(), name='customer_profile_api'),
        path('points/', views.points_balance, name='points_balance_api'),
        path('points/history/', views.points_history, name='points_history_api'),
        path('points/adjust/', views.adjust_points, name='adjust_points_api'),
        path('rewards/', views.customer_rewards, name='customer_rewards_api'),
        path('rewards/redeem/', views.redeem_reward, name='redeem_reward_api'),
        path('checkin/', views.customer_checkin, name='customer_checkin_api'),
        path('recommendations/', views.ai_recommendations, name='ai_recommendations_api'),
    ])),
    
    # Legacy UI endpoints (to be updated)
    path('history/', views.transaction_history, name='transaction_history'),
    path('rewards/', views.customer_rewards_view, name='customer_rewards'),
]