"""
AI-powered churn prediction and prevention system
"""
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
from django.db import models
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q, Max
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score
import joblib
import warnings
warnings.filterwarnings('ignore')

from apps.customers.models import Customer, LoyaltyAccount
from apps.loyalty.models import Transaction
from apps.locations.models import CheckIn
from apps.ai_services.models import OpenAIService


class ChurnPredictionEngine:
    """Machine learning-based churn prediction system"""
    
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.feature_columns = []
        self.churn_threshold_days = 60  # Consider churned if no activity for 60 days
        
    def extract_churn_features(self, customers: List[Customer], 
                              prediction_date: datetime = None) -> pd.DataFrame:
        """Extract features for churn prediction"""
        if prediction_date is None:
            prediction_date = timezone.now()
        
        features = []
        
        for customer in customers:
            try:
                loyalty_account = customer.loyalty_account
                
                # Define time windows
                cutoff_30d = prediction_date - timedelta(days=30)
                cutoff_60d = prediction_date - timedelta(days=60)
                cutoff_90d = prediction_date - timedelta(days=90)
                cutoff_180d = prediction_date - timedelta(days=180)
                
                # Get all transactions
                all_transactions = Transaction.objects.filter(
                    loyalty_account=loyalty_account,
                    timestamp__lt=prediction_date
                )
                
                # Basic account metrics
                account_age_days = (prediction_date - customer.created_at).days if hasattr(customer, 'created_at') else 0
                total_points = loyalty_account.lifetime_points
                current_balance = loyalty_account.points_balance
                
                # Transaction patterns
                total_transactions = all_transactions.count()
                transactions_30d = all_transactions.filter(timestamp__gte=cutoff_30d).count()
                transactions_60d = all_transactions.filter(timestamp__gte=cutoff_60d).count()
                transactions_90d = all_transactions.filter(timestamp__gte=cutoff_90d).count()
                
                # Engagement metrics
                checkins = CheckIn.objects.filter(customer=customer, timestamp__lt=prediction_date)
                total_checkins = checkins.count()
                checkins_30d = checkins.filter(timestamp__gte=cutoff_30d).count()
                checkins_60d = checkins.filter(timestamp__gte=cutoff_60d).count()
                
                # Recency metrics
                last_transaction = all_transactions.order_by('-timestamp').first()
                days_since_last_transaction = (prediction_date - last_transaction.timestamp).days if last_transaction else 999
                
                last_checkin = checkins.order_by('-timestamp').first()
                days_since_last_checkin = (prediction_date - last_checkin.timestamp).days if last_checkin else 999
                
                # Frequency metrics
                avg_transactions_per_month = total_transactions / max(account_age_days / 30, 1)
                avg_checkins_per_month = total_checkins / max(account_age_days / 30, 1)
                
                # Trend analysis
                trend_30_60 = transactions_30d - all_transactions.filter(
                    timestamp__gte=cutoff_60d, timestamp__lt=cutoff_30d
                ).count()
                
                trend_60_90 = transactions_60d - all_transactions.filter(
                    timestamp__gte=cutoff_90d, timestamp__lt=cutoff_60d
                ).count()
                
                # Redemption behavior
                redemptions = all_transactions.filter(transaction_type='redeem')
                total_redemptions = redemptions.count()
                redemptions_30d = redemptions.filter(timestamp__gte=cutoff_30d).count()
                redemption_rate = total_redemptions / max(total_transactions, 1)
                
                # Value metrics
                avg_transaction_value = all_transactions.aggregate(avg=Avg('points'))['avg'] or 0
                total_earned = all_transactions.filter(transaction_type='earn').aggregate(sum=Sum('points'))['sum'] or 0
                total_redeemed = all_transactions.filter(transaction_type='redeem').aggregate(sum=Sum('points'))['sum'] or 0
                
                # Location diversity
                unique_locations = checkins.values('location').distinct().count()
                
                # Tier information
                tier_level = 0
                if loyalty_account.tier:
                    tier_mapping = {'bronze': 1, 'silver': 2, 'gold': 3, 'platinum': 4}
                    tier_level = tier_mapping.get(loyalty_account.tier.name.lower(), 0)
                
                # Seasonal patterns
                current_month = prediction_date.month
                same_month_last_year = all_transactions.filter(
                    timestamp__month=current_month,
                    timestamp__year=prediction_date.year - 1
                ).count()
                
                # Determine churn label (for training)
                is_churned = days_since_last_transaction > self.churn_threshold_days
                
                feature_vector = {
                    'customer_id': customer.id,
                    'account_age_days': account_age_days,
                    'total_points': total_points,
                    'current_balance': current_balance,
                    'total_transactions': total_transactions,
                    'transactions_30d': transactions_30d,
                    'transactions_60d': transactions_60d,
                    'transactions_90d': transactions_90d,
                    'total_checkins': total_checkins,
                    'checkins_30d': checkins_30d,
                    'checkins_60d': checkins_60d,
                    'days_since_last_transaction': min(days_since_last_transaction, 365),
                    'days_since_last_checkin': min(days_since_last_checkin, 365),
                    'avg_transactions_per_month': avg_transactions_per_month,
                    'avg_checkins_per_month': avg_checkins_per_month,
                    'trend_30_60': trend_30_60,
                    'trend_60_90': trend_60_90,
                    'total_redemptions': total_redemptions,
                    'redemptions_30d': redemptions_30d,
                    'redemption_rate': redemption_rate,
                    'avg_transaction_value': avg_transaction_value,
                    'total_earned': total_earned,
                    'total_redeemed': total_redeemed,
                    'unique_locations': unique_locations,
                    'tier_level': tier_level,
                    'same_month_last_year': same_month_last_year,
                    'balance_to_earned_ratio': current_balance / max(total_earned, 1),
                    'activity_consistency': min(transactions_30d, transactions_60d, transactions_90d),
                    'is_churned': is_churned
                }
                
                features.append(feature_vector)
                
            except Exception as e:
                print(f"Error processing customer {customer.id}: {e}")
                continue
        
        return pd.DataFrame(features)
    
    def train_churn_model(self, tenant_id: int) -> Dict[str, Any]:
        """Train churn prediction model"""
        
        # Get historical data
        customers = Customer.objects.filter(tenant_id=tenant_id)
        
        if customers.count() < 100:
            return {
                'success': False,
                'error': f'Insufficient data: need at least 100 customers, got {customers.count()}'
            }
        
        # Extract features from historical data
        df = self.extract_churn_features(list(customers))
        
        if df.empty:
            return {'success': False, 'error': 'No valid customer data found'}
        
        # Prepare features and target
        feature_columns = [col for col in df.columns if col not in ['customer_id', 'is_churned']]
        self.feature_columns = feature_columns
        
        X = df[feature_columns].fillna(0)
        y = df['is_churned'].astype(int)
        
        # Check class balance
        churn_rate = y.mean()
        if churn_rate < 0.05 or churn_rate > 0.95:
            return {
                'success': False,
                'error': f'Imbalanced dataset: churn rate is {churn_rate:.2%}'
            }
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train multiple models and select best
        models = {
            'random_forest': RandomForestClassifier(n_estimators=100, random_state=42),
            'gradient_boosting': GradientBoostingClassifier(random_state=42),
            'logistic_regression': LogisticRegression(random_state=42, max_iter=1000)
        }
        
        best_model = None
        best_score = 0
        model_results = {}
        
        for name, model in models.items():
            if name == 'logistic_regression':
                model.fit(X_train_scaled, y_train)
                y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]
            else:
                model.fit(X_train, y_train)
                y_pred_proba = model.predict_proba(X_test)[:, 1]
            
            auc_score = roc_auc_score(y_test, y_pred_proba)
            model_results[name] = {
                'auc_score': auc_score,
                'model': model
            }
            
            if auc_score > best_score:
                best_score = auc_score
                best_model = model
        
        self.model = best_model
        
        # Feature importance
        if hasattr(best_model, 'feature_importances_'):
            feature_importance = dict(zip(feature_columns, best_model.feature_importances_))
        else:
            feature_importance = dict(zip(feature_columns, abs(best_model.coef_[0])))
        
        # Sort by importance
        feature_importance = dict(sorted(feature_importance.items(), 
                                       key=lambda x: x[1], reverse=True))
        
        return {
            'success': True,
            'model_performance': model_results,
            'best_model': type(best_model).__name__,
            'best_auc_score': best_score,
            'feature_importance': feature_importance,
            'churn_rate': churn_rate,
            'training_samples': len(X_train),
            'test_samples': len(X_test)
        }
    
    def predict_churn_risk(self, customers: List[Customer]) -> List[Dict[str, Any]]:
        """Predict churn risk for customers"""
        
        if self.model is None:
            return [{'error': 'Model not trained'} for _ in customers]
        
        # Extract features
        df = self.extract_churn_features(customers)
        
        if df.empty:
            return [{'error': 'No valid data'} for _ in customers]
        
        # Prepare features
        X = df[self.feature_columns].fillna(0)
        
        # Scale if using logistic regression
        if isinstance(self.model, LogisticRegression):
            X = self.scaler.transform(X)
        
        # Predict probabilities
        churn_probabilities = self.model.predict_proba(X)[:, 1]
        
        # Generate results
        results = []
        for i, (_, row) in enumerate(df.iterrows()):
            churn_prob = churn_probabilities[i]
            risk_level = self._categorize_risk(churn_prob)
            
            result = {
                'customer_id': row['customer_id'],
                'churn_probability': float(churn_prob),
                'risk_level': risk_level,
                'days_since_last_activity': row['days_since_last_transaction'],
                'key_risk_factors': self._identify_risk_factors(row, churn_prob),
                'recommended_actions': self._get_retention_actions(risk_level, row)
            }
            
            results.append(result)
        
        return results
    
    def _categorize_risk(self, probability: float) -> str:
        """Categorize churn risk level"""
        if probability >= 0.8:
            return 'Critical'
        elif probability >= 0.6:
            return 'High'
        elif probability >= 0.4:
            return 'Medium'
        elif probability >= 0.2:
            return 'Low'
        else:
            return 'Very Low'
    
    def _identify_risk_factors(self, customer_data: pd.Series, churn_prob: float) -> List[str]:
        """Identify key risk factors for a customer"""
        risk_factors = []
        
        if customer_data['days_since_last_transaction'] > 30:
            risk_factors.append(f"No activity for {customer_data['days_since_last_transaction']} days")
        
        if customer_data['transactions_30d'] == 0:
            risk_factors.append("No transactions in last 30 days")
        
        if customer_data['trend_30_60'] < -2:
            risk_factors.append("Declining transaction frequency")
        
        if customer_data['redemption_rate'] < 0.1 and customer_data['current_balance'] > 100:
            risk_factors.append("High balance but low redemption activity")
        
        if customer_data['unique_locations'] <= 1:
            risk_factors.append("Limited location engagement")
        
        if customer_data['avg_transactions_per_month'] < 1:
            risk_factors.append("Low overall engagement")
        
        return risk_factors[:3]  # Return top 3 factors
    
    def _get_retention_actions(self, risk_level: str, customer_data: pd.Series) -> List[str]:
        """Get recommended retention actions"""
        actions = []
        
        if risk_level in ['Critical', 'High']:
            actions.extend([
                "Send immediate personalized re-engagement offer",
                "Provide bonus points for next visit",
                "Offer exclusive rewards or experiences"
            ])
            
            if customer_data['current_balance'] > 50:
                actions.append("Remind about available rewards to redeem")
        
        elif risk_level == 'Medium':
            actions.extend([
                "Send targeted promotional campaign",
                "Offer location-based incentives",
                "Provide program education and tips"
            ])
        
        else:  # Low or Very Low risk
            actions.extend([
                "Continue regular engagement campaigns",
                "Offer tier advancement opportunities",
                "Provide new feature announcements"
            ])
        
        # Add specific actions based on customer behavior
        if customer_data['redemption_rate'] < 0.1:
            actions.append("Educate about reward redemption process")
        
        if customer_data['unique_locations'] <= 1:
            actions.append("Encourage visits to other locations")
        
        return actions[:4]  # Return top 4 actions


