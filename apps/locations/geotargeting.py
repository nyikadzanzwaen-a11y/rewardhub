"""
Location-based promotional targeting system
"""
import json
import math
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import Distance
from django.db import models
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q

from apps.customers.models import Customer
from apps.locations.models import Location, CheckIn
from apps.loyalty.models import Transaction
from apps.rewards.models import Reward
from apps.ai_services.models import OpenAIService


class GeoTargetingEngine:
    """Advanced location-based promotional targeting"""
    
    def __init__(self):
        self.default_radius_km = 5.0
        self.ai_service = OpenAIService()
    
    def find_nearby_customers(self, location: Location, radius_km: float = None) -> List[Customer]:
        """Find customers within radius of a location"""
        if radius_km is None:
            radius_km = self.default_radius_km
        
        # Get customers who have checked in within radius
        nearby_checkins = CheckIn.objects.filter(
            location__coordinates__distance_lte=(
                location.coordinates, 
                Distance(km=radius_km)
            )
        ).values_list('customer_id', flat=True).distinct()
        
        return Customer.objects.filter(id__in=nearby_checkins)
    
    def get_location_analytics(self, location: Location, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive analytics for a location"""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Basic metrics
        total_checkins = CheckIn.objects.filter(location=location, timestamp__gte=cutoff_date).count()
        unique_customers = CheckIn.objects.filter(
            location=location, 
            timestamp__gte=cutoff_date
        ).values('customer').distinct().count()
        
        # Time-based patterns
        hourly_distribution = {}
        daily_distribution = {}
        
        checkins = CheckIn.objects.filter(location=location, timestamp__gte=cutoff_date)
        
        for checkin in checkins:
            hour = checkin.timestamp.hour
            day = checkin.timestamp.strftime('%A')
            
            hourly_distribution[hour] = hourly_distribution.get(hour, 0) + 1
            daily_distribution[day] = daily_distribution.get(day, 0) + 1
        
        # Peak hours and days
        peak_hour = max(hourly_distribution.items(), key=lambda x: x[1])[0] if hourly_distribution else None
        peak_day = max(daily_distribution.items(), key=lambda x: x[1])[0] if daily_distribution else None
        
        # Customer behavior
        repeat_customers = CheckIn.objects.filter(
            location=location,
            timestamp__gte=cutoff_date
        ).values('customer').annotate(
            visit_count=Count('id')
        ).filter(visit_count__gt=1).count()
        
        # Revenue metrics
        transactions = Transaction.objects.filter(
            location=location,
            timestamp__gte=cutoff_date,
            transaction_type='earn'
        )
        
        total_points_earned = transactions.aggregate(total=Sum('points'))['total'] or 0
        avg_points_per_visit = total_points_earned / max(total_checkins, 1)
        
        return {
            'location_id': location.id,
            'location_name': location.name,
            'period_days': days,
            'total_checkins': total_checkins,
            'unique_customers': unique_customers,
            'repeat_customers': repeat_customers,
            'repeat_rate': repeat_customers / max(unique_customers, 1),
            'avg_visits_per_customer': total_checkins / max(unique_customers, 1),
            'total_points_earned': total_points_earned,
            'avg_points_per_visit': avg_points_per_visit,
            'peak_hour': peak_hour,
            'peak_day': peak_day,
            'hourly_distribution': hourly_distribution,
            'daily_distribution': daily_distribution
        }
    
    def create_geofenced_promotion(self, location: Location, promotion_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a location-specific promotion with geofencing"""
        
        # Extract promotion parameters
        radius_km = promotion_config.get('radius_km', self.default_radius_km)
        target_segments = promotion_config.get('target_segments', [])
        promotion_type = promotion_config.get('type', 'bonus_points')
        value = promotion_config.get('value', 10)
        duration_hours = promotion_config.get('duration_hours', 24)
        
        # Find target customers
        if target_segments:
            target_customers = Customer.objects.filter(
                metadata__segment_name__in=target_segments
            )
        else:
            target_customers = self.find_nearby_customers(location, radius_km)
        
        # Create promotion rules
        promotion_rules = {
            'type': 'location_based',
            'location_id': str(location.id),
            'geofence': {
                'center': {
                    'latitude': location.coordinates.y,
                    'longitude': location.coordinates.x
                },
                'radius_km': radius_km
            },
            'promotion_type': promotion_type,
            'value': value,
            'target_segments': target_segments,
            'valid_until': (timezone.now() + timedelta(hours=duration_hours)).isoformat(),
            'conditions': promotion_config.get('conditions', {})
        }
        
        # Generate personalized messages
        personalized_messages = self._generate_personalized_messages(
            target_customers, location, promotion_config
        )
        
        return {
            'promotion_id': f"geo_{location.id}_{int(timezone.now().timestamp())}",
            'location': {
                'id': location.id,
                'name': location.name,
                'coordinates': [location.coordinates.x, location.coordinates.y]
            },
            'rules': promotion_rules,
            'target_customers': [c.id for c in target_customers],
            'estimated_reach': len(target_customers),
            'personalized_messages': personalized_messages,
            'created_at': timezone.now().isoformat()
        }
    
    def _generate_personalized_messages(self, customers: List[Customer], 
                                      location: Location, config: Dict[str, Any]) -> Dict[str, str]:
        """Generate personalized promotional messages using AI"""
        messages = {}
        
        for customer in customers[:10]:  # Limit for demo
            try:
                # Get customer context
                customer_context = self._get_customer_context(customer, location)
                
                # Generate AI message
                prompt = f"""
                Create a personalized promotional message for a loyalty program customer with these details:
                - Customer segment: {customer_context.get('segment', 'General')}
                - Last visit to {location.name}: {customer_context.get('last_visit_days', 'Never')} days ago
                - Total visits to this location: {customer_context.get('total_visits', 0)}
                - Favorite visit time: {customer_context.get('preferred_time', 'Unknown')}
                - Points balance: {customer_context.get('points_balance', 0)}
                
                Promotion details:
                - Type: {config.get('type', 'bonus_points')}
                - Value: {config.get('value', 10)} points
                - Location: {location.name}
                
                Create a friendly, personalized message (max 160 characters) that encourages them to visit.
                """
                
                response = self.ai_service.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=100,
                    temperature=0.7
                )
                
                message = response.choices[0].message.content.strip()
                messages[str(customer.id)] = message
                
            except Exception as e:
                # Fallback message
                messages[str(customer.id)] = f"Visit {location.name} and earn {config.get('value', 10)} bonus points!"
        
        return messages
    
    def _get_customer_context(self, customer: Customer, location: Location) -> Dict[str, Any]:
        """Get customer context for personalization"""
        
        # Get customer's history at this location
        checkins = CheckIn.objects.filter(customer=customer, location=location)
        total_visits = checkins.count()
        
        last_checkin = checkins.order_by('-timestamp').first()
        last_visit_days = (timezone.now() - last_checkin.timestamp).days if last_checkin else None
        
        # Analyze visit patterns
        preferred_hour = None
        if checkins.exists():
            hour_counts = {}
            for checkin in checkins:
                hour = checkin.timestamp.hour
                hour_counts[hour] = hour_counts.get(hour, 0) + 1
            
            if hour_counts:
                preferred_hour = max(hour_counts.items(), key=lambda x: x[1])[0]
        
        # Get customer segment
        segment = 'General'
        if customer.metadata and 'segment_name' in customer.metadata:
            segment = customer.metadata['segment_name']
        
        # Get points balance
        points_balance = customer.loyalty_account.points_balance if hasattr(customer, 'loyalty_account') else 0
        
        return {
            'segment': segment,
            'total_visits': total_visits,
            'last_visit_days': last_visit_days,
            'preferred_hour': preferred_hour,
            'preferred_time': self._hour_to_time_period(preferred_hour) if preferred_hour else 'Unknown',
            'points_balance': points_balance
        }
    
    def _hour_to_time_period(self, hour: int) -> str:
        """Convert hour to readable time period"""
        if 6 <= hour < 12:
            return 'Morning'
        elif 12 <= hour < 17:
            return 'Afternoon'
        elif 17 <= hour < 21:
            return 'Evening'
        else:
            return 'Night'
    
    def analyze_competitor_locations(self, location: Location, radius_km: float = 2.0) -> Dict[str, Any]:
        """Analyze competitor presence and customer overlap"""
        
        # Find nearby locations (potential competitors)
        nearby_locations = Location.objects.filter(
            coordinates__distance_lte=(location.coordinates, Distance(km=radius_km))
        ).exclude(id=location.id)
        
        competitor_analysis = {}
        
        for competitor in nearby_locations:
            # Calculate distance
            distance = location.coordinates.distance(competitor.coordinates) * 111  # Convert to km
            
            # Find shared customers
            location_customers = set(
                CheckIn.objects.filter(location=location).values_list('customer_id', flat=True)
            )
            competitor_customers = set(
                CheckIn.objects.filter(location=competitor).values_list('customer_id', flat=True)
            )
            
            shared_customers = location_customers.intersection(competitor_customers)
            overlap_rate = len(shared_customers) / max(len(location_customers), 1)
            
            # Analyze visit patterns
            competitor_checkins = CheckIn.objects.filter(location=competitor).count()
            
            competitor_analysis[str(competitor.id)] = {
                'name': competitor.name,
                'distance_km': round(distance, 2),
                'shared_customers': len(shared_customers),
                'overlap_rate': round(overlap_rate, 3),
                'competitor_checkins': competitor_checkins,
                'threat_level': self._assess_threat_level(distance, overlap_rate, competitor_checkins)
            }
        
        return {
            'location_id': location.id,
            'analysis_radius_km': radius_km,
            'competitors_found': len(competitor_analysis),
            'competitor_details': competitor_analysis,
            'recommendations': self._get_competitive_recommendations(competitor_analysis)
        }
    
    def _assess_threat_level(self, distance: float, overlap_rate: float, competitor_activity: int) -> str:
        """Assess competitive threat level"""
        
        # Closer distance = higher threat
        distance_score = max(0, 1 - (distance / 2.0))  # Normalize to 0-1
        
        # Higher overlap = higher threat
        overlap_score = overlap_rate
        
        # Higher activity = higher threat
        activity_score = min(1.0, competitor_activity / 100)  # Normalize to 0-1
        
        threat_score = (distance_score * 0.4 + overlap_score * 0.4 + activity_score * 0.2)
        
        if threat_score >= 0.7:
            return 'High'
        elif threat_score >= 0.4:
            return 'Medium'
        else:
            return 'Low'
    
    def _get_competitive_recommendations(self, competitor_analysis: Dict) -> List[str]:
        """Get recommendations based on competitive analysis"""
        recommendations = []
        
        high_threat_competitors = [
            comp for comp in competitor_analysis.values() 
            if comp['threat_level'] == 'High'
        ]
        
        if high_threat_competitors:
            recommendations.extend([
                "Implement aggressive retention campaigns for shared customers",
                "Offer exclusive location-specific rewards",
                "Increase promotional frequency during peak competitor hours"
            ])
        
        total_overlap = sum(comp['overlap_rate'] for comp in competitor_analysis.values())
        avg_overlap = total_overlap / max(len(competitor_analysis), 1)
        
        if avg_overlap > 0.3:
            recommendations.append("High customer overlap detected - focus on differentiation")
        
        recommendations.extend([
            "Monitor competitor promotional activities",
            "Develop unique value propositions for this location",
            "Consider partnership opportunities with low-threat nearby businesses"
        ])
        
        return recommendations


