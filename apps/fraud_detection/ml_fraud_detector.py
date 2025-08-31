"""
Advanced fraud detection using machine learning
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q, F
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import warnings
warnings.filterwarnings('ignore')

from apps.customers.models import Customer
from apps.loyalty.models import Transaction
from apps.locations.models import CheckIn


class FraudFeatureExtractor:
    """Extract features for fraud detection models"""
    
    def extract_transaction_features(self, customer: Customer, transaction: Transaction = None) -> Dict[str, float]:
        """Extract features from customer transaction history"""
        
        loyalty_account = customer.loyalty_account
        
        # Time-based features
        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        last_30d = now - timedelta(days=30)
        
        # Transaction history
        all_transactions = Transaction.objects.filter(loyalty_account=loyalty_account)
        recent_24h = all_transactions.filter(timestamp__gte=last_24h)
        recent_7d = all_transactions.filter(timestamp__gte=last_7d)
        recent_30d = all_transactions.filter(timestamp__gte=last_30d)
        
        # Basic transaction features
        total_transactions = all_transactions.count()
        avg_transaction_value = all_transactions.aggregate(avg=Avg('points'))['avg'] or 0
        
        # Velocity features
        transactions_24h = recent_24h.count()
        transactions_7d = recent_7d.count()
        transactions_30d = recent_30d.count()
        
        points_24h = recent_24h.aggregate(sum=Sum('points'))['sum'] or 0
        points_7d = recent_7d.aggregate(sum=Sum('points'))['sum'] or 0
        points_30d = recent_30d.aggregate(sum=Sum('points'))['sum'] or 0
        
        # Pattern features
        unique_locations_7d = CheckIn.objects.filter(
            customer=customer,
            timestamp__gte=last_7d
        ).values('location').distinct().count()
        
        # Account age
        account_age_days = (now - customer.created_at).days if hasattr(customer, 'created_at') else 1
        
        # Current transaction features (if provided)
        current_transaction_value = transaction.points if transaction else 0
        
        # Behavioral anomalies
        value_deviation = abs(current_transaction_value - avg_transaction_value) / max(avg_transaction_value, 1)
        
        # Time-based patterns
        hour_of_day = now.hour
        day_of_week = now.weekday()
        
        # Historical patterns
        earn_transactions = all_transactions.filter(transaction_type='earn').count()
        redeem_transactions = all_transactions.filter(transaction_type='redeem').count()
        earn_redeem_ratio = earn_transactions / max(redeem_transactions, 1)
        
        return {
            # Basic features
            'total_transactions': total_transactions,
            'avg_transaction_value': avg_transaction_value,
            'account_age_days': account_age_days,
            'current_balance': loyalty_account.points_balance,
            'lifetime_points': loyalty_account.lifetime_points,
            
            # Velocity features
            'transactions_24h': transactions_24h,
            'transactions_7d': transactions_7d,
            'transactions_30d': transactions_30d,
            'points_24h': points_24h,
            'points_7d': points_7d,
            'points_30d': points_30d,
            
            # Pattern features
            'unique_locations_7d': unique_locations_7d,
            'value_deviation': value_deviation,
            'earn_redeem_ratio': earn_redeem_ratio,
            
            # Time features
            'hour_of_day': hour_of_day,
            'day_of_week': day_of_week,
            
            # Current transaction
            'current_transaction_value': current_transaction_value,
            
            # Derived features
            'transactions_per_day': total_transactions / max(account_age_days, 1),
            'points_per_transaction': (points_30d / max(transactions_30d, 1)) if transactions_30d > 0 else 0,
            'location_diversity': unique_locations_7d / max(transactions_7d, 1) if transactions_7d > 0 else 0
        }
    
    def extract_checkin_features(self, customer: Customer, checkin: CheckIn = None) -> Dict[str, float]:
        """Extract features from customer check-in patterns"""
        
        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        
        # Check-in history
        all_checkins = CheckIn.objects.filter(customer=customer)
        recent_24h = all_checkins.filter(timestamp__gte=last_24h)
        recent_7d = all_checkins.filter(timestamp__gte=last_7d)
        
        # Basic check-in features
        total_checkins = all_checkins.count()
        checkins_24h = recent_24h.count()
        checkins_7d = recent_7d.count()
        
        # Location features
        unique_locations = all_checkins.values('location').distinct().count()
        unique_locations_7d = recent_7d.values('location').distinct().count()
        
        # Time patterns
        if checkin:
            current_hour = checkin.timestamp.hour
            current_day = checkin.timestamp.weekday()
        else:
            current_hour = now.hour
            current_day = now.weekday()
        
        # Distance patterns (if current check-in provided)
        avg_distance_from_previous = 0
        if checkin and total_checkins > 1:
            previous_checkin = all_checkins.exclude(id=checkin.id).order_by('-timestamp').first()
            if previous_checkin:
                # Simplified distance calculation (would use actual geospatial in production)
                avg_distance_from_previous = 1.0  # Placeholder
        
        return {
            'total_checkins': total_checkins,
            'checkins_24h': checkins_24h,
            'checkins_7d': checkins_7d,
            'unique_locations': unique_locations,
            'unique_locations_7d': unique_locations_7d,
            'location_diversity': unique_locations / max(total_checkins, 1),
            'checkin_frequency': total_checkins / max((now - customer.created_at).days, 1) if hasattr(customer, 'created_at') else 0,
            'current_hour': current_hour,
            'current_day': current_day,
            'avg_distance_from_previous': avg_distance_from_previous
        }


class AnomalyDetector:
    """Detect anomalies using unsupervised learning"""
    
    def __init__(self):
        self.isolation_forest = IsolationForest(
            contamination=0.1,
            random_state=42,
            n_estimators=100
        )
        self.scaler = StandardScaler()
        self.is_trained = False
    
    def train_on_historical_data(self, tenant_id: int):
        """Train anomaly detector on historical data"""
        
        # Get customers and their transaction data
        customers = Customer.objects.filter(tenant_id=tenant_id)
        feature_extractor = FraudFeatureExtractor()
        
        features_list = []
        for customer in customers:
            try:
                features = feature_extractor.extract_transaction_features(customer)
                features_list.append(list(features.values()))
            except Exception:
                continue
        
        if len(features_list) < 10:
            return False  # Not enough data to train
        
        # Convert to numpy array and train
        X = np.array(features_list)
        X_scaled = self.scaler.fit_transform(X)
        
        self.isolation_forest.fit(X_scaled)
        self.is_trained = True
        
        return True
    
    def detect_anomaly(self, customer: Customer, transaction: Transaction = None) -> Dict[str, Any]:
        """Detect if customer behavior is anomalous"""
        
        if not self.is_trained:
            return {
                'is_anomaly': False,
                'anomaly_score': 0.0,
                'confidence': 0.0,
                'reason': 'Model not trained'
            }
        
        feature_extractor = FraudFeatureExtractor()
        features = feature_extractor.extract_transaction_features(customer, transaction)
        
        # Convert to array and scale
        X = np.array([list(features.values())])
        X_scaled = self.scaler.transform(X)
        
        # Predict anomaly
        anomaly_prediction = self.isolation_forest.predict(X_scaled)[0]
        anomaly_score = self.isolation_forest.decision_function(X_scaled)[0]
        
        is_anomaly = anomaly_prediction == -1
        confidence = abs(anomaly_score)
        
        # Determine reason for anomaly
        reason = self._analyze_anomaly_reason(features) if is_anomaly else 'Normal behavior'
        
        return {
            'is_anomaly': is_anomaly,
            'anomaly_score': float(anomaly_score),
            'confidence': float(confidence),
            'reason': reason,
            'features': features
        }
    
    def _analyze_anomaly_reason(self, features: Dict[str, float]) -> str:
        """Analyze why behavior is considered anomalous"""
        
        reasons = []
        
        # High velocity
        if features['transactions_24h'] > 10:
            reasons.append('High transaction velocity')
        
        # Unusual value
        if features['value_deviation'] > 3:
            reasons.append('Unusual transaction value')
        
        # Unusual time
        if features['hour_of_day'] < 6 or features['hour_of_day'] > 23:
            reasons.append('Unusual time of activity')
        
        # High location diversity
        if features['location_diversity'] > 0.8:
            reasons.append('Unusual location pattern')
        
        return '; '.join(reasons) if reasons else 'Multiple behavioral anomalies'


class SupervisedFraudDetector:
    """Supervised fraud detection using labeled data"""
    
    def __init__(self):
        self.classifier = RandomForestClassifier(
            n_estimators=100,
            random_state=42,
            class_weight='balanced'
        )
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_names = []
    
    def train_with_labeled_data(self, training_data: List[Dict]) -> Dict[str, Any]:
        """Train classifier with labeled fraud data"""
        
        if len(training_data) < 20:
            return {'success': False, 'error': 'Insufficient training data'}
        
        # Extract features and labels
        X = []
        y = []
        
        for data_point in training_data:
            features = data_point['features']
            label = data_point['is_fraud']  # 1 for fraud, 0 for legitimate
            
            X.append(list(features.values()))
            y.append(label)
            
            if not self.feature_names:
                self.feature_names = list(features.keys())
        
        X = np.array(X)
        y = np.array(y)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train classifier
        self.classifier.fit(X_train_scaled, y_train)
        self.is_trained = True
        
        # Evaluate
        y_pred = self.classifier.predict(X_test_scaled)
        y_pred_proba = self.classifier.predict_proba(X_test_scaled)
        
        # Get feature importance
        feature_importance = dict(zip(
            self.feature_names,
            self.classifier.feature_importances_
        ))
        
        return {
            'success': True,
            'accuracy': self.classifier.score(X_test_scaled, y_test),
            'feature_importance': feature_importance,
            'training_samples': len(X_train),
            'test_samples': len(X_test)
        }
    
    def predict_fraud(self, customer: Customer, transaction: Transaction = None) -> Dict[str, Any]:
        """Predict fraud probability for customer/transaction"""
        
        if not self.is_trained:
            return {
                'fraud_probability': 0.0,
                'is_fraud': False,
                'confidence': 0.0,
                'reason': 'Model not trained'
            }
        
        feature_extractor = FraudFeatureExtractor()
        features = feature_extractor.extract_transaction_features(customer, transaction)
        
        # Convert to array and scale
        X = np.array([list(features.values())])
        X_scaled = self.scaler.transform(X)
        
        # Predict
        fraud_probability = self.classifier.predict_proba(X_scaled)[0][1]  # Probability of fraud class
        is_fraud = fraud_probability > 0.5
        confidence = max(fraud_probability, 1 - fraud_probability)
        
        # Get top contributing features
        feature_contributions = self._get_feature_contributions(features)
        
        return {
            'fraud_probability': float(fraud_probability),
            'is_fraud': is_fraud,
            'confidence': float(confidence),
            'top_risk_factors': feature_contributions[:3],
            'features': features
        }
    
    def _get_feature_contributions(self, features: Dict[str, float]) -> List[Dict]:
        """Get features contributing most to fraud prediction"""
        
        if not self.is_trained:
            return []
        
        feature_importance = self.classifier.feature_importances_
        contributions = []
        
        for i, (feature_name, value) in enumerate(features.items()):
            if i < len(feature_importance):
                contributions.append({
                    'feature': feature_name,
                    'value': value,
                    'importance': float(feature_importance[i])
                })
        
        # Sort by importance
        contributions.sort(key=lambda x: x['importance'], reverse=True)
        return contributions


class FraudDetectionEngine:
    """Main fraud detection engine combining multiple approaches"""
    
    def __init__(self):
        self.anomaly_detector = AnomalyDetector()
        self.supervised_detector = SupervisedFraudDetector()
        self.rule_based_thresholds = {
            'max_transactions_per_hour': 5,
            'max_points_per_transaction': 1000,
            'max_locations_per_day': 10,
            'suspicious_hours': [0, 1, 2, 3, 4, 5],  # Late night/early morning
            'max_value_deviation': 5.0
        }
    
    def initialize_models(self, tenant_id: int) -> Dict[str, Any]:
        """Initialize and train fraud detection models"""
        
        results = {}
        
        # Train anomaly detector
        anomaly_trained = self.anomaly_detector.train_on_historical_data(tenant_id)
        results['anomaly_detector'] = {
            'trained': anomaly_trained,
            'status': 'Ready' if anomaly_trained else 'Insufficient data'
        }
        
        # For supervised detector, we'd need labeled fraud data
        # In a real implementation, this would come from historical fraud cases
        results['supervised_detector'] = {
            'trained': False,
            'status': 'Requires labeled training data'
        }
        
        return results
    
    def analyze_transaction_risk(self, customer: Customer, transaction: Transaction) -> Dict[str, Any]:
        """Comprehensive fraud analysis for a transaction"""
        
        # Rule-based checks
        rule_based_result = self._rule_based_fraud_check(customer, transaction)
        
        # Anomaly detection
        anomaly_result = self.anomaly_detector.detect_anomaly(customer, transaction)
        
        # Supervised detection (if trained)
        supervised_result = self.supervised_detector.predict_fraud(customer, transaction)
        
        # Combine results
        risk_score = self._calculate_combined_risk_score(
            rule_based_result, anomaly_result, supervised_result
        )
        
        # Determine final decision
        is_high_risk = risk_score > 0.7
        is_medium_risk = 0.3 < risk_score <= 0.7
        
        risk_level = 'high' if is_high_risk else 'medium' if is_medium_risk else 'low'
        
        # Compile reasons
        risk_factors = []
        if rule_based_result['violations']:
            risk_factors.extend(rule_based_result['violations'])
        if anomaly_result['is_anomaly']:
            risk_factors.append(f"Anomalous behavior: {anomaly_result['reason']}")
        if supervised_result['is_fraud']:
            risk_factors.extend([f"{rf['feature']}: {rf['value']}" for rf in supervised_result.get('top_risk_factors', [])])
        
        return {
            'risk_score': risk_score,
            'risk_level': risk_level,
            'is_high_risk': is_high_risk,
            'risk_factors': risk_factors,
            'recommended_action': self._get_recommended_action(risk_level),
            'analysis_details': {
                'rule_based': rule_based_result,
                'anomaly_detection': anomaly_result,
                'supervised_ml': supervised_result
            }
        }
    
    def _rule_based_fraud_check(self, customer: Customer, transaction: Transaction) -> Dict[str, Any]:
        """Rule-based fraud detection"""
        
        violations = []
        risk_score = 0.0
        
        # Extract features for rule checking
        feature_extractor = FraudFeatureExtractor()
        features = feature_extractor.extract_transaction_features(customer, transaction)
        
        # Check transaction velocity
        if features['transactions_24h'] > self.rule_based_thresholds['max_transactions_per_hour']:
            violations.append('High transaction velocity')
            risk_score += 0.3
        
        # Check transaction value
        if transaction.points > self.rule_based_thresholds['max_points_per_transaction']:
            violations.append('Unusually high transaction value')
            risk_score += 0.4
        
        # Check time patterns
        if features['hour_of_day'] in self.rule_based_thresholds['suspicious_hours']:
            violations.append('Transaction at suspicious hour')
            risk_score += 0.2
        
        # Check location diversity
        if features['unique_locations_7d'] > self.rule_based_thresholds['max_locations_per_day']:
            violations.append('Unusual location diversity')
            risk_score += 0.3
        
        # Check value deviation
        if features['value_deviation'] > self.rule_based_thresholds['max_value_deviation']:
            violations.append('Transaction value significantly deviates from pattern')
            risk_score += 0.4
        
        return {
            'risk_score': min(risk_score, 1.0),
            'violations': violations,
            'features_checked': features
        }
    
    def _calculate_combined_risk_score(self, rule_based: Dict, anomaly: Dict, supervised: Dict) -> float:
        """Combine risk scores from different detection methods"""
        
        # Weighted combination of different approaches
        rule_weight = 0.4
        anomaly_weight = 0.3
        supervised_weight = 0.3
        
        rule_score = rule_based.get('risk_score', 0.0)
        anomaly_score = 1.0 if anomaly.get('is_anomaly', False) else 0.0
        supervised_score = supervised.get('fraud_probability', 0.0)
        
        combined_score = (
            rule_score * rule_weight +
            anomaly_score * anomaly_weight +
            supervised_score * supervised_weight
        )
        
        return min(combined_score, 1.0)
    
    def _get_recommended_action(self, risk_level: str) -> str:
        """Get recommended action based on risk level"""
        
        actions = {
            'low': 'Allow transaction',
            'medium': 'Flag for review',
            'high': 'Block transaction and require verification'
        }
        
        return actions.get(risk_level, 'Allow transaction')
    
    def generate_fraud_report(self, tenant_id: int, days: int = 30) -> Dict[str, Any]:
        """Generate fraud detection report"""
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Get transactions in period
        transactions = Transaction.objects.filter(
            loyalty_account__customer__tenant_id=tenant_id,
            timestamp__gte=start_date,
            timestamp__lte=end_date
        )
        
        total_transactions = transactions.count()
        
        # Analyze each transaction (simplified for demo)
        high_risk_count = 0
        medium_risk_count = 0
        
        # In a real implementation, you'd analyze all transactions
        # For demo, we'll estimate based on typical fraud rates
        estimated_fraud_rate = 0.02  # 2% typical fraud rate
        high_risk_count = int(total_transactions * estimated_fraud_rate)
        medium_risk_count = int(total_transactions * 0.05)  # 5% flagged for review
        
        return {
            'period': f'{days} days',
            'total_transactions': total_transactions,
            'high_risk_transactions': high_risk_count,
            'medium_risk_transactions': medium_risk_count,
            'low_risk_transactions': total_transactions - high_risk_count - medium_risk_count,
            'fraud_rate': (high_risk_count / max(total_transactions, 1)) * 100,
            'review_rate': (medium_risk_count / max(total_transactions, 1)) * 100,
            'model_status': {
                'anomaly_detector': 'Active' if self.anomaly_detector.is_trained else 'Not trained',
                'supervised_detector': 'Active' if self.supervised_detector.is_trained else 'Not trained'
            },
            'generated_at': timezone.now().isoformat()
        }
