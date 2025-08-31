"""
Security utilities for fraud prevention and rate limiting
"""
import time
import hashlib
from collections import defaultdict, deque
from datetime import datetime, timedelta
from django.core.cache import cache
from django.conf import settings
from django.http import JsonResponse
from functools import wraps
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """Simple in-memory rate limiter with Redis fallback"""
    
    def __init__(self):
        self.requests = defaultdict(deque)
        
    def is_allowed(self, key, limit, window_seconds):
        """Check if request is within rate limit"""
        now = time.time()
        window_start = now - window_seconds
        
        # Try Redis first, fallback to memory
        try:
            cache_key = f"rate_limit:{key}"
            requests = cache.get(cache_key, [])
            
            # Remove old requests
            requests = [req_time for req_time in requests if req_time > window_start]
            
            if len(requests) >= limit:
                return False
                
            # Add current request
            requests.append(now)
            cache.set(cache_key, requests, window_seconds)
            return True
            
        except Exception:
            # Fallback to memory
            requests = self.requests[key]
            
            # Remove old requests
            while requests and requests[0] <= window_start:
                requests.popleft()
                
            if len(requests) >= limit:
                return False
                
            requests.append(now)
            return True

# Global rate limiter instance
rate_limiter = RateLimiter()

def rate_limit(limit=60, window=60, key_func=None):
    """
    Rate limiting decorator
    
    Args:
        limit: Number of requests allowed
        window: Time window in seconds
        key_func: Function to generate rate limit key (default: IP address)
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Generate rate limit key
            if key_func:
                key = key_func(request)
            else:
                key = get_client_ip(request)
                
            if not rate_limiter.is_allowed(key, limit, window):
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'retry_after': window
                }, status=429)
                
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

class FraudDetector:
    """Basic fraud detection mechanisms"""
    
    @staticmethod
    def detect_duplicate_transactions(user, transaction_type, amount, location_id=None, window_minutes=5):
        """Detect duplicate transactions within time window"""
        from apps.loyalty.models import LoyaltyTransaction
        
        cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
        
        filters = {
            'customer__user': user,
            'transaction_type': transaction_type,
            'points': amount,
            'timestamp__gte': cutoff_time
        }
        
        if location_id:
            filters['location_id'] = location_id
            
        duplicate_count = LoyaltyTransaction.objects.filter(**filters).count()
        
        if duplicate_count > 0:
            logger.warning(f"Duplicate transaction detected for user {user.id}")
            return True
            
        return False
    
    @staticmethod
    def detect_suspicious_checkin_pattern(user, location_id, window_hours=1):
        """Detect suspicious check-in patterns"""
        from apps.loyalty.models import LoyaltyTransaction
        
        cutoff_time = datetime.now() - timedelta(hours=window_hours)
        
        checkin_count = LoyaltyTransaction.objects.filter(
            customer__user=user,
            transaction_type='earn',
            location_id=location_id,
            timestamp__gte=cutoff_time
        ).count()
        
        # Flag if more than 3 check-ins at same location within hour
        if checkin_count > 3:
            logger.warning(f"Suspicious check-in pattern for user {user.id} at location {location_id}")
            return True
            
        return False
    
    @staticmethod
    def detect_velocity_fraud(user, window_minutes=10, max_transactions=10):
        """Detect high-velocity transaction patterns"""
        from apps.loyalty.models import LoyaltyTransaction
        
        cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
        
        transaction_count = LoyaltyTransaction.objects.filter(
            customer__user=user,
            timestamp__gte=cutoff_time
        ).count()
        
        if transaction_count > max_transactions:
            logger.warning(f"High velocity transactions detected for user {user.id}")
            return True
            
        return False
    
    @staticmethod
    def detect_geolocation_fraud(user, current_lat, current_lng, max_distance_km=100):
        """Detect impossible travel between locations"""
        from apps.loyalty.models import LoyaltyTransaction
        from django.contrib.gis.geos import Point
        from django.contrib.gis.measure import Distance
        
        # Get last location-based transaction within last hour
        cutoff_time = datetime.now() - timedelta(hours=1)
        
        last_transaction = LoyaltyTransaction.objects.filter(
            customer__user=user,
            location__isnull=False,
            timestamp__gte=cutoff_time
        ).order_by('-timestamp').first()
        
        if last_transaction and last_transaction.location:
            last_point = last_transaction.location.coordinates
            current_point = Point(current_lng, current_lat)
            
            distance = last_point.distance(current_point) * 111  # Convert to km
            
            if distance > max_distance_km:
                logger.warning(f"Impossible travel detected for user {user.id}: {distance}km")
                return True
                
        return False

def fraud_check(check_duplicates=True, check_velocity=True, check_location=False):
    """
    Fraud detection decorator
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user
            
            if not user.is_authenticated:
                return view_func(request, *args, **kwargs)
            
            # Check for duplicate transactions
            if check_duplicates and hasattr(request, 'json'):
                data = getattr(request, 'json', {})
                if FraudDetector.detect_duplicate_transactions(
                    user, 
                    data.get('transaction_type', 'earn'),
                    data.get('points', 0),
                    data.get('location_id')
                ):
                    return JsonResponse({
                        'error': 'Duplicate transaction detected'
                    }, status=400)
            
            # Check transaction velocity
            if check_velocity and FraudDetector.detect_velocity_fraud(user):
                return JsonResponse({
                    'error': 'Too many transactions in short time period'
                }, status=429)
            
            # Check geolocation fraud
            if check_location and hasattr(request, 'json'):
                data = getattr(request, 'json', {})
                lat = data.get('latitude')
                lng = data.get('longitude')
                
                if lat and lng and FraudDetector.detect_geolocation_fraud(user, lat, lng):
                    return JsonResponse({
                        'error': 'Suspicious location activity detected'
                    }, status=400)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def generate_transaction_hash(user_id, transaction_type, points, location_id=None):
    """Generate hash for transaction deduplication"""
    data = f"{user_id}:{transaction_type}:{points}:{location_id or 'none'}:{int(time.time() // 300)}"  # 5-minute window
    return hashlib.md5(data.encode()).hexdigest()

