import uuid
from django.db import models
from django.utils import timezone
from django.conf import settings
import requests
import json
import logging

logger = logging.getLogger(__name__)


class AIRecommendation(models.Model):
    RECOMMENDATION_TYPES = [
        ("reward", "Reward Recommendation"),
        ("offer", "Personalized Offer"),
        ("location", "Location-based"),
        ("tier", "Tier Upgrade"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey("customers.Customer", on_delete=models.CASCADE, related_name="ai_recommendations")
    content = models.JSONField(default=dict)
    recommendation_type = models.CharField(max_length=20, choices=RECOMMENDATION_TYPES, default="reward")
    confidence_score = models.FloatField(default=0.0)
    created_at = models.DateTimeField(default=timezone.now)
    viewed = models.BooleanField(default=False)
    accepted = models.BooleanField(default=False)

    class Meta:
        db_table = "ai_recommendation"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.recommendation_type} for {self.customer.user.email}"

    def is_relevant(self):
        """Check if recommendation is still relevant"""
        # Recommendations older than 30 days are considered stale
        return (timezone.now() - self.created_at).days < 30

    def mark_as_viewed(self):
        """Mark recommendation as viewed"""
        self.viewed = True
        self.save()

    def mark_as_accepted(self):
        """Mark recommendation as accepted"""
        self.accepted = True
        self.viewed = True
        self.save()


class ChurnPrediction(models.Model):
    RISK_LEVELS = [
        ("low", "Low Risk"),
        ("medium", "Medium Risk"),
        ("high", "High Risk"),
        ("critical", "Critical Risk"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.OneToOneField("customers.Customer", on_delete=models.CASCADE, related_name="churn_prediction")
    churn_risk = models.FloatField(help_text="Risk score between 0.0 and 1.0")
    risk_level = models.CharField(max_length=20, choices=RISK_LEVELS, default="low")
    factors = models.JSONField(default=dict, blank=True)
    suggested_actions = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ai_churn_prediction"

    def __str__(self):
        return f"Churn: {self.customer.user.email} ({self.risk_level})"

    def generate_retention_campaign(self):
        """Generate retention campaign based on churn factors"""
        campaign_data = {
            "customer_id": str(self.customer.id),
            "risk_level": self.risk_level,
            "suggested_actions": self.suggested_actions,
            "created_at": timezone.now().isoformat()
        }
        return campaign_data

    def update_prediction(self, new_risk_score, factors=None, suggested_actions=None):
        """Update churn prediction with new data"""
        self.churn_risk = new_risk_score
        
        # Determine risk level based on score
        if new_risk_score >= 0.8:
            self.risk_level = "critical"
        elif new_risk_score >= 0.6:
            self.risk_level = "high"
        elif new_risk_score >= 0.3:
            self.risk_level = "medium"
        else:
            self.risk_level = "low"
            
        if factors:
            self.factors = factors
        if suggested_actions:
            self.suggested_actions = suggested_actions
            
        self.save()


class OpenAIService:
    """Service class for OpenAI API integration"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'OPENAI_API_KEY', '')
        self.model = getattr(settings, 'OPENAI_MODEL', 'gpt-4o-mini')
        self.base_url = "https://api.openai.com/v1"

    def _make_request(self, messages, temperature=0.7):
        """Make request to OpenAI API"""
        if not self.api_key:
            logger.warning("OpenAI API key not configured")
            return None
            
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return None

    def generate_recommendation(self, customer):
        """Generate personalized recommendations for a customer"""
        try:
            # Prepare customer context
            context = {
                "points_balance": customer.loyalty_account.points_balance if hasattr(customer, 'loyalty_account') else 0,
                "tier": customer.get_current_tier().name if customer.get_current_tier() else "None",
                "recent_transactions": [str(t) for t in customer.get_recent_transactions(5)],
                "preferences": customer.preferences,
                "segment_tags": customer.segment_tags
            }
            
            prompt = f"""
            Based on the following customer data, suggest 3 personalized reward recommendations.
            
            Customer data: {json.dumps(context, indent=2)}
            
            Provide recommendations in JSON format:
            [
              {{"title": "Recommendation title", "description": "Brief description", "points_required": 100, "reasoning": "Why recommended"}}
            ]
            """
            
            messages = [
                {"role": "system", "content": "You are a loyalty program AI that provides personalized recommendations."},
                {"role": "user", "content": prompt}
            ]
            
            response = self._make_request(messages)
            if response:
                try:
                    recommendations = json.loads(response)
                    return recommendations
                except json.JSONDecodeError:
                    logger.error("Failed to parse OpenAI response as JSON")
                    
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            
        # Fallback recommendations
        return [
            {"title": "Welcome Bonus", "description": "Get started with bonus points", "points_required": 0, "reasoning": "New customer incentive"},
            {"title": "Check-in Reward", "description": "Visit our locations for points", "points_required": 50, "reasoning": "Encourage location visits"},
            {"title": "Loyalty Bonus", "description": "Bonus for continued engagement", "points_required": 100, "reasoning": "Retention reward"}
        ]

    def predict_churn(self, customer):
        """Predict churn risk for a customer"""
        try:
            # Prepare customer activity data
            recent_transactions = customer.get_recent_transactions(10)
            days_since_last_activity = 0
            
            if hasattr(customer, 'loyalty_account') and customer.loyalty_account.last_activity:
                days_since_last_activity = (timezone.now() - customer.loyalty_account.last_activity).days
                
            context = {
                "days_since_last_activity": days_since_last_activity,
                "transaction_count": len(recent_transactions),
                "points_balance": customer.loyalty_account.points_balance if hasattr(customer, 'loyalty_account') else 0,
                "account_age_days": (timezone.now() - customer.created_at).days
            }
            
            prompt = f"""
            Analyze this customer data and predict churn risk (0.0 to 1.0) and key factors.
            
            Customer data: {json.dumps(context, indent=2)}
            
            Respond in JSON format:
            {{
              "churn_risk": 0.3,
              "factors": ["Low recent activity", "High points balance unused"],
              "suggested_actions": ["Send personalized offer", "Remind about point expiration"]
            }}
            """
            
            messages = [
                {"role": "system", "content": "You are a customer analytics AI that predicts churn risk."},
                {"role": "user", "content": prompt}
            ]
            
            response = self._make_request(messages)
            if response:
                try:
                    return json.loads(response)
                except json.JSONDecodeError:
                    logger.error("Failed to parse churn prediction response")
                    
        except Exception as e:
            logger.error(f"Error predicting churn: {e}")
            
        # Fallback prediction
        return {
            "churn_risk": 0.2,
            "factors": ["Insufficient data for analysis"],
            "suggested_actions": ["Collect more customer interaction data"]
        }

    def segment_customers(self, customers_data):
        """Segment customers based on behavior patterns"""
        # This would be implemented for batch processing
        # For now, return basic segmentation
        return {
            "segments": [
                {"name": "High Value", "criteria": "High lifetime points", "count": 0},
                {"name": "At Risk", "criteria": "Low recent activity", "count": 0},
                {"name": "New Users", "criteria": "Recent signups", "count": 0}
            ]
        }

    def analyze_feedback(self, feedback_text):
        """Analyze customer feedback for sentiment and insights"""
        if not feedback_text:
            return {"sentiment": "neutral", "insights": []}
            
        try:
            prompt = f"""
            Analyze this customer feedback for sentiment and key insights:
            
            Feedback: "{feedback_text}"
            
            Respond in JSON format:
            {{
              "sentiment": "positive/negative/neutral",
              "confidence": 0.8,
              "key_themes": ["theme1", "theme2"],
              "actionable_insights": ["insight1", "insight2"]
            }}
            """
            
            messages = [
                {"role": "system", "content": "You are a feedback analysis AI that extracts sentiment and insights."},
                {"role": "user", "content": prompt}
            ]
            
            response = self._make_request(messages)
            if response:
                try:
                    return json.loads(response)
                except json.JSONDecodeError:
                    logger.error("Failed to parse feedback analysis response")
                    
        except Exception as e:
            logger.error(f"Error analyzing feedback: {e}")
            
        return {"sentiment": "neutral", "insights": ["Unable to analyze feedback"]}

    def generate_location_insights(self, location_data):
        """Generate insights about location performance and optimization"""
        try:
            prompt = f"""
            Analyze this location data and provide insights for optimization:
            
            Location data: {json.dumps(location_data, indent=2)}
            
            Respond in JSON format:
            {{
              "performance_score": 0.7,
              "key_insights": ["High traffic during lunch", "Low weekend activity"],
              "optimization_suggestions": ["Add weekend promotions", "Extend lunch hour offers"]
            }}
            """
            
            messages = [
                {"role": "system", "content": "You are a location analytics AI that provides business insights."},
                {"role": "user", "content": prompt}
            ]
            
            response = self._make_request(messages)
            if response:
                try:
                    return json.loads(response)
                except json.JSONDecodeError:
                    logger.error("Failed to parse location insights response")
                    
        except Exception as e:
            logger.error(f"Error generating location insights: {e}")
            
        return {
            "performance_score": 0.5,
            "key_insights": ["Insufficient data for analysis"],
            "optimization_suggestions": ["Collect more location interaction data"]
        }