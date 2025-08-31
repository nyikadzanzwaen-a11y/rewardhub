from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required

def dashboard_redirect(request):
    """Redirect to appropriate dashboard based on user type"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    # Check if user is a business owner (has owned tenants)
    if hasattr(request.user, 'owned_tenants') and request.user.owned_tenants.exists():
        return redirect('tenants:tenant_dashboard')
    # Otherwise redirect to customer dashboard
    else:
        return redirect('customers:customer_dashboard')

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Homepage
    path('', include('apps.core.urls')),
    
    # Dashboard redirect
    path('dashboard/', dashboard_redirect, name='dashboard'),
    
    # Authentication
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page="login"), name='logout'),
    path('auth/login/', auth_views.LoginView.as_view(), name='auth_login'),
    path('auth/logout/', auth_views.LogoutView.as_view(next_page="login"), name='auth_logout'),
    path('auth/register/', auth_views.LoginView.as_view(template_name='registration/register.html'), name='register'),
    
    # Admin Dashboard
    path('admin-dashboard/', include('apps.admin_dashboard.urls')),
    
    # Analytics and AI
    path('analytics/', include('apps.analytics.urls')),
    path('gamification/', include('apps.gamification.urls')),
    path('fraud-detection/', include('apps.fraud_detection.urls')),
    
    # API routes
    path('api/customers/', include('apps.customers.urls')),
    path('api/loyalty/', include('apps.loyalty.urls')),
    path('api/rewards/', include('apps.rewards.urls')),
    path('api/locations/', include('apps.locations.urls')),
    
    # Rewards routes
    path('rewards/', include('apps.rewards.urls')),
    
    # Tenant routes
    path('tenant/', include('apps.tenants.urls')),
    
    # Customer UI routes
    path('customer/', include('apps.customers.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)