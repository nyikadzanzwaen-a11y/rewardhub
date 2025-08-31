from django.urls import path
from . import views

urlpatterns = [
    # API endpoints
    path('api/nearby/', views.nearby_locations, name='nearby_locations'),
    path('api/checkin/', views.check_in, name='check_in'),
    
    # UI endpoints
    path('map/', views.location_map, name='location_map'),
]