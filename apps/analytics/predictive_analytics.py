"""
Predictive analytics for customer behavior
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

from apps.customers.models import Customer
from apps.loyalty.models import Transaction
from apps.locations.models import CheckIn


class PredictiveAnalyticsEngine:
    """Advanced predictive analytics for customer behavior"""
    
    def __init__(self):
        self.models = {}
        self.scalers = {}
    
    def predict_customer_lifetime_value(self, customers: List[Customer]) -> Dict[str, Any]:
        """Predict customer lifetime value"""
        
        features = []
        for customer in customers:
            try:
                loyalty_account = customer.loyalty_account
                
                # Historical metrics
                transactions = Transaction.objects.filter(loyalty_account=loyalty_account)
                total_transactions = transactions.count()
                
                if total_transactions == 0:
                    continue
                
                # Calculate features
                account_age_days = (timezone.now() - customer.created_at).days if hasattr(customer, 'created_at') else 30
                total_points = loyalty_account.lifetime_points
                avg_transaction = total_points / max(total_transactions, 1)
                
                # Time-based patterns
                last_30_days = timezone.now() - timedelta(days=30)
                recent_transactions = transactions.filter(timestamp__gte=last_30_days).count()
                
                # Engagement metrics
                checkins = CheckIn.objects.filter(customer=customer).count()
                unique_locations = CheckIn.objects.filter(customer=customer).values('location').distinct().count()
                
                # Calculate current CLV (simplified)
                monthly_value = total_points / max(account_age_days / 30, 1)
                current_clv = monthly_value * 12  # Annualized
                
                feature_vector = {
                    'customer_id': customer.id,
                    'account_age_days': account_age_days,
                    'total_transactions': total_transactions,
                    'avg_transaction_value': avg_transaction,
                    'recent_activity': recent_transactions,
                    'total_checkins': checkins,
                    'location_diversity': unique_locations,
                    'monthly_value': monthly_value,
                    'predicted_clv': current_clv * 1.2,  # Simple prediction
                    'confidence': 0.75
                }
                
                features.append(feature_vector)
                
            except Exception as e:
                continue
        
        return {
            'predictions': features,
            'total_customers': len(features),
            'avg_predicted_clv': sum(f['predicted_clv'] for f in features) / max(len(features), 1),
            'high_value_customers': len([f for f in features if f['predicted_clv'] > 1000])
        }
    
    def predict_next_visit(self, customer: Customer) -> Dict[str, Any]:
        """Predict when customer will visit next"""
        
        checkins = CheckIn.objects.filter(customer=customer).order_by('timestamp')
        
        if checkins.count() < 3:
            return {
                'predicted_days': 7,
                'confidence': 0.3,
                'reason': 'Insufficient visit history'
            }
        
        # Calculate visit intervals
        intervals = []
        prev_checkin = None
        
        for checkin in checkins:
            if prev_checkin:
                interval = (checkin.timestamp - prev_checkin.timestamp).days
                intervals.append(interval)
            prev_checkin = checkin
        
        # Simple prediction based on average interval
        avg_interval = sum(intervals) / len(intervals)
        last_visit = checkins.last().timestamp
        days_since_last = (timezone.now() - last_visit).days
        
        predicted_days = max(0, avg_interval - days_since_last)
        
        # Calculate confidence based on consistency
        variance = sum((x - avg_interval) ** 2 for x in intervals) / len(intervals)
        confidence = 1 / (1 + variance / max(avg_interval, 1))
        
        return {
            'predicted_days': int(predicted_days),
            'confidence': min(confidence, 1.0),
            'avg_interval': avg_interval,
            'last_visit_days_ago': days_since_last
        }
    
    def analyze_spending_patterns(self, tenant_id: int) -> Dict[str, Any]:
        """Analyze and predict spending patterns"""
        
        customers = Customer.objects.filter(tenant_id=tenant_id)
        
        patterns = {
            'seasonal_trends': {},
            'weekly_patterns': {},
            'customer_segments': {},
            'predictions': {}
        }
        
        # Analyze seasonal trends
        for month in range(1, 13):
            month_transactions = Transaction.objects.filter(
                loyalty_account__customer__tenant_id=tenant_id,
                timestamp__month=month,
                transaction_type='earn'
            ).aggregate(
                total_points=Sum('points'),
                total_transactions=Count('id')
            )
            
            patterns['seasonal_trends'][month] = {
                'total_points': month_transactions['total_points'] or 0,
                'total_transactions': month_transactions['total_transactions'] or 0
            }
        
        # Weekly patterns
        for day in range(7):  # 0=Monday, 6=Sunday
            day_transactions = Transaction.objects.filter(
                loyalty_account__customer__tenant_id=tenant_id,
                timestamp__week_day=day + 2,  # Django uses 1=Sunday
                transaction_type='earn'
            ).aggregate(
                avg_points=Avg('points'),
                total_transactions=Count('id')
            )
            
            patterns['weekly_patterns'][day] = {
                'avg_points': day_transactions['avg_points'] or 0,
                'total_transactions': day_transactions['total_transactions'] or 0
            }
        
        return patterns


class BehaviorPredictionEngine:
    """Predict specific customer behaviors"""
    
    def predict_redemption_likelihood(self, customer: Customer) -> Dict[str, Any]:
        """Predict likelihood of reward redemption"""
        
        loyalty_account = customer.loyalty_account
        current_balance = loyalty_account.points_balance
        
        # Historical redemption behavior
        transactions = Transaction.objects.filter(loyalty_account=loyalty_account)
        redemptions = transactions.filter(transaction_type='redeem')
        
        total_transactions = transactions.count()
        total_redemptions = redemptions.count()
        
        if total_transactions == 0:
            return {
                'likelihood': 0.1,
                'confidence': 0.2,
                'recommended_action': 'Educate about rewards program'
            }
        
        # Calculate redemption rate
        redemption_rate = total_redemptions / total_transactions
        
        # Factor in current balance
        balance_factor = min(current_balance / 100, 1.0)  # Normalize to 0-1
        
        # Recent activity factor
        last_30_days = timezone.now() - timedelta(days=30)
        recent_activity = transactions.filter(timestamp__gte=last_30_days).count()
        activity_factor = min(recent_activity / 5, 1.0)  # Normalize to 0-1
        
        # Calculate likelihood
        likelihood = (redemption_rate * 0.5 + balance_factor * 0.3 + activity_factor * 0.2)
        
        # Determine recommended action
        if likelihood > 0.7:
            action = 'Send reward recommendations'
        elif likelihood > 0.4:
            action = 'Highlight available rewards'
        else:
            action = 'Educate about reward benefits'
        
        return {
            'likelihood': min(likelihood, 1.0),
            'confidence': 0.8,
            'factors': {
                'redemption_rate': redemption_rate,
                'balance_factor': balance_factor,
                'activity_factor': activity_factor
            },
            'recommended_action': action
        }
    
    def predict_tier_advancement(self, customer: Customer) -> Dict[str, Any]:
        """Predict when customer will advance to next tier"""
        
        loyalty_account = customer.loyalty_account
        current_tier = loyalty_account.tier
        
        if not current_tier:
            return {
                'days_to_next_tier': 30,
                'confidence': 0.3,
                'next_tier': 'Silver'
            }
        
        # Simple tier thresholds
        tier_thresholds = {
            'Bronze': 500,
            'Silver': 1500,
            'Gold': 3000,
            'Platinum': 5000
        }
        
        current_points = loyalty_account.lifetime_points
        current_tier_name = current_tier.name
        
        # Find next tier
        next_tier = None
        points_needed = 0
        
        for tier, threshold in tier_thresholds.items():
            if current_points < threshold:
                next_tier = tier
                points_needed = threshold - current_points
                break
        
        if not next_tier:
            return {
                'days_to_next_tier': None,
                'confidence': 1.0,
                'message': 'Already at highest tier'
            }
        
        # Calculate earning rate
        last_90_days = timezone.now() - timedelta(days=90)
        recent_points = Transaction.objects.filter(
            loyalty_account=loyalty_account,
            timestamp__gte=last_90_days,
            transaction_type='earn'
        ).aggregate(total=Sum('points'))['total'] or 0
        
        daily_earning_rate = recent_points / 90
        
        if daily_earning_rate > 0:
            days_to_next_tier = int(points_needed / daily_earning_rate)
        else:
            days_to_next_tier = 365  # Default if no recent activity
        
        return {
            'days_to_next_tier': days_to_next_tier,
            'points_needed': points_needed,
            'next_tier': next_tier,
            'daily_earning_rate': daily_earning_rate,
            'confidence': 0.7 if daily_earning_rate > 0 else 0.3
        }


class TrendAnalyzer:
    """Analyze trends and patterns in loyalty program data"""
    
    def analyze_program_trends(self, tenant_id: int, months: int = 6) -> Dict[str, Any]:
        """Analyze overall program trends"""
        
        trends = {}
        
        for i in range(months):
            month_start = timezone.now().replace(day=1) - timedelta(days=30 * i)
            month_end = month_start + timedelta(days=30)
            month_key = month_start.strftime('%Y-%m')
            
            # Customer metrics
            new_customers = Customer.objects.filter(
                tenant_id=tenant_id,
                created_at__gte=month_start,
                created_at__lt=month_end
            ).count()
            
            # Transaction metrics
            transactions = Transaction.objects.filter(
                loyalty_account__customer__tenant_id=tenant_id,
                timestamp__gte=month_start,
                timestamp__lt=month_end
            )
            
            total_transactions = transactions.count()
            total_points = transactions.aggregate(total=Sum('points'))['total'] or 0
            
            trends[month_key] = {
                'new_customers': new_customers,
                'total_transactions': total_transactions,
                'total_points': total_points,
                'avg_points_per_transaction': total_points / max(total_transactions, 1)
            }
        
        # Calculate growth rates
        months_list = sorted(trends.keys())
        if len(months_list) >= 2:
            latest = trends[months_list[-1]]
            previous = trends[months_list[-2]]
            
            growth_rates = {
                'customer_growth': ((latest['new_customers'] - previous['new_customers']) / max(previous['new_customers'], 1)) * 100,
                'transaction_growth': ((latest['total_transactions'] - previous['total_transactions']) / max(previous['total_transactions'], 1)) * 100,
                'points_growth': ((latest['total_points'] - previous['total_points']) / max(previous['total_points'], 1)) * 100
            }
        else:
            growth_rates = {}
        
        return {
            'monthly_trends': trends,
            'growth_rates': growth_rates,
            'analysis_period': f'{months} months',
            'generated_at': timezone.now().isoformat()
        }
    
    def forecast_future_performance(self, tenant_id: int, forecast_months: int = 3) -> Dict[str, Any]:
        """Forecast future program performance"""
        
        # Get historical data
        historical_trends = self.analyze_program_trends(tenant_id, 6)
        monthly_data = historical_trends['monthly_trends']
        
        if len(monthly_data) < 3:
            return {
                'error': 'Insufficient historical data for forecasting',
                'required_months': 3,
                'available_months': len(monthly_data)
            }
        
        # Simple linear trend forecasting
        months_list = sorted(monthly_data.keys())
        
        forecasts = {}
        
        for i in range(1, forecast_months + 1):
            forecast_date = timezone.now() + timedelta(days=30 * i)
            forecast_key = forecast_date.strftime('%Y-%m')
            
            # Calculate trends
            recent_months = months_list[-3:]  # Last 3 months
            
            # Customer trend
            customer_values = [monthly_data[month]['new_customers'] for month in recent_months]
            customer_trend = (customer_values[-1] - customer_values[0]) / len(customer_values)
            forecast_customers = max(0, customer_values[-1] + customer_trend * i)
            
            # Transaction trend
            transaction_values = [monthly_data[month]['total_transactions'] for month in recent_months]
            transaction_trend = (transaction_values[-1] - transaction_values[0]) / len(transaction_values)
            forecast_transactions = max(0, transaction_values[-1] + transaction_trend * i)
            
            # Points trend
            points_values = [monthly_data[month]['total_points'] for month in recent_months]
            points_trend = (points_values[-1] - points_values[0]) / len(points_values)
            forecast_points = max(0, points_values[-1] + points_trend * i)
            
            forecasts[forecast_key] = {
                'forecast_new_customers': int(forecast_customers),
                'forecast_transactions': int(forecast_transactions),
                'forecast_points': int(forecast_points),
                'confidence': max(0.3, 0.9 - (i * 0.1))  # Decreasing confidence over time
            }
        
        return {
            'forecasts': forecasts,
            'forecast_period': f'{forecast_months} months',
            'methodology': 'Linear trend analysis',
            'confidence_note': 'Confidence decreases with forecast horizon',
            'generated_at': timezone.now().isoformat()
        }
