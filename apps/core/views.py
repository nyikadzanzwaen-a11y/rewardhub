from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

def home(request):
    """Homepage view - entry point for all users"""
    return render(request, 'home.html')