class LocationIntelligence:
    """Advanced location intelligence and optimization"""
    
    def __init__(self):
        self.geo_engine = GeoTargetingEngine()
    
    def optimize_location_portfolio(self, tenant_id: int) -> Dict[str, Any]:
        """Optimize entire location portfolio for a tenant"""
        
        locations = Location.objects.filter(tenant_id=tenant_id)
        
        if not locations.exists():
            return {'error': 'No locations found for tenant'}
        
        location_performance = {}
        
        for location in locations:
            analytics = self.geo_engine.get_location_analytics(location)
            competitor_analysis = self.geo_engine.analyze_competitor_locations(location)
            
            # Calculate performance score
            performance_score = self._calculate_performance_score(analytics)
            
            location_performance[str(location.id)] = {
                'location_name': location.name,
                'performance_score': performance_score,
                'analytics': analytics,
                'competitive_position': competitor_analysis,
                'optimization_opportunities': self._identify_optimization_opportunities(
                    analytics, competitor_analysis
                )
            }
        
        # Rank locations
        ranked_locations = sorted(
            location_performance.items(),
            key=lambda x: x[1]['performance_score'],
            reverse=True
        )
        
        return {
            'tenant_id': tenant_id,
            'total_locations': len(locations),
            'location_performance': location_performance,
            'top_performers': ranked_locations[:3],
            'underperformers': ranked_locations[-3:],
            'portfolio_recommendations': self._get_portfolio_recommendations(location_performance),
            'analysis_date': timezone.now().isoformat()
        }
    
    def _calculate_performance_score(self, analytics: Dict[str, Any]) -> float:
        """Calculate overall performance score for a location"""
        
        # Normalize metrics (0-1 scale)
        checkins_score = min(1.0, analytics['total_checkins'] / 100)
        unique_customers_score = min(1.0, analytics['unique_customers'] / 50)
        repeat_rate_score = analytics['repeat_rate']
        points_score = min(1.0, analytics['total_points_earned'] / 1000)
        
        # Weighted average
        performance_score = (
            checkins_score * 0.3 +
            unique_customers_score * 0.25 +
            repeat_rate_score * 0.25 +
            points_score * 0.2
        )
        
        return round(performance_score, 3)
    
    def _identify_optimization_opportunities(self, analytics: Dict, competitor_analysis: Dict) -> List[str]:
        """Identify specific optimization opportunities"""
        opportunities = []
        
        # Low engagement opportunities
        if analytics['repeat_rate'] < 0.3:
            opportunities.append("Improve customer retention with loyalty incentives")
        
        if analytics['avg_points_per_visit'] < 10:
            opportunities.append("Increase point earning opportunities")
        
        # Time-based opportunities
        hourly_dist = analytics.get('hourly_distribution', {})
        if hourly_dist:
            low_hours = [hour for hour, count in hourly_dist.items() if count < 2]
            if len(low_hours) > 12:  # More than half the day is slow
                opportunities.append("Implement off-peak hour promotions")
        
        # Competitive opportunities
        high_threat_count = sum(
            1 for comp in competitor_analysis.get('competitor_details', {}).values()
            if comp['threat_level'] == 'High'
        )
        
        if high_threat_count > 2:
            opportunities.append("Develop competitive differentiation strategy")
        
        return opportunities
    
    def _get_portfolio_recommendations(self, location_performance: Dict) -> List[str]:
        """Get portfolio-level recommendations"""
        recommendations = []
        
        scores = [loc['performance_score'] for loc in location_performance.values()]
        avg_score = sum(scores) / len(scores) if scores else 0
        
        if avg_score < 0.5:
            recommendations.append("Overall portfolio performance below average - review strategy")
        
        underperformers = [
            loc for loc in location_performance.values() 
            if loc['performance_score'] < 0.3
        ]
        
        if len(underperformers) > len(location_performance) * 0.3:
            recommendations.append("High number of underperforming locations - consider consolidation")
        
        recommendations.extend([
            "Implement cross-location promotional campaigns",
            "Share best practices from top-performing locations",
            "Consider expansion in high-performing areas"
        ])
        
        return recommendations
