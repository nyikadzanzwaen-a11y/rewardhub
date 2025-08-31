from django.urls import path
from . import views

urlpatterns = [
    # API endpoints
    path('api/list/', views.reward_list, name='reward_list'),
    path('api/redeem/', views.redeem_reward, name='redeem_reward'),
    
    # UI endpoints
    path('catalog/', views.reward_catalog, name='rewards_catalog'),
    path('redemptions/', views.redemption_history, name='redemption_history'),
]