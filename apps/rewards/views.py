from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

# Placeholder views for rewards app
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def reward_list(request):
    """Get available rewards"""
    return Response({'rewards': []})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def redeem_reward(request):
    """Redeem a reward"""
    return Response({'success': True, 'message': 'Reward redeemed successfully'})

@login_required
def reward_catalog(request):
    """Reward catalog UI"""
    return render(request, 'rewards/catalog.html')

@login_required
def redemption_history(request):
    """Redemption history UI"""
    return render(request, 'rewards/history.html')