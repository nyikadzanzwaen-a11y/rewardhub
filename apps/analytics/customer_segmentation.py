"""
AI-powered customer segmentation system
"""
import json
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
from django.db import models
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
import pandas as pd

from apps.customers.models import Customer, LoyaltyAccount
from apps.loyalty.models import Transaction
from apps.locations.models import CheckIn
from apps.ai_services.models import OpenAIService


class CustomerSegmentationEngine:
    """AI-powered customer segmentation using machine learning"""
    
    SEGMENT_TYPES = {
        'behavioral': 'Behavioral Segmentation',
        'value': 'Value-based Segmentation', 
        'engagement': 'Engagement Segmentation',
        'lifecycle': 'Customer Lifecycle Segmentation',
        'geographic': 'Geographic Segmentation'
    }
    
    def __init__(self):
        self.scaler = StandardScaler()
        self.pca = PCA(n_components=0.95)  # Retain 95% of variance
        self.kmeans = None
        
    def extract_customer_features(self, customers: List[Customer]) -> pd.DataFrame:
        """Extract features for customer segmentation"""
        features = []
        
        for customer in customers:
            try:
                loyalty_account = customer.loyalty_account
                
                # Basic metrics
                total_points = loyalty_account.lifetime_points
                current_balance = loyalty_account.points_balance
                
                # Transaction analysis
                transactions = Transaction.objects.filter(loyalty_account=loyalty_account)
                total_transactions = transactions.count()
                
                # Time-based metrics
                now = timezone.now()
                last_30_days = now - timedelta(days=30)
                last_90_days = now - timedelta(days=90)
                
                recent_transactions = transactions.filter(timestamp__gte=last_30_days)
                quarterly_transactions = transactions.filter(timestamp__gte=last_90_days)
                
                # Frequency metrics
                avg_transaction_value = transactions.aggregate(
                    avg_points=Avg('points')
                )['avg_points'] or 0
                
                transaction_frequency_30d = recent_transactions.count()
                transaction_frequency_90d = quarterly_transactions.count()
                
                # Engagement metrics
                checkins = CheckIn.objects.filter(customer=customer)
                total_checkins = checkins.count()
                recent_checkins = checkins.filter(timestamp__gte=last_30_days).count()
                
                # Redemption behavior
                redemptions = transactions.filter(transaction_type='redeem')
                total_redemptions = redemptions.count()
                redemption_rate = total_redemptions / max(total_transactions, 1)
                
                # Recency (days since last activity)
                last_transaction = transactions.order_by('-timestamp').first()
                days_since_last_activity = 0
                if last_transaction:
                    days_since_last_activity = (now - last_transaction.timestamp).days
                
                # Location diversity
                unique_locations = checkins.values('location').distinct().count()
                
                # Tier information
                tier_level = 0
                if loyalty_account.tier:
                    tier_mapping = {'bronze': 1, 'silver': 2, 'gold': 3, 'platinum': 4}
                    tier_level = tier_mapping.get(loyalty_account.tier.name.lower(), 0)
                
                # Account age
                account_age_days = (now - customer.created_at).days if hasattr(customer, 'created_at') else 0
                
                feature_vector = {
                    'customer_id': customer.id,
                    'total_points': total_points,
                    'current_balance': current_balance,
                    'total_transactions': total_transactions,
                    'avg_transaction_value': avg_transaction_value,
                    'transaction_frequency_30d': transaction_frequency_30d,
                    'transaction_frequency_90d': transaction_frequency_90d,
                    'total_checkins': total_checkins,
                    'recent_checkins': recent_checkins,
                    'total_redemptions': total_redemptions,
                    'redemption_rate': redemption_rate,
                    'days_since_last_activity': days_since_last_activity,
                    'unique_locations': unique_locations,
                    'tier_level': tier_level,
                    'account_age_days': account_age_days,
                    'points_per_day': total_points / max(account_age_days, 1),
                    'checkin_frequency': total_checkins / max(account_age_days, 1),
                }
                
                features.append(feature_vector)
                
            except Exception as e:
                print(f"Error processing customer {customer.id}: {e}")
                continue
        
        return pd.DataFrame(features)
    
    def perform_segmentation(self, tenant_id: int, n_clusters: int = 5) -> Dict[str, Any]:
        """Perform customer segmentation using K-means clustering"""
        
        # Get customers for tenant
        customers = Customer.objects.filter(tenant_id=tenant_id)
        
        if customers.count() < n_clusters:
            return {
                'success': False,
                'error': f'Not enough customers ({customers.count()}) for {n_clusters} clusters'
            }
        
        # Extract features
        df = self.extract_customer_features(list(customers))
        
        if df.empty:
            return {'success': False, 'error': 'No valid customer data found'}
        
        # Prepare features for clustering (exclude customer_id)
        feature_columns = [col for col in df.columns if col != 'customer_id']
        X = df[feature_columns].fillna(0)
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Apply PCA for dimensionality reduction
        X_pca = self.pca.fit_transform(X_scaled)
        
        # Perform K-means clustering
        self.kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        cluster_labels = self.kmeans.fit_predict(X_pca)
        
        # Add cluster labels to dataframe
        df['cluster'] = cluster_labels
        
        # Analyze clusters
        cluster_analysis = self._analyze_clusters(df, feature_columns)
        
        # Generate segment names and descriptions
        segments = self._generate_segment_descriptions(cluster_analysis)
        
        # Save segmentation results
        segmentation_results = {
            'tenant_id': tenant_id,
            'n_clusters': n_clusters,
            'total_customers': len(df),
            'segments': segments,
            'cluster_analysis': cluster_analysis,
            'feature_importance': self._calculate_feature_importance(X, feature_columns),
            'timestamp': timezone.now().isoformat()
        }
        
        # Update customer segments in database
        self._update_customer_segments(df, segments)
        
        return {
            'success': True,
            'results': segmentation_results
        }
    
    def _analyze_clusters(self, df: pd.DataFrame, feature_columns: List[str]) -> Dict[int, Dict]:
        """Analyze characteristics of each cluster"""
        cluster_analysis = {}
        
        for cluster_id in df['cluster'].unique():
            cluster_data = df[df['cluster'] == cluster_id]
            cluster_size = len(cluster_data)
            
            # Calculate cluster statistics
            cluster_stats = {}
            for feature in feature_columns:
                cluster_stats[feature] = {
                    'mean': float(cluster_data[feature].mean()),
                    'median': float(cluster_data[feature].median()),
                    'std': float(cluster_data[feature].std()),
                    'min': float(cluster_data[feature].min()),
                    'max': float(cluster_data[feature].max())
                }
            
            cluster_analysis[cluster_id] = {
                'size': cluster_size,
                'percentage': (cluster_size / len(df)) * 100,
                'stats': cluster_stats,
                'customer_ids': cluster_data['customer_id'].tolist()
            }
        
        return cluster_analysis
    
    def _generate_segment_descriptions(self, cluster_analysis: Dict) -> Dict[int, Dict]:
        """Generate human-readable segment descriptions using AI"""
        segments = {}
        
        for cluster_id, analysis in cluster_analysis.items():
            stats = analysis['stats']
            
            # Rule-based segment naming
            segment_name, segment_description = self._classify_segment(stats, analysis['size'])
            
            # Use AI to enhance descriptions
            ai_description = self._get_ai_segment_description(stats, segment_name)
            
            segments[cluster_id] = {
                'name': segment_name,
                'description': segment_description,
                'ai_description': ai_description,
                'size': analysis['size'],
                'percentage': analysis['percentage'],
                'characteristics': self._extract_key_characteristics(stats),
                'recommended_actions': self._get_recommended_actions(segment_name, stats)
            }
        
        return segments
    
    def _classify_segment(self, stats: Dict, size: int) -> Tuple[str, str]:
        """Classify segment based on statistical characteristics"""
        
        # High-value characteristics
        high_points = stats['total_points']['mean'] > 1000
        high_frequency = stats['transaction_frequency_30d']['mean'] > 5
        high_engagement = stats['recent_checkins']['mean'] > 10
        high_redemption = stats['redemption_rate']['mean'] > 0.3
        
        # Low engagement characteristics
        low_activity = stats['days_since_last_activity']['mean'] > 30
        low_frequency = stats['transaction_frequency_30d']['mean'] < 2
        
        # Segment classification logic
        if high_points and high_frequency and high_engagement:
            return "VIP Champions", "High-value, highly engaged customers who frequently interact and earn points"
        
        elif high_points and high_redemption:
            return "Reward Seekers", "High-value customers who actively redeem their points for rewards"
        
        elif high_frequency and high_engagement:
            return "Loyal Enthusiasts", "Highly engaged customers who frequently visit and participate"
        
        elif low_activity and low_frequency:
            return "At-Risk Customers", "Customers showing signs of disengagement and potential churn"
        
        elif stats['account_age_days']['mean'] < 30:
            return "New Joiners", "Recently acquired customers still exploring the program"
        
        elif stats['transaction_frequency_90d']['mean'] > stats['transaction_frequency_30d']['mean'] * 2:
            return "Declining Actives", "Previously active customers showing reduced engagement"
        
        elif stats['unique_locations']['mean'] > 3:
            return "Location Explorers", "Customers who visit multiple locations regularly"
        
        else:
            return "Casual Users", "Moderate engagement customers with steady but limited activity"
    
    def _get_ai_segment_description(self, stats: Dict, segment_name: str) -> str:
        """Get AI-enhanced segment description"""
        try:
            ai_service = OpenAIService()
            
            # Prepare stats summary for AI
            key_stats = {
                'avg_total_points': round(stats['total_points']['mean'], 2),
                'avg_monthly_transactions': round(stats['transaction_frequency_30d']['mean'], 2),
                'avg_redemption_rate': round(stats['redemption_rate']['mean'], 2),
                'avg_days_since_last_activity': round(stats['days_since_last_activity']['mean'], 2)
            }
            
            prompt = f"""
            Analyze this customer segment called "{segment_name}" with the following characteristics:
            - Average total points: {key_stats['avg_total_points']}
            - Average monthly transactions: {key_stats['avg_monthly_transactions']}
            - Average redemption rate: {key_stats['avg_redemption_rate']}
            - Average days since last activity: {key_stats['avg_days_since_last_activity']}
            
            Provide a concise 2-3 sentence description of this customer segment's behavior and value to the business.
            """
            
            response = ai_service.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            return f"AI analysis unavailable: {str(e)}"
    
    def _extract_key_characteristics(self, stats: Dict) -> List[str]:
        """Extract key characteristics for a segment"""
        characteristics = []
        
        # Points behavior
        if stats['total_points']['mean'] > 1000:
            characteristics.append("High lifetime value")
        elif stats['total_points']['mean'] < 100:
            characteristics.append("Low lifetime value")
        
        # Engagement level
        if stats['recent_checkins']['mean'] > 10:
            characteristics.append("Highly engaged")
        elif stats['recent_checkins']['mean'] < 2:
            characteristics.append("Low engagement")
        
        # Transaction frequency
        if stats['transaction_frequency_30d']['mean'] > 5:
            characteristics.append("Frequent transactor")
        elif stats['transaction_frequency_30d']['mean'] < 1:
            characteristics.append("Infrequent transactor")
        
        # Redemption behavior
        if stats['redemption_rate']['mean'] > 0.5:
            characteristics.append("Active redeemer")
        elif stats['redemption_rate']['mean'] < 0.1:
            characteristics.append("Point accumulator")
        
        # Recency
        if stats['days_since_last_activity']['mean'] > 60:
            characteristics.append("At risk of churn")
        elif stats['days_since_last_activity']['mean'] < 7:
            characteristics.append("Recently active")
        
        return characteristics
    
    def _get_recommended_actions(self, segment_name: str, stats: Dict) -> List[str]:
        """Get recommended marketing actions for each segment"""
        actions = []
        
        if "VIP" in segment_name or "Champions" in segment_name:
            actions = [
                "Offer exclusive VIP rewards and experiences",
                "Provide early access to new products/services",
                "Create personalized high-value offers",
                "Implement referral incentives"
            ]
        
        elif "At-Risk" in segment_name:
            actions = [
                "Send re-engagement campaigns with special offers",
                "Provide bonus points for return visits",
                "Conduct satisfaction surveys",
                "Offer personalized incentives to return"
            ]
        
        elif "New Joiners" in segment_name:
            actions = [
                "Send welcome series with program education",
                "Offer onboarding bonuses and easy wins",
                "Provide tutorial content and tips",
                "Create low-barrier engagement opportunities"
            ]
        
        elif "Reward Seekers" in segment_name:
            actions = [
                "Highlight new and limited-time rewards",
                "Send reward availability notifications",
                "Offer bonus point promotions",
                "Create tiered reward structures"
            ]
        
        else:
            actions = [
                "Send targeted promotional offers",
                "Encourage increased engagement with bonuses",
                "Provide relevant product recommendations",
                "Create personalized communication campaigns"
            ]
        
        return actions
    
    def _calculate_feature_importance(self, X: np.ndarray, feature_columns: List[str]) -> Dict[str, float]:
        """Calculate feature importance for segmentation"""
        if self.kmeans is None:
            return {}
        
        # Calculate variance of cluster centers for each feature
        cluster_centers = self.kmeans.cluster_centers_
        feature_importance = {}
        
        for i, feature in enumerate(feature_columns):
            if i < cluster_centers.shape[1]:
                # Calculate variance across cluster centers for this feature
                variance = np.var(cluster_centers[:, i])
                feature_importance[feature] = float(variance)
        
        # Normalize importance scores
        max_importance = max(feature_importance.values()) if feature_importance else 1
        for feature in feature_importance:
            feature_importance[feature] = feature_importance[feature] / max_importance
        
        return feature_importance
    
    def _update_customer_segments(self, df: pd.DataFrame, segments: Dict):
        """Update customer segment information in database"""
        for _, row in df.iterrows():
            try:
                customer = Customer.objects.get(id=row['customer_id'])
                cluster_id = row['cluster']
                segment_info = segments.get(cluster_id, {})
                
                # Store segment information in customer metadata
                if not hasattr(customer, 'metadata') or customer.metadata is None:
                    customer.metadata = {}
                
                customer.metadata.update({
                    'segment_id': cluster_id,
                    'segment_name': segment_info.get('name', 'Unknown'),
                    'segment_description': segment_info.get('description', ''),
                    'segmentation_date': timezone.now().isoformat(),
                    'segment_characteristics': segment_info.get('characteristics', [])
                })
                
                customer.save()
                
            except Customer.DoesNotExist:
                continue
            except Exception as e:
                print(f"Error updating customer {row['customer_id']}: {e}")
                continue


