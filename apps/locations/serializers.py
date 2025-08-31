from rest_framework import serializers
# from rest_framework_gis.serializers import GeoFeatureModelSerializer  # Removed GIS dependency
from .models import Location, CheckIn


class LocationSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    coordinates = serializers.SerializerMethodField()
    
    class Meta:
        model = Location
        fields = ['id', 'name', 'address', 'coordinates', 'radius_m', 'tenant_name', 'created_at']
        read_only_fields = ['id', 'tenant_name', 'created_at']
    
    def get_coordinates(self, obj):
        return {
            'latitude': obj.latitude,
            'longitude': obj.longitude
        }


class CheckInSerializer(serializers.ModelSerializer):
    customer_email = serializers.CharField(source='customer.user.email', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    coordinates = serializers.SerializerMethodField()
    
    class Meta:
        model = CheckIn
        fields = ['id', 'customer_email', 'location_name', 'coordinates', 'timestamp', 'verified']
        read_only_fields = ['id', 'customer_email', 'location_name', 'timestamp', 'verified']
    
    def get_coordinates(self, obj):
        return {
            'latitude': obj.latitude,
            'longitude': obj.longitude
        }


class CheckInCreateSerializer(serializers.Serializer):
    location_id = serializers.UUIDField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    device_info = serializers.JSONField(required=False, default=dict)