from django.urls import path
from . import views

urlpatterns = [
    # Loyalty Programs
    path("programs/", views.LoyaltyProgramListCreateView.as_view(), name="programs_list"),
    path("programs/<uuid:pk>/", views.LoyaltyProgramDetailView.as_view(), name="program_detail"),
    
    # Rules
    path("rules/", views.RuleListCreateView.as_view(), name="rules_list"),
    path("rules/<uuid:pk>/", views.RuleDetailView.as_view(), name="rule_detail"),
    
    # Customers
    path("customers/", views.CustomerListView.as_view(), name="customers_list"),
    path("customers/<uuid:customer_id>/adjust-points/", views.adjust_customer_points, name="adjust_points"),
    
    # Locations
    path("locations/", views.LocationListCreateView.as_view(), name="locations_list"),
    path("locations/<uuid:pk>/", views.LocationDetailView.as_view(), name="location_detail"),
    
    # Rewards
    path("rewards/", views.RewardListCreateView.as_view(), name="admin_rewards_list"),
    path("rewards/<uuid:pk>/", views.RewardDetailView.as_view(), name="admin_reward_detail"),
    
    # Analytics
    path("analytics/overview/", views.analytics_overview, name="analytics_overview"),
    
    # AI Insights
    path("insights/segments/", views.customer_segments, name="customer_segments"),
    path("insights/churn/", views.churn_predictions, name="churn_predictions"),
    path("insights/churn/generate/", views.generate_churn_predictions, name="generate_churn"),
]