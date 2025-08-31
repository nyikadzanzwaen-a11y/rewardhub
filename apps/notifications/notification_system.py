"""
Automated notification system for customer engagement
"""
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from django.utils import timezone
from django.db import models
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
import requests

from apps.customers.models import Customer
from apps.loyalty.models import Transaction
from apps.locations.models import CheckIn
from apps.rewards.models import Reward


class NotificationEngine:
    """Automated notification system with multiple channels"""
    
    NOTIFICATION_TYPES = {
        'welcome': 'Welcome Message',
        'points_earned': 'Points Earned',
        'tier_upgrade': 'Tier Upgrade',
        'reward_available': 'Reward Available',
        'points_expiring': 'Points Expiring',
        'milestone_reached': 'Milestone Reached',
        'inactivity_reminder': 'Inactivity Reminder',
        'location_promotion': 'Location Promotion',
        'birthday': 'Birthday Offer',
        'churn_prevention': 'Churn Prevention'
    }
    
    CHANNELS = ['email', 'sms', 'push', 'in_app']
    
    def __init__(self):
        self.email_enabled = getattr(settings, 'EMAIL_NOTIFICATIONS_ENABLED', True)
        self.sms_enabled = getattr(settings, 'SMS_NOTIFICATIONS_ENABLED', False)
        self.push_enabled = getattr(settings, 'PUSH_NOTIFICATIONS_ENABLED', False)
    
    def send_notification(self, customer: Customer, notification_type: str, 
                         context: Dict[str, Any], channels: List[str] = None) -> Dict[str, Any]:
        """Send notification through specified channels"""
        
        if channels is None:
            channels = self._get_default_channels(notification_type)
        
        results = {}
        
        for channel in channels:
            try:
                if channel == 'email' and self.email_enabled:
                    results[channel] = self._send_email_notification(
                        customer, notification_type, context
                    )
                elif channel == 'sms' and self.sms_enabled:
                    results[channel] = self._send_sms_notification(
                        customer, notification_type, context
                    )
                elif channel == 'push' and self.push_enabled:
                    results[channel] = self._send_push_notification(
                        customer, notification_type, context
                    )
                elif channel == 'in_app':
                    results[channel] = self._create_in_app_notification(
                        customer, notification_type, context
                    )
                else:
                    results[channel] = {'success': False, 'reason': 'Channel disabled'}
                    
            except Exception as e:
                results[channel] = {'success': False, 'error': str(e)}
        
        # Log notification
        self._log_notification(customer, notification_type, channels, results, context)
        
        return results
    
    def _send_email_notification(self, customer: Customer, notification_type: str, 
                               context: Dict[str, Any]) -> Dict[str, Any]:
        """Send email notification"""
        
        # Get email template
        template_name = f'notifications/email/{notification_type}.html'
        subject_template = f'notifications/email/{notification_type}_subject.txt'
        
        try:
            # Prepare context
            email_context = {
                'customer': customer,
                'customer_name': customer.user.first_name or customer.user.email.split('@')[0],
                'points_balance': customer.loyalty_account.points_balance,
                'tier': customer.loyalty_account.tier.name if customer.loyalty_account.tier else 'Bronze',
                **context
            }
            
            # Render templates
            subject = render_to_string(subject_template, email_context).strip()
            html_message = render_to_string(template_name, email_context)
            
            # Send email
            send_mail(
                subject=subject,
                message='',  # Plain text version
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[customer.user.email],
                fail_silently=False
            )
            
            return {'success': True, 'message': 'Email sent successfully'}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _send_sms_notification(self, customer: Customer, notification_type: str, 
                             context: Dict[str, Any]) -> Dict[str, Any]:
        """Send SMS notification (placeholder implementation)"""
        
        # This would integrate with SMS providers like Twilio, AWS SNS, etc.
        message = self._generate_sms_message(notification_type, context)
        
        # Placeholder for SMS API integration
        try:
            # Example Twilio integration:
            # client = Client(settings.TWILIO_SID, settings.TWILIO_TOKEN)
            # message = client.messages.create(
            #     body=message,
            #     from_=settings.TWILIO_PHONE_NUMBER,
            #     to=customer.phone_number
            # )
            
            return {'success': True, 'message': 'SMS would be sent', 'content': message}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _send_push_notification(self, customer: Customer, notification_type: str, 
                              context: Dict[str, Any]) -> Dict[str, Any]:
        """Send push notification (placeholder implementation)"""
        
        # This would integrate with push notification services like FCM, APNS
        notification_data = {
            'title': self._get_push_title(notification_type, context),
            'body': self._get_push_body(notification_type, context),
            'data': context
        }
        
        try:
            # Example FCM integration:
            # response = requests.post(
            #     'https://fcm.googleapis.com/fcm/send',
            #     headers={
            #         'Authorization': f'key={settings.FCM_SERVER_KEY}',
            #         'Content-Type': 'application/json'
            #     },
            #     json={
            #         'to': customer.fcm_token,
            #         'notification': notification_data
            #     }
            # )
            
            return {'success': True, 'message': 'Push notification would be sent', 'data': notification_data}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _create_in_app_notification(self, customer: Customer, notification_type: str, 
                                  context: Dict[str, Any]) -> Dict[str, Any]:
        """Create in-app notification"""
        
        try:
            # Create notification record in database
            notification = InAppNotification.objects.create(
                customer=customer,
                notification_type=notification_type,
                title=self._get_notification_title(notification_type, context),
                message=self._get_notification_message(notification_type, context),
                data=context,
                is_read=False
            )
            
            return {'success': True, 'notification_id': notification.id}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _get_default_channels(self, notification_type: str) -> List[str]:
        """Get default channels for notification type"""
        
        channel_mapping = {
            'welcome': ['email', 'in_app'],
            'points_earned': ['in_app'],
            'tier_upgrade': ['email', 'push', 'in_app'],
            'reward_available': ['email', 'push', 'in_app'],
            'points_expiring': ['email', 'sms', 'push'],
            'milestone_reached': ['email', 'push', 'in_app'],
            'inactivity_reminder': ['email', 'push'],
            'location_promotion': ['push', 'sms'],
            'birthday': ['email', 'sms', 'push'],
            'churn_prevention': ['email', 'sms', 'push']
        }
        
        return channel_mapping.get(notification_type, ['email', 'in_app'])
    
    def _generate_sms_message(self, notification_type: str, context: Dict[str, Any]) -> str:
        """Generate SMS message content"""
        
        templates = {
            'points_earned': f"🎉 You earned {context.get('points', 0)} points! Balance: {context.get('balance', 0)} pts",
            'tier_upgrade': f"🌟 Congratulations! You've been upgraded to {context.get('new_tier', '')} tier!",
            'reward_available': f"🎁 New reward available: {context.get('reward_name', '')} for {context.get('points_cost', 0)} pts",
            'points_expiring': f"⚠️ {context.get('expiring_points', 0)} points expire in {context.get('days_until_expiry', 0)} days",
            'location_promotion': f"📍 Special offer at {context.get('location_name', '')}: {context.get('offer_description', '')}",
            'birthday': f"🎂 Happy Birthday! Enjoy {context.get('birthday_points', 0)} bonus points on us!",
            'churn_prevention': f"We miss you! Come back and earn {context.get('comeback_bonus', 0)} bonus points"
        }
        
        return templates.get(notification_type, "You have a new loyalty program update!")
    
    def _get_push_title(self, notification_type: str, context: Dict[str, Any]) -> str:
        """Get push notification title"""
        
        titles = {
            'points_earned': "Points Earned!",
            'tier_upgrade': "Tier Upgrade!",
            'reward_available': "New Reward Available",
            'points_expiring': "Points Expiring Soon",
            'milestone_reached': "Milestone Achieved!",
            'location_promotion': "Special Offer Nearby",
            'birthday': "Happy Birthday!",
            'churn_prevention': "We Miss You!"
        }
        
        return titles.get(notification_type, "Loyalty Update")
    
    def _get_push_body(self, notification_type: str, context: Dict[str, Any]) -> str:
        """Get push notification body"""
        
        return self._generate_sms_message(notification_type, context)
    
    def _get_notification_title(self, notification_type: str, context: Dict[str, Any]) -> str:
        """Get in-app notification title"""
        
        return self._get_push_title(notification_type, context)
    
    def _get_notification_message(self, notification_type: str, context: Dict[str, Any]) -> str:
        """Get in-app notification message"""
        
        return self._generate_sms_message(notification_type, context)
    
    def _log_notification(self, customer: Customer, notification_type: str, 
                         channels: List[str], results: Dict[str, Any], context: Dict[str, Any]):
        """Log notification for analytics"""
        
        try:
            NotificationLog.objects.create(
                customer=customer,
                notification_type=notification_type,
                channels=channels,
                success_channels=[ch for ch, result in results.items() if result.get('success')],
                failed_channels=[ch for ch, result in results.items() if not result.get('success')],
                context=context,
                results=results
            )
        except Exception as e:
            print(f"Failed to log notification: {e}")