class ChurnPreventionCampaignManager:
    """Manage automated churn prevention campaigns"""
    
    def __init__(self):
        self.churn_engine = ChurnPredictionEngine()
    
    def create_prevention_campaigns(self, tenant_id: int) -> Dict[str, Any]:
        """Create targeted prevention campaigns for at-risk customers"""
        
        customers = Customer.objects.filter(tenant_id=tenant_id)
        churn_predictions = self.churn_engine.predict_churn_risk(list(customers))
        
        campaigns = {
            'Critical': [],
            'High': [],
            'Medium': [],
            'Low': []
        }
        
        for prediction in churn_predictions:
            if 'error' in prediction:
                continue
            
            risk_level = prediction['risk_level']
            if risk_level in campaigns:
                campaigns[risk_level].append(prediction)
        
        # Generate campaign strategies
        campaign_strategies = {}
        
        for risk_level, at_risk_customers in campaigns.items():
            if not at_risk_customers:
                continue
            
            strategy = self._create_campaign_strategy(risk_level, at_risk_customers)
            campaign_strategies[risk_level] = strategy
        
        return {
            'total_at_risk': sum(len(customers) for customers in campaigns.values()),
            'risk_distribution': {level: len(customers) for level, customers in campaigns.items()},
            'campaign_strategies': campaign_strategies,
            'generated_at': timezone.now().isoformat()
        }
    
    def _create_campaign_strategy(self, risk_level: str, customers: List[Dict]) -> Dict[str, Any]:
        """Create campaign strategy for specific risk level"""
        
        customer_count = len(customers)
        
        # Analyze common risk factors
        all_risk_factors = []
        for customer in customers:
            all_risk_factors.extend(customer.get('key_risk_factors', []))
        
        # Count factor frequency
        factor_counts = {}
        for factor in all_risk_factors:
            factor_counts[factor] = factor_counts.get(factor, 0) + 1
        
        common_factors = sorted(factor_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        
        # Define campaign parameters based on risk level
        if risk_level == 'Critical':
            urgency = 'Immediate'
            channels = ['Email', 'SMS', 'Push Notification', 'Phone Call']
            offer_type = 'High-value bonus points or exclusive rewards'
            frequency = 'Daily for 1 week'
        elif risk_level == 'High':
            urgency = 'Within 24 hours'
            channels = ['Email', 'SMS', 'Push Notification']
            offer_type = 'Bonus points or special discounts'
            frequency = 'Every 2 days for 2 weeks'
        elif risk_level == 'Medium':
            urgency = 'Within 3 days'
            channels = ['Email', 'Push Notification']
            offer_type = 'Targeted promotions or location incentives'
            frequency = 'Weekly for 1 month'
        else:
            urgency = 'Within 1 week'
            channels = ['Email']
            offer_type = 'Regular promotional content'
            frequency = 'Bi-weekly'
        
        return {
            'customer_count': customer_count,
            'urgency': urgency,
            'channels': channels,
            'offer_type': offer_type,
            'frequency': frequency,
            'common_risk_factors': [factor for factor, count in common_factors],
            'personalization_level': 'High' if risk_level in ['Critical', 'High'] else 'Medium',
            'success_metrics': ['Re-engagement rate', 'Transaction increase', 'Retention rate'],
            'budget_priority': 'High' if risk_level in ['Critical', 'High'] else 'Medium'
        }


class ChurnAnalytics:
    """Analytics and reporting for churn prediction"""
    
    @staticmethod
    def generate_churn_report(tenant_id: int) -> Dict[str, Any]:
        """Generate comprehensive churn analysis report"""
        
        engine = ChurnPredictionEngine()
        customers = Customer.objects.filter(tenant_id=tenant_id)
        
        # Get churn predictions
        predictions = engine.predict_churn_risk(list(customers))
        
        # Analyze risk distribution
        risk_distribution = {}
        total_customers = len([p for p in predictions if 'error' not in p])
        
        for prediction in predictions:
            if 'error' in prediction:
                continue
            
            risk_level = prediction['risk_level']
            risk_distribution[risk_level] = risk_distribution.get(risk_level, 0) + 1
        
        # Calculate percentages
        risk_percentages = {
            level: (count / total_customers * 100) if total_customers > 0 else 0
            for level, count in risk_distribution.items()
        }
        
        # Identify trends
        high_risk_customers = [p for p in predictions 
                             if p.get('risk_level') in ['Critical', 'High']]
        
        # Common risk factors
        all_risk_factors = []
        for customer in high_risk_customers:
            all_risk_factors.extend(customer.get('key_risk_factors', []))
        
        factor_analysis = {}
        for factor in set(all_risk_factors):
            factor_analysis[factor] = all_risk_factors.count(factor)
        
        return {
            'total_customers': total_customers,
            'risk_distribution': risk_distribution,
            'risk_percentages': risk_percentages,
            'high_risk_count': len(high_risk_customers),
            'estimated_revenue_at_risk': len(high_risk_customers) * 100,  # Placeholder calculation
            'common_risk_factors': dict(sorted(factor_analysis.items(), 
                                             key=lambda x: x[1], reverse=True)),
            'recommendations': ChurnAnalytics._get_strategic_recommendations(risk_distribution),
            'generated_at': timezone.now().isoformat()
        }
    
    @staticmethod
    def _get_strategic_recommendations(risk_distribution: Dict[str, int]) -> List[str]:
        """Get strategic recommendations based on risk distribution"""
        recommendations = []
        
        total_at_risk = risk_distribution.get('Critical', 0) + risk_distribution.get('High', 0)
        total_customers = sum(risk_distribution.values())
        
        if total_at_risk > total_customers * 0.2:
            recommendations.append("High churn risk detected - implement immediate retention campaigns")
        
        if risk_distribution.get('Critical', 0) > 0:
            recommendations.append("Deploy emergency retention tactics for critical risk customers")
        
        if risk_distribution.get('Medium', 0) > total_customers * 0.3:
            recommendations.append("Focus on engagement programs to prevent medium-risk customers from escalating")
        
        recommendations.extend([
            "Implement predictive analytics dashboard for real-time monitoring",
            "Develop automated trigger campaigns based on risk levels",
            "Conduct customer satisfaction surveys for high-risk segments"
        ])
        
        return recommendations
