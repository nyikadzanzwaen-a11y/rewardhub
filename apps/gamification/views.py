"""
Gamification API views
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from apps.customers.models import Customer
from utils.security import rate_limit, validate_request_data
from .models import Badge, Challenge, CustomerChallenge, Leaderboard
from .gamification_engine import GamificationManager


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@rate_limit(limit=60, window=60)
def customer_gamification_summary(request, customer_id=None):
    """Get gamification summary for customer"""
    
    try:
        tenant = request.user.tenant
        
        if customer_id:
            customer = get_object_or_404(Customer, id=customer_id, tenant=tenant)
        else:
            # Get current user's customer profile
            customer = get_object_or_404(Customer, email=request.user.email, tenant=tenant)
        
        manager = GamificationManager()
        summary = manager.get_customer_gamification_summary(customer)
        
        return Response({
            'success': True,
            'customer_id': customer.id,
            'gamification': summary
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@rate_limit(limit=30, window=60)
def available_challenges(request):
    """Get available challenges for customer"""
    
    try:
        tenant = request.user.tenant
        customer = get_object_or_404(Customer, email=request.user.email, tenant=tenant)
        
        # Get ongoing challenges
        ongoing_challenges = Challenge.objects.filter(
            tenant=tenant,
            is_active=True,
            start_date__lte=timezone.now(),
            end_date__gte=timezone.now()
        )
        
        # Get customer's current challenges
        customer_challenges = CustomerChallenge.objects.filter(
            customer=customer,
            status='active'
        ).values_list('challenge_id', flat=True)
        
        # Available challenges (not yet joined)
        available = ongoing_challenges.exclude(id__in=customer_challenges)
        
        challenges_data = []
        for challenge in available:
            challenges_data.append({
                'id': challenge.id,
                'name': challenge.name,
                'description': challenge.description,
                'challenge_type': challenge.challenge_type,
                'difficulty': challenge.difficulty,
                'target_value': challenge.target_value,
                'points_reward': challenge.points_reward,
                'badge_reward': challenge.badge_reward.name if challenge.badge_reward else None,
                'end_date': challenge.end_date.isoformat(),
                'days_remaining': (challenge.end_date - timezone.now()).days
            })
        
        return Response({
            'success': True,
            'challenges': challenges_data
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@rate_limit(limit=10, window=60)
def join_challenge(request, challenge_id):
    """Join a challenge"""
    
    try:
        tenant = request.user.tenant
        customer = get_object_or_404(Customer, email=request.user.email, tenant=tenant)
        challenge = get_object_or_404(Challenge, id=challenge_id, tenant=tenant)
        
        manager = GamificationManager()
        customer_challenge = manager.challenge_engine.create_challenge_participation(customer, challenge)
        
        if customer_challenge:
            return Response({
                'success': True,
                'message': f'Successfully joined challenge: {challenge.name}',
                'challenge_id': challenge.id
            })
        else:
            return Response({
                'success': False,
                'error': 'Unable to join challenge'
            }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@rate_limit(limit=30, window=60)
def customer_badges(request, customer_id=None):
    """Get customer badges"""
    
    try:
        tenant = request.user.tenant
        
        if customer_id:
            customer = get_object_or_404(Customer, id=customer_id, tenant=tenant)
        else:
            customer = get_object_or_404(Customer, email=request.user.email, tenant=tenant)
        
        badges = customer.badges.select_related('badge').order_by('-earned_at')
        
        badges_data = []
        for customer_badge in badges:
            badge = customer_badge.badge
            badges_data.append({
                'id': badge.id,
                'name': badge.name,
                'description': badge.description,
                'badge_type': badge.badge_type,
                'rarity': badge.rarity,
                'icon': badge.icon,
                'points_reward': badge.points_reward,
                'earned_at': customer_badge.earned_at.isoformat()
            })
        
        return Response({
            'success': True,
            'badges': badges_data,
            'total_badges': len(badges_data)
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@rate_limit(limit=20, window=60)
def leaderboard(request, leaderboard_id):
    """Get leaderboard data"""
    
    try:
        tenant = request.user.tenant
        leaderboard = get_object_or_404(Leaderboard, id=leaderboard_id, tenant=tenant)
        
        if not leaderboard.is_public and not request.user.is_staff:
            return Response({
                'success': False,
                'error': 'Access denied to private leaderboard'
            }, status=status.HTTP_403_FORBIDDEN)
        
        manager = GamificationManager()
        leaderboard_data = manager.leaderboard_engine.generate_leaderboard(leaderboard)
        
        return Response({
            'success': True,
            'leaderboard': {
                'name': leaderboard.name,
                'type': leaderboard.leaderboard_type,
                'timeframe': leaderboard.timeframe,
                'entries': leaderboard_data
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@rate_limit(limit=30, window=60)
def available_leaderboards(request):
    """Get available leaderboards"""
    
    try:
        tenant = request.user.tenant
        
        leaderboards = Leaderboard.objects.filter(
            tenant=tenant,
            is_active=True,
            is_public=True
        )
        
        leaderboards_data = []
        for lb in leaderboards:
            leaderboards_data.append({
                'id': lb.id,
                'name': lb.name,
                'leaderboard_type': lb.leaderboard_type,
                'timeframe': lb.timeframe,
                'max_entries': lb.max_entries
            })
        
        return Response({
            'success': True,
            'leaderboards': leaderboards_data
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# UI Views

@login_required
def gamification_dashboard(request):
    """Gamification dashboard UI"""
    return render(request, 'gamification/dashboard.html', {
        'page_title': 'Gamification Dashboard'
    })


@login_required
def badges_gallery(request):
    """Badges gallery UI"""
    return render(request, 'gamification/badges.html', {
        'page_title': 'Badges Gallery'
    })


@login_required
def challenges_page(request):
    """Challenges page UI"""
    return render(request, 'gamification/challenges.html', {
        'page_title': 'Challenges'
    })


@login_required
def leaderboards_page(request):
    """Leaderboards page UI"""
    return render(request, 'gamification/leaderboards.html', {
        'page_title': 'Leaderboards'
    })