class AutomatedNotificationTriggers:
    """Automated triggers for various notification scenarios"""
    
    def __init__(self):
        self.notification_engine = NotificationEngine()
    
    def process_transaction_notifications(self, transaction: Transaction):
        """Process notifications triggered by transactions"""
        
        customer = transaction.loyalty_account.customer
        
        # Points earned notification
        if transaction.transaction_type == 'earn':
            context = {
                'points': transaction.points,
                'balance': transaction.loyalty_account.points_balance,
                'transaction_description': transaction.description,
                'location_name': transaction.location.name if transaction.location else None
            }
            
            self.notification_engine.send_notification(
                customer, 'points_earned', context, ['in_app']
            )
        
        # Check for tier upgrade
        self._check_tier_upgrade(customer)
        
        # Check for milestones
        self._check_milestones(customer)
    
    def process_daily_notifications(self):
        """Process daily automated notifications"""
        
        # Points expiring notifications
        self._send_points_expiring_notifications()
        
        # Inactivity reminders
        self._send_inactivity_reminders()
        
        # Birthday notifications
        self._send_birthday_notifications()
    
    def process_weekly_notifications(self):
        """Process weekly automated notifications"""
        
        # Reward availability notifications
        self._send_reward_availability_notifications()
        
        # Churn prevention notifications
        self._send_churn_prevention_notifications()
    
    def _check_tier_upgrade(self, customer: Customer):
        """Check if customer has upgraded tier"""
        
        # This would check if tier changed in recent transaction
        # For now, we'll implement a simple check
        
        loyalty_account = customer.loyalty_account
        current_tier = loyalty_account.tier
        
        if current_tier:
            context = {
                'new_tier': current_tier.name,
                'tier_benefits': self._get_tier_benefits(current_tier.name)
            }
            
            # Check if this is a recent upgrade (simplified)
            recent_transactions = Transaction.objects.filter(
                loyalty_account=loyalty_account,
                timestamp__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            if recent_transactions > 0:  # Simplified upgrade detection
                self.notification_engine.send_notification(
                    customer, 'tier_upgrade', context
                )
    
    def _check_milestones(self, customer: Customer):
        """Check for milestone achievements"""
        
        loyalty_account = customer.loyalty_account
        lifetime_points = loyalty_account.lifetime_points
        
        # Define milestones
        milestones = [100, 500, 1000, 2500, 5000, 10000]
        
        for milestone in milestones:
            if lifetime_points >= milestone:
                # Check if milestone notification already sent
                existing_notification = NotificationLog.objects.filter(
                    customer=customer,
                    notification_type='milestone_reached',
                    context__milestone=milestone
                ).exists()
                
                if not existing_notification:
                    context = {
                        'milestone': milestone,
                        'lifetime_points': lifetime_points,
                        'bonus_points': milestone // 10  # 10% bonus
                    }
                    
                    self.notification_engine.send_notification(
                        customer, 'milestone_reached', context
                    )
                    break  # Only send for highest achieved milestone
    
    def _send_points_expiring_notifications(self):
        """Send notifications for points expiring soon"""
        
        # This would query for customers with points expiring in next 7 days
        # Simplified implementation
        
        expiry_date = timezone.now() + timedelta(days=7)
        
        # In a real implementation, you'd have an expiry system
        # For now, we'll simulate with customers who haven't been active
        
        inactive_customers = Customer.objects.filter(
            loyalty_account__transactions__timestamp__lt=timezone.now() - timedelta(days=30)
        ).distinct()[:10]  # Limit for demo
        
        for customer in inactive_customers:
            context = {
                'expiring_points': 100,  # Placeholder
                'days_until_expiry': 7,
                'balance': customer.loyalty_account.points_balance
            }
            
            self.notification_engine.send_notification(
                customer, 'points_expiring', context
            )
    
    def _send_inactivity_reminders(self):
        """Send reminders to inactive customers"""
        
        cutoff_date = timezone.now() - timedelta(days=14)
        
        inactive_customers = Customer.objects.filter(
            loyalty_account__transactions__timestamp__lt=cutoff_date
        ).distinct()[:20]  # Limit for demo
        
        for customer in inactive_customers:
            last_transaction = customer.loyalty_account.transactions.order_by('-timestamp').first()
            days_inactive = (timezone.now() - last_transaction.timestamp).days if last_transaction else 30
            
            context = {
                'days_inactive': days_inactive,
                'comeback_bonus': 25,
                'balance': customer.loyalty_account.points_balance
            }
            
            self.notification_engine.send_notification(
                customer, 'inactivity_reminder', context
            )
    
    def _send_birthday_notifications(self):
        """Send birthday notifications"""
        
        today = timezone.now().date()
        
        # This would filter customers with birthday today
        # For demo, we'll use a placeholder
        
        birthday_customers = Customer.objects.filter(
            # birth_date__month=today.month,
            # birth_date__day=today.day
        )[:5]  # Placeholder query
        
        for customer in birthday_customers:
            context = {
                'birthday_points': 50,
                'special_offer': "20% off next reward redemption"
            }
            
            self.notification_engine.send_notification(
                customer, 'birthday', context
            )
    
    def _send_reward_availability_notifications(self):
        """Notify customers about available rewards they can afford"""
        
        customers = Customer.objects.all()[:10]  # Limit for demo
        
        for customer in customers:
            balance = customer.loyalty_account.points_balance
            
            # Find affordable rewards
            affordable_rewards = Reward.objects.filter(
                point_cost__lte=balance,
                active=True,
                program=customer.loyalty_account.program
            )[:3]
            
            if affordable_rewards.exists():
                context = {
                    'rewards': [
                        {
                            'name': reward.name,
                            'points_cost': reward.point_cost,
                            'description': reward.description
                        }
                        for reward in affordable_rewards
                    ],
                    'balance': balance
                }
                
                self.notification_engine.send_notification(
                    customer, 'reward_available', context
                )
    
    def _send_churn_prevention_notifications(self):
        """Send churn prevention notifications to at-risk customers"""
        
        # This would integrate with churn prediction system
        # For now, we'll use customers inactive for 30+ days
        
        at_risk_customers = Customer.objects.filter(
            loyalty_account__transactions__timestamp__lt=timezone.now() - timedelta(days=30)
        ).distinct()[:10]
        
        for customer in at_risk_customers:
            context = {
                'comeback_bonus': 100,
                'special_offer': "Double points on next 3 visits",
                'personal_message': f"We miss you, {customer.user.first_name or 'valued customer'}!"
            }
            
            self.notification_engine.send_notification(
                customer, 'churn_prevention', context
            )
    
    def _get_tier_benefits(self, tier_name: str) -> List[str]:
        """Get benefits for a tier"""
        
        benefits = {
            'Bronze': ['Earn 1x points', 'Basic rewards access'],
            'Silver': ['Earn 1.5x points', 'Priority customer service', 'Exclusive rewards'],
            'Gold': ['Earn 2x points', 'Free shipping', 'Birthday bonus', 'VIP events'],
            'Platinum': ['Earn 2.5x points', 'Personal concierge', 'Premium rewards', 'Early access']
        }
        
        return benefits.get(tier_name, ['Standard benefits'])


# Database models for notifications
class InAppNotification(models.Model):
    """In-app notification model"""
    
    customer = models.ForeignKey('customers.Customer', on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=50)
    title = models.CharField(max_length=200)
    message = models.TextField()
    data = models.JSONField(default=dict)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'in_app_notifications'
        ordering = ['-created_at']
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.read_at = timezone.now()
        self.save()


class NotificationLog(models.Model):
    """Notification log for analytics"""
    
    customer = models.ForeignKey('customers.Customer', on_delete=models.CASCADE, related_name='notification_logs')
    notification_type = models.CharField(max_length=50)
    channels = models.JSONField(default=list)
    success_channels = models.JSONField(default=list)
    failed_channels = models.JSONField(default=list)
    context = models.JSONField(default=dict)
    results = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'notification_logs'
        ordering = ['-created_at']


class NotificationPreferences(models.Model):
    """Customer notification preferences"""
    
    customer = models.OneToOneField('customers.Customer', on_delete=models.CASCADE, related_name='notification_preferences')
    email_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)
    push_enabled = models.BooleanField(default=True)
    
    # Notification type preferences
    points_earned = models.BooleanField(default=True)
    tier_upgrades = models.BooleanField(default=True)
    reward_notifications = models.BooleanField(default=True)
    promotional_offers = models.BooleanField(default=True)
    inactivity_reminders = models.BooleanField(default=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notification_preferences'
