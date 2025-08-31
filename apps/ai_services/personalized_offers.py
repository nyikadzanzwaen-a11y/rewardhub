"""
Advanced AI-driven personalized offer generation system
"""
import json
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q, Max
import openai

from apps.customers.models import Customer
from apps.loyalty.models import Transaction
from apps.locations.models import Location, CheckIn
from apps.rewards.models import Reward
from apps.ai_services.models import OpenAIService, AIRecommendation


class PersonalizedOfferEngine:
    """AI-powered personalized offer generation"""
    
    def __init__(self):
        self.ai_service = OpenAIService()
        self.offer_types = {
            'bonus_points': 'Bonus Points Offer',
            'discount': 'Discount Offer',
            'free_reward': 'Free Reward Offer',
            'tier_boost': 'Tier Advancement Offer',
            'location_specific': 'Location-Specific Offer',
            'time_limited': 'Time-Limited Offer',
            'combo_deal': 'Combo Deal Offer',
            'referral_bonus': 'Referral Bonus Offer'
        }
    
    def generate_personalized_offers(self, customer: Customer, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Generate personalized offers for a customer using AI"""
        
        # Gather customer intelligence
        customer_profile = self._build_customer_profile(customer)
        
        # Get behavioral patterns
        behavior_patterns = self._analyze_behavior_patterns(customer)
        
        # Determine optimal offer types
        suitable_offers = self._determine_suitable_offers(customer_profile, behavior_patterns)
        
        # Generate AI-enhanced offers
        personalized_offers = []
        
        for offer_type in suitable_offers[:3]:  # Limit to top 3 offers
            offer = self._generate_ai_offer(customer, offer_type, customer_profile, behavior_patterns, context)
            if offer:
                personalized_offers.append(offer)
        
        return personalized_offers
    
    def _build_customer_profile(self, customer: Customer) -> Dict[str, Any]:
        """Build comprehensive customer profile"""
        
        loyalty_account = customer.loyalty_account
        
        # Basic profile
        profile = {
            'customer_id': customer.id,
            'points_balance': loyalty_account.points_balance,
            'lifetime_points': loyalty_account.lifetime_points,
            'tier': loyalty_account.tier.name if loyalty_account.tier else 'Bronze',
            'account_age_days': (timezone.now() - customer.created_at).days if hasattr(customer, 'created_at') else 0
        }
        
        # Transaction analysis
        transactions = Transaction.objects.filter(loyalty_account=loyalty_account)
        
        profile.update({
            'total_transactions': transactions.count(),
            'avg_transaction_value': transactions.aggregate(avg=Avg('points'))['avg'] or 0,
            'total_earned': transactions.filter(transaction_type='earn').aggregate(sum=Sum('points'))['sum'] or 0,
            'total_redeemed': transactions.filter(transaction_type='redeem').aggregate(sum=Sum('points'))['sum'] or 0,
            'redemption_rate': transactions.filter(transaction_type='redeem').count() / max(transactions.count(), 1)
        })
        
        # Recent activity
        last_30_days = timezone.now() - timedelta(days=30)
        recent_transactions = transactions.filter(timestamp__gte=last_30_days)
        
        profile.update({
            'recent_transactions': recent_transactions.count(),
            'recent_points_earned': recent_transactions.filter(transaction_type='earn').aggregate(sum=Sum('points'))['sum'] or 0,
            'days_since_last_activity': self._days_since_last_activity(customer)
        })
        
        # Location preferences
        checkins = CheckIn.objects.filter(customer=customer)
        favorite_locations = checkins.values('location__name').annotate(
            visit_count=Count('id')
        ).order_by('-visit_count')[:3]
        
        profile['favorite_locations'] = [loc['location__name'] for loc in favorite_locations]
        profile['location_diversity'] = checkins.values('location').distinct().count()
        
        # Segment information
        if customer.metadata and 'segment_name' in customer.metadata:
            profile['segment'] = customer.metadata['segment_name']
            profile['segment_characteristics'] = customer.metadata.get('segment_characteristics', [])
        
        return profile
    
    def _analyze_behavior_patterns(self, customer: Customer) -> Dict[str, Any]:
        """Analyze customer behavior patterns"""
        
        patterns = {}
        
        # Time-based patterns
        checkins = CheckIn.objects.filter(customer=customer)
        
        if checkins.exists():
            # Preferred visit times
            hour_distribution = {}
            day_distribution = {}
            
            for checkin in checkins:
                hour = checkin.timestamp.hour
                day = checkin.timestamp.strftime('%A')
                
                hour_distribution[hour] = hour_distribution.get(hour, 0) + 1
                day_distribution[day] = day_distribution.get(day, 0) + 1
            
            patterns['preferred_hours'] = sorted(hour_distribution.items(), key=lambda x: x[1], reverse=True)[:3]
            patterns['preferred_days'] = sorted(day_distribution.items(), key=lambda x: x[1], reverse=True)[:3]
        
        # Spending patterns
        transactions = Transaction.objects.filter(loyalty_account=customer.loyalty_account)
        
        if transactions.exists():
            # Monthly spending trend
            monthly_spending = {}
            for transaction in transactions.filter(transaction_type='earn'):
                month_key = transaction.timestamp.strftime('%Y-%m')
                monthly_spending[month_key] = monthly_spending.get(month_key, 0) + transaction.points
            
            patterns['spending_trend'] = self._calculate_trend(monthly_spending)
            patterns['avg_monthly_spending'] = sum(monthly_spending.values()) / max(len(monthly_spending), 1)
        
        # Redemption patterns
        redemptions = transactions.filter(transaction_type='redeem')
        if redemptions.exists():
            patterns['avg_redemption_value'] = redemptions.aggregate(avg=Avg('points'))['avg']
            patterns['redemption_frequency'] = redemptions.count() / max(transactions.count(), 1)
            
            # Preferred reward types (would need reward category data)
            patterns['redemption_recency'] = (timezone.now() - redemptions.order_by('-timestamp').first().timestamp).days
        
        # Engagement patterns
        patterns['visit_frequency'] = checkins.count() / max((timezone.now() - customer.created_at).days / 30, 1) if hasattr(customer, 'created_at') else 0
        patterns['consistency_score'] = self._calculate_consistency_score(customer)
        
        return patterns
    
    def _determine_suitable_offers(self, profile: Dict[str, Any], patterns: Dict[str, Any]) -> List[str]:
        """Determine most suitable offer types for customer"""
        
        suitable_offers = []
        
        # High-value customers
        if profile['lifetime_points'] > 1000:
            suitable_offers.extend(['tier_boost', 'free_reward', 'referral_bonus'])
        
        # Low engagement customers
        if profile['days_since_last_activity'] > 14:
            suitable_offers.extend(['bonus_points', 'time_limited', 'comeback_offer'])
        
        # High redemption rate customers
        if profile['redemption_rate'] > 0.3:
            suitable_offers.extend(['discount', 'free_reward', 'combo_deal'])
        
        # Location-loyal customers
        if profile['location_diversity'] <= 2 and profile['favorite_locations']:
            suitable_offers.append('location_specific')
        
        # New customers
        if profile['account_age_days'] < 30:
            suitable_offers.extend(['bonus_points', 'tier_boost'])
        
        # Segment-based offers
        segment = profile.get('segment', '')
        if 'VIP' in segment or 'Champions' in segment:
            suitable_offers.extend(['free_reward', 'tier_boost', 'referral_bonus'])
        elif 'At-Risk' in segment:
            suitable_offers.extend(['bonus_points', 'time_limited', 'discount'])
        
        # Remove duplicates and return top offers
        return list(dict.fromkeys(suitable_offers))[:5]
    
    def _generate_ai_offer(self, customer: Customer, offer_type: str, 
                          profile: Dict[str, Any], patterns: Dict[str, Any], 
                          context: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """Generate AI-enhanced personalized offer"""
        
        try:
            # Prepare context for AI
            ai_context = {
                'customer_profile': profile,
                'behavior_patterns': patterns,
                'offer_type': offer_type,
                'context': context or {}
            }
            
            # Generate offer using AI
            prompt = self._create_offer_prompt(offer_type, ai_context)
            
            response = self.ai_service.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert loyalty program manager creating personalized offers."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.7
            )
            
            ai_response = response.choices[0].message.content.strip()
            
            # Parse AI response and create structured offer
            offer = self._parse_ai_offer_response(ai_response, offer_type, profile)
            
            # Add business logic validation
            validated_offer = self._validate_and_enhance_offer(offer, customer, profile)
            
            return validated_offer
            
        except Exception as e:
            # Fallback to rule-based offer generation
            return self._generate_fallback_offer(offer_type, profile, patterns)
    
    def _create_offer_prompt(self, offer_type: str, context: Dict[str, Any]) -> str:
        """Create AI prompt for offer generation"""
        
        profile = context['customer_profile']
        patterns = context['behavior_patterns']
        
        base_prompt = f"""
        Create a personalized {offer_type} offer for a loyalty program customer with these characteristics:
        
        Customer Profile:
        - Tier: {profile.get('tier', 'Bronze')}
        - Points Balance: {profile.get('points_balance', 0)}
        - Lifetime Points: {profile.get('lifetime_points', 0)}
        - Account Age: {profile.get('account_age_days', 0)} days
        - Segment: {profile.get('segment', 'General')}
        - Recent Activity: {profile.get('days_since_last_activity', 0)} days ago
        
        Behavior Patterns:
        - Visit Frequency: {patterns.get('visit_frequency', 0):.1f} visits/month
        - Redemption Rate: {profile.get('redemption_rate', 0):.1%}
        - Favorite Locations: {', '.join(profile.get('favorite_locations', [])[:2])}
        """
        
        # Add offer-specific instructions
        if offer_type == 'bonus_points':
            base_prompt += """
            
            Create a bonus points offer that:
            1. Provides appropriate point value based on their tier and activity
            2. Has clear, achievable conditions
            3. Includes compelling copy that motivates action
            4. Considers their visit patterns and preferences
            
            Format: JSON with fields: title, description, points_value, conditions, expiry_days, urgency_level
            """
        
        elif offer_type == 'location_specific':
            base_prompt += f"""
            
            Create a location-specific offer for their favorite location: {profile.get('favorite_locations', ['their preferred location'])[0] if profile.get('favorite_locations') else 'their preferred location'}
            
            The offer should:
            1. Be tailored to this specific location
            2. Encourage visits during their preferred times
            3. Provide meaningful value
            4. Create urgency to visit soon
            
            Format: JSON with fields: title, description, location_name, offer_value, conditions, expiry_days
            """
        
        elif offer_type == 'tier_boost':
            base_prompt += """
            
            Create a tier advancement offer that:
            1. Helps them reach the next tier faster
            2. Explains the benefits of tier upgrade
            3. Provides a clear path to advancement
            4. Creates excitement about tier benefits
            
            Format: JSON with fields: title, description, tier_target, points_needed, bonus_multiplier, benefits, expiry_days
            """
        
        return base_prompt
    
    def _parse_ai_offer_response(self, ai_response: str, offer_type: str, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Parse AI response into structured offer"""
        
        try:
            # Try to extract JSON from AI response
            import re
            json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
            
            if json_match:
                offer_data = json.loads(json_match.group())
            else:
                # Fallback parsing
                offer_data = self._extract_offer_from_text(ai_response, offer_type)
            
            # Ensure required fields
            offer = {
                'type': offer_type,
                'title': offer_data.get('title', f'Special {offer_type.replace("_", " ").title()} Offer'),
                'description': offer_data.get('description', 'Exclusive offer just for you!'),
                'ai_generated': True,
                'personalization_score': self._calculate_personalization_score(offer_data, profile),
                'created_at': timezone.now().isoformat(),
                **offer_data
            }
            
            return offer
            
        except Exception as e:
            return self._generate_fallback_offer(offer_type, profile, {})
    
    def _validate_and_enhance_offer(self, offer: Dict[str, Any], customer: Customer, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and enhance offer with business logic"""
        
        # Validate point values
        if 'points_value' in offer:
            max_points = min(profile['points_balance'] * 2, 500)  # Cap at 2x balance or 500
            offer['points_value'] = min(offer['points_value'], max_points)
        
        # Set appropriate expiry
        if 'expiry_days' not in offer:
            offer['expiry_days'] = 7  # Default 7 days
        
        offer['expiry_date'] = (timezone.now() + timedelta(days=offer['expiry_days'])).isoformat()
        
        # Add tracking information
        offer['offer_id'] = f"{offer['type']}_{customer.id}_{int(timezone.now().timestamp())}"
        offer['customer_id'] = customer.id
        offer['estimated_value'] = self._calculate_offer_value(offer, profile)
        
        # Add redemption tracking
        offer['redemption_url'] = f"/offers/{offer['offer_id']}/redeem"
        offer['tracking_code'] = f"PERS_{customer.id}_{offer['type'].upper()}"
        
        return offer
    
    def _generate_fallback_offer(self, offer_type: str, profile: Dict[str, Any], patterns: Dict[str, Any]) -> Dict[str, Any]:
        """Generate fallback offer using rule-based logic"""
        
        fallback_offers = {
            'bonus_points': {
                'title': 'Bonus Points Boost!',
                'description': f'Earn {min(profile["points_balance"] // 2, 50)} bonus points on your next visit!',
                'points_value': min(profile['points_balance'] // 2, 50),
                'conditions': 'Valid on next check-in',
                'expiry_days': 7
            },
            'discount': {
                'title': '20% Off Your Next Reward',
                'description': 'Save 20% points on any reward redemption this week!',
                'discount_percentage': 20,
                'conditions': 'Valid on reward redemptions only',
                'expiry_days': 7
            },
            'location_specific': {
                'title': 'Visit Your Favorite Location',
                'description': f'Double points at {profile.get("favorite_locations", ["your favorite location"])[0] if profile.get("favorite_locations") else "your favorite location"}!',
                'multiplier': 2,
                'location_name': profile.get('favorite_locations', ['Any location'])[0] if profile.get('favorite_locations') else 'Any location',
                'expiry_days': 5
            }
        }
        
        base_offer = fallback_offers.get(offer_type, fallback_offers['bonus_points'])
        
        return {
            'type': offer_type,
            'ai_generated': False,
            'personalization_score': 0.5,
            'created_at': timezone.now().isoformat(),
            **base_offer
        }
    
    def _calculate_personalization_score(self, offer_data: Dict[str, Any], profile: Dict[str, Any]) -> float:
        """Calculate how personalized the offer is"""
        
        score = 0.0
        
        # Check if offer mentions customer-specific data
        offer_text = f"{offer_data.get('title', '')} {offer_data.get('description', '')}".lower()
        
        # Tier-specific content
        if profile.get('tier', '').lower() in offer_text:
            score += 0.2
        
        # Location-specific content
        for location in profile.get('favorite_locations', []):
            if location.lower() in offer_text:
                score += 0.3
                break
        
        # Value appropriateness
        if 'points_value' in offer_data:
            points_ratio = offer_data['points_value'] / max(profile.get('points_balance', 1), 1)
            if 0.1 <= points_ratio <= 0.5:  # Reasonable point value
                score += 0.2
        
        # Timing relevance
        if profile.get('days_since_last_activity', 0) > 7 and 'comeback' in offer_text:
            score += 0.3
        
        return min(score, 1.0)
    
    def _calculate_offer_value(self, offer: Dict[str, Any], profile: Dict[str, Any]) -> float:
        """Calculate estimated monetary value of offer"""
        
        # Simple point-to-dollar conversion (1 point = $0.01)
        point_value = 0.01
        
        if 'points_value' in offer:
            return offer['points_value'] * point_value
        elif 'discount_percentage' in offer:
            avg_redemption = profile.get('avg_transaction_value', 100)
            return (offer['discount_percentage'] / 100) * avg_redemption * point_value
        elif 'multiplier' in offer:
            avg_earning = profile.get('avg_transaction_value', 20)
            return avg_earning * (offer['multiplier'] - 1) * point_value
        
        return 5.0  # Default $5 value
    
    def _days_since_last_activity(self, customer: Customer) -> int:
        """Calculate days since last customer activity"""
        
        last_transaction = Transaction.objects.filter(
            loyalty_account=customer.loyalty_account
        ).order_by('-timestamp').first()
        
        if last_transaction:
            return (timezone.now() - last_transaction.timestamp).days
        
        return 999  # Very high number for inactive customers
    
    def _calculate_trend(self, monthly_data: Dict[str, float]) -> str:
        """Calculate trend from monthly data"""
        
        if len(monthly_data) < 2:
            return 'stable'
        
        values = list(monthly_data.values())
        recent_avg = sum(values[-2:]) / 2
        older_avg = sum(values[:-2]) / max(len(values) - 2, 1)
        
        if recent_avg > older_avg * 1.1:
            return 'increasing'
        elif recent_avg < older_avg * 0.9:
            return 'decreasing'
        else:
            return 'stable'
    
    def _calculate_consistency_score(self, customer: Customer) -> float:
        """Calculate customer consistency score"""
        
        checkins = CheckIn.objects.filter(customer=customer).order_by('timestamp')
        
        if checkins.count() < 3:
            return 0.5
        
        # Calculate intervals between visits
        intervals = []
        prev_checkin = None
        
        for checkin in checkins:
            if prev_checkin:
                interval = (checkin.timestamp - prev_checkin.timestamp).days
                intervals.append(interval)
            prev_checkin = checkin
        
        if not intervals:
            return 0.5
        
        # Lower variance = higher consistency
        avg_interval = sum(intervals) / len(intervals)
        variance = sum((x - avg_interval) ** 2 for x in intervals) / len(intervals)
        
        # Normalize to 0-1 scale
        consistency = 1 / (1 + variance / max(avg_interval, 1))
        
        return min(consistency, 1.0)
    
    def _extract_offer_from_text(self, text: str, offer_type: str) -> Dict[str, Any]:
        """Extract offer details from plain text AI response"""
        
        lines = text.strip().split('\n')
        offer_data = {}
        
        # Simple text parsing
        for line in lines:
            line = line.strip()
            if line.startswith('Title:') or line.startswith('title:'):
                offer_data['title'] = line.split(':', 1)[1].strip()
            elif line.startswith('Description:') or line.startswith('description:'):
                offer_data['description'] = line.split(':', 1)[1].strip()
            elif 'points' in line.lower() and any(char.isdigit() for char in line):
                # Extract point value
                import re
                points_match = re.search(r'(\d+)', line)
                if points_match:
                    offer_data['points_value'] = int(points_match.group(1))
        
        return offer_data


class OfferOptimizationEngine:
    """Optimize offers based on performance data"""
    
    def __init__(self):
        self.offer_engine = PersonalizedOfferEngine()
    
    def analyze_offer_performance(self, tenant_id: int, days: int = 30) -> Dict[str, Any]:
        """Analyze performance of generated offers"""
        
        # This would analyze offer redemption rates, customer engagement, etc.
        # For now, we'll provide a framework
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Get customers who received offers
        customers_with_offers = Customer.objects.filter(
            tenant_id=tenant_id,
            ai_recommendations__created_at__gte=cutoff_date
        ).distinct()
        
        performance_data = {
            'total_offers_generated': customers_with_offers.count(),
            'offer_types': {},
            'personalization_impact': {},
            'recommendations': []
        }
        
        # Analyze by offer type
        for customer in customers_with_offers[:50]:  # Limit for demo
            offers = self.offer_engine.generate_personalized_offers(customer)
            
            for offer in offers:
                offer_type = offer['type']
                if offer_type not in performance_data['offer_types']:
                    performance_data['offer_types'][offer_type] = {
                        'count': 0,
                        'avg_personalization_score': 0,
                        'estimated_value': 0
                    }
                
                performance_data['offer_types'][offer_type]['count'] += 1
                performance_data['offer_types'][offer_type]['avg_personalization_score'] += offer.get('personalization_score', 0)
                performance_data['offer_types'][offer_type]['estimated_value'] += offer.get('estimated_value', 0)
        
        # Calculate averages
        for offer_type, data in performance_data['offer_types'].items():
            if data['count'] > 0:
                data['avg_personalization_score'] /= data['count']
                data['estimated_value'] /= data['count']
        
        # Generate recommendations
        performance_data['recommendations'] = self._generate_optimization_recommendations(
            performance_data['offer_types']
        )
        
        return performance_data
    
    def _generate_optimization_recommendations(self, offer_performance: Dict[str, Any]) -> List[str]:
        """Generate recommendations for offer optimization"""
        
        recommendations = []
        
        # Find best performing offer types
        if offer_performance:
            best_type = max(offer_performance.items(), 
                          key=lambda x: x[1]['avg_personalization_score'])[0]
            recommendations.append(f"Focus on {best_type} offers - highest personalization scores")
        
        # Check for low personalization
        low_personalization = [
            offer_type for offer_type, data in offer_performance.items()
            if data['avg_personalization_score'] < 0.5
        ]
        
        if low_personalization:
            recommendations.append(f"Improve personalization for: {', '.join(low_personalization)}")
        
        recommendations.extend([
            "A/B test different offer values and messaging",
            "Implement real-time offer optimization based on customer response",
            "Expand AI training data with more customer behavior patterns"
        ])
        
        return recommendations
