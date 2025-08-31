"""
Gamification app URL patterns
"""
from django.urls import path
from . import views

app_name = 'gamification'

urlpatterns = [
    # API endpoints
    path('api/summary/', views.customer_gamification_summary, name='gamification_summary'),
    path('api/summary/<int:customer_id>/', views.customer_gamification_summary, name='customer_gamification_summary'),
    path('api/challenges/', views.available_challenges, name='available_challenges'),
    path('api/challenges/<int:challenge_id>/join/', views.join_challenge, name='join_challenge'),
    path('api/badges/', views.customer_badges, name='customer_badges'),
    path('api/badges/<int:customer_id>/', views.customer_badges, name='customer_badges_detail'),
    path('api/leaderboards/', views.available_leaderboards, name='available_leaderboards'),
    path('api/leaderboards/<int:leaderboard_id>/', views.leaderboard, name='leaderboard_detail'),
    
    # UI views
    path('dashboard/', views.gamification_dashboard, name='dashboard'),
    path('badges/', views.badges_gallery, name='badges'),
    path('challenges/', views.challenges_page, name='challenges'),
    path('leaderboards/', views.leaderboards_page, name='leaderboards'),
]