class SegmentationAnalytics:
    """Analytics and reporting for customer segmentation"""
    
    @staticmethod
    def get_segment_performance(tenant_id: int, days: int = 30) -> Dict[str, Any]:
        """Analyze performance metrics by customer segment"""
        
        cutoff_date = timezone.now() - timedelta(days=days)
        customers = Customer.objects.filter(tenant_id=tenant_id)
        
        segment_performance = {}
        
        for customer in customers:
            if not customer.metadata or 'segment_name' not in customer.metadata:
                continue
            
            segment_name = customer.metadata['segment_name']
            
            if segment_name not in segment_performance:
                segment_performance[segment_name] = {
                    'customer_count': 0,
                    'total_points_earned': 0,
                    'total_points_redeemed': 0,
                    'total_transactions': 0,
                    'avg_transaction_value': 0,
                    'retention_rate': 0
                }
            
            # Get customer metrics
            transactions = Transaction.objects.filter(
                loyalty_account=customer.loyalty_account,
                timestamp__gte=cutoff_date
            )
            
            points_earned = transactions.filter(transaction_type='earn').aggregate(
                total=Sum('points')
            )['total'] or 0
            
            points_redeemed = transactions.filter(transaction_type='redeem').aggregate(
                total=Sum('points')
            )['total'] or 0
            
            transaction_count = transactions.count()
            
            # Update segment metrics
            segment_performance[segment_name]['customer_count'] += 1
            segment_performance[segment_name]['total_points_earned'] += points_earned
            segment_performance[segment_name]['total_points_redeemed'] += points_redeemed
            segment_performance[segment_name]['total_transactions'] += transaction_count
        
        # Calculate averages
        for segment_name, metrics in segment_performance.items():
            customer_count = metrics['customer_count']
            if customer_count > 0:
                metrics['avg_points_earned'] = metrics['total_points_earned'] / customer_count
                metrics['avg_points_redeemed'] = metrics['total_points_redeemed'] / customer_count
                metrics['avg_transactions'] = metrics['total_transactions'] / customer_count
        
        return segment_performance
    
    @staticmethod
    def get_segment_trends(tenant_id: int, months: int = 6) -> Dict[str, Any]:
        """Analyze segment trends over time"""
        
        trends = {}
        
        for month_offset in range(months):
            month_start = timezone.now().replace(day=1) - timedelta(days=30 * month_offset)
            month_end = month_start + timedelta(days=30)
            
            month_key = month_start.strftime('%Y-%m')
            trends[month_key] = SegmentationAnalytics.get_segment_performance(
                tenant_id, 
                days=(timezone.now() - month_start).days
            )
        
        return trends