class SecurityMiddleware:
    """Custom security middleware for additional protection"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Add security headers
        response = self.get_response(request)
        
        # Security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        return response

def validate_request_data(required_fields=None, optional_fields=None):
    """
    Validate request data decorator
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            try:
                import json
                data = json.loads(request.body) if request.body else {}
                request.json = data
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Invalid JSON'}, status=400)
            
            # Check required fields
            if required_fields:
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    return JsonResponse({
                        'error': f'Missing required fields: {", ".join(missing_fields)}'
                    }, status=400)
            
            # Validate field types and values
            for field, value in data.items():
                if field in ['latitude', 'longitude'] and not isinstance(value, (int, float)):
                    return JsonResponse({
                        'error': f'Invalid {field}: must be a number'
                    }, status=400)
                
                if field == 'points' and (not isinstance(value, int) or value < 0):
                    return JsonResponse({
                        'error': 'Invalid points: must be a positive integer'
                    }, status=400)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

# Rate limit configurations for different endpoints
RATE_LIMITS = {
    'checkin': {'limit': 10, 'window': 3600},  # 10 check-ins per hour
    'redeem': {'limit': 5, 'window': 3600},    # 5 redemptions per hour
    'login': {'limit': 5, 'window': 900},      # 5 login attempts per 15 minutes
    'api_general': {'limit': 100, 'window': 3600},  # 100 API calls per hour
}

def get_rate_limit_key(request, endpoint_type):
    """Generate rate limit key based on user and endpoint"""
    if request.user.is_authenticated:
        return f"{endpoint_type}:user:{request.user.id}"
    else:
        return f"{endpoint_type}:ip:{get_client_ip(request)}"
