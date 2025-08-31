"""
Advanced rule engine for complex loyalty scenarios
"""
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from django.db import models
from django.utils import timezone
from .models import Rule, Transaction
from apps.customers.models import Customer, LoyaltyAccount


class AdvancedRuleEngine:
    """Enhanced rule engine with complex conditions and actions"""
    
    def __init__(self):
        self.rule_processors = {
            'time_based': self._process_time_based_rule,
            'frequency_based': self._process_frequency_rule,
            'tier_based': self._process_tier_rule,
            'combo_based': self._process_combo_rule,
            'milestone_based': self._process_milestone_rule,
            'seasonal': self._process_seasonal_rule,
            'location_chain': self._process_location_chain_rule,
        }
    
    def evaluate_advanced_rule(self, rule: Rule, customer: Customer, 
                             action_data: Dict = None, location=None) -> Dict[str, Any]:
        """Evaluate advanced rule with complex conditions"""
        
        if not rule.conditions:
            return {'applicable': False, 'reason': 'No conditions defined'}
        
        conditions = json.loads(rule.conditions) if isinstance(rule.conditions, str) else rule.conditions
        rule_type = conditions.get('type', 'basic')
        
        if rule_type in self.rule_processors:
            return self.rule_processors[rule_type](rule, customer, conditions, action_data, location)
        
        return self._process_basic_rule(rule, customer, conditions, action_data, location)
    
    def _process_time_based_rule(self, rule: Rule, customer: Customer, 
                               conditions: Dict, action_data: Dict, location) -> Dict[str, Any]:
        """Process time-based rules (happy hour, weekend bonuses, etc.)"""
        now = timezone.now()
        
        # Check time windows
        time_windows = conditions.get('time_windows', [])
        current_applicable = False
        
        for window in time_windows:
            start_time = datetime.strptime(window['start'], '%H:%M').time()
            end_time = datetime.strptime(window['end'], '%H:%M').time()
            days = window.get('days', [])  # 0=Monday, 6=Sunday
            
            if not days or now.weekday() in days:
                if start_time <= now.time() <= end_time:
                    current_applicable = True
                    break
        
        if not current_applicable:
            return {'applicable': False, 'reason': 'Outside time window'}
        
        # Calculate multiplier
        multiplier = conditions.get('multiplier', 1.0)
        base_points = rule.points
        bonus_points = int(base_points * (multiplier - 1))
        
        return {
            'applicable': True,
            'points': base_points + bonus_points,
            'bonus_points': bonus_points,
            'reason': f'Time-based bonus: {multiplier}x multiplier'
        }
    
    def _process_frequency_rule(self, rule: Rule, customer: Customer, 
                              conditions: Dict, action_data: Dict, location) -> Dict[str, Any]:
        """Process frequency-based rules (visit streaks, daily limits)"""
        frequency_type = conditions.get('frequency_type', 'daily')
        limit = conditions.get('limit', 1)
        streak_bonus = conditions.get('streak_bonus', 0)
        
        # Get time window
        if frequency_type == 'daily':
            window_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        elif frequency_type == 'weekly':
            days_since_monday = timezone.now().weekday()
            window_start = timezone.now() - timedelta(days=days_since_monday)
            window_start = window_start.replace(hour=0, minute=0, second=0, microsecond=0)
        elif frequency_type == 'monthly':
            window_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            return {'applicable': False, 'reason': 'Invalid frequency type'}
        
        # Count transactions in window
        transaction_count = Transaction.objects.filter(
            loyalty_account=customer.loyalty_account,
            rule_applied=rule,
            timestamp__gte=window_start,
            status='completed'
        ).count()
        
        if transaction_count >= limit:
            return {'applicable': False, 'reason': f'{frequency_type.title()} limit reached'}
        
        # Calculate streak bonus
        bonus_points = 0
        if streak_bonus > 0:
            consecutive_days = self._calculate_streak(customer, rule)
            bonus_points = consecutive_days * streak_bonus
        
        return {
            'applicable': True,
            'points': rule.points + bonus_points,
            'bonus_points': bonus_points,
            'streak_days': consecutive_days if streak_bonus > 0 else 0,
            'reason': f'Frequency rule applied with {bonus_points} streak bonus'
        }
    
    def _process_tier_rule(self, rule: Rule, customer: Customer, 
                         conditions: Dict, action_data: Dict, location) -> Dict[str, Any]:
        """Process tier-based rules with tier-specific multipliers"""
        tier_multipliers = conditions.get('tier_multipliers', {})
        current_tier = customer.loyalty_account.tier
        
        if not current_tier:
            tier_name = 'bronze'  # Default tier
        else:
            tier_name = current_tier.name.lower()
        
        multiplier = tier_multipliers.get(tier_name, 1.0)
        base_points = rule.points
        total_points = int(base_points * multiplier)
        bonus_points = total_points - base_points
        
        return {
            'applicable': True,
            'points': total_points,
            'bonus_points': bonus_points,
            'tier': tier_name,
            'multiplier': multiplier,
            'reason': f'Tier-based bonus: {multiplier}x for {tier_name} tier'
        }
    
    def _process_combo_rule(self, rule: Rule, customer: Customer, 
                          conditions: Dict, action_data: Dict, location) -> Dict[str, Any]:
        """Process combo rules (multiple actions within timeframe)"""
        required_actions = conditions.get('required_actions', [])
        timeframe_hours = conditions.get('timeframe_hours', 24)
        combo_bonus = conditions.get('combo_bonus', 0)
        
        cutoff_time = timezone.now() - timedelta(hours=timeframe_hours)
        
        # Check if all required actions have been performed
        completed_actions = []
        for action in required_actions:
            action_type = action.get('type')
            min_count = action.get('min_count', 1)
            
            if action_type == 'checkin':
                count = Transaction.objects.filter(
                    loyalty_account=customer.loyalty_account,
                    transaction_type='earn',
                    description__icontains='check-in',
                    timestamp__gte=cutoff_time
                ).count()
            elif action_type == 'purchase':
                count = Transaction.objects.filter(
                    loyalty_account=customer.loyalty_account,
                    transaction_type='earn',
                    description__icontains='purchase',
                    timestamp__gte=cutoff_time
                ).count()
            else:
                count = 0
            
            if count >= min_count:
                completed_actions.append(action_type)
        
        if len(completed_actions) < len(required_actions):
            return {
                'applicable': True,
                'points': rule.points,
                'bonus_points': 0,
                'combo_progress': f'{len(completed_actions)}/{len(required_actions)}',
                'reason': 'Partial combo progress'
            }
        
        return {
            'applicable': True,
            'points': rule.points + combo_bonus,
            'bonus_points': combo_bonus,
            'combo_completed': True,
            'reason': f'Combo completed! {combo_bonus} bonus points'
        }
    
    def _process_milestone_rule(self, rule: Rule, customer: Customer, 
                              conditions: Dict, action_data: Dict, location) -> Dict[str, Any]:
        """Process milestone-based rules (lifetime points, visit counts)"""
        milestone_type = conditions.get('milestone_type', 'lifetime_points')
        milestones = conditions.get('milestones', [])
        
        if milestone_type == 'lifetime_points':
            current_value = customer.loyalty_account.lifetime_points
        elif milestone_type == 'total_visits':
            current_value = Transaction.objects.filter(
                loyalty_account=customer.loyalty_account,
                transaction_type='earn',
                description__icontains='check-in'
            ).count()
        else:
            return {'applicable': False, 'reason': 'Invalid milestone type'}
        
        # Find applicable milestone
        applicable_milestone = None
        for milestone in sorted(milestones, key=lambda x: x['threshold']):
            if current_value >= milestone['threshold']:
                # Check if this milestone was already awarded
                milestone_awarded = Transaction.objects.filter(
                    loyalty_account=customer.loyalty_account,
                    description__icontains=f"milestone_{milestone['threshold']}",
                    rule_applied=rule
                ).exists()
                
                if not milestone_awarded:
                    applicable_milestone = milestone
        
        if not applicable_milestone:
            return {'applicable': False, 'reason': 'No new milestones reached'}
        
        return {
            'applicable': True,
            'points': applicable_milestone['bonus_points'],
            'bonus_points': applicable_milestone['bonus_points'],
            'milestone_reached': applicable_milestone['threshold'],
            'reason': f'Milestone reached: {applicable_milestone["threshold"]} {milestone_type}'
        }
    
    def _process_seasonal_rule(self, rule: Rule, customer: Customer, 
                             conditions: Dict, action_data: Dict, location) -> Dict[str, Any]:
        """Process seasonal/event-based rules"""
        seasons = conditions.get('seasons', [])
        events = conditions.get('events', [])
        multiplier = conditions.get('multiplier', 1.0)
        
        now = timezone.now()
        current_applicable = False
        active_reason = ""
        
        # Check seasons
        for season in seasons:
            start_date = datetime.strptime(f"{now.year}-{season['start']}", '%Y-%m-%d').date()
            end_date = datetime.strptime(f"{now.year}-{season['end']}", '%Y-%m-%d').date()
            
            if start_date <= now.date() <= end_date:
                current_applicable = True
                active_reason = f"Seasonal bonus: {season['name']}"
                break
        
        # Check events
        if not current_applicable:
            for event in events:
                event_start = datetime.strptime(event['start'], '%Y-%m-%d').date()
                event_end = datetime.strptime(event['end'], '%Y-%m-%d').date()
                
                if event_start <= now.date() <= event_end:
                    current_applicable = True
                    active_reason = f"Event bonus: {event['name']}"
                    break
        
        if not current_applicable:
            return {'applicable': False, 'reason': 'No active seasonal/event bonus'}
        
        base_points = rule.points
        total_points = int(base_points * multiplier)
        bonus_points = total_points - base_points
        
        return {
            'applicable': True,
            'points': total_points,
            'bonus_points': bonus_points,
            'multiplier': multiplier,
            'reason': active_reason
        }
    
    def _process_location_chain_rule(self, rule: Rule, customer: Customer, 
                                   conditions: Dict, action_data: Dict, location) -> Dict[str, Any]:
        """Process location chain rules (visit different locations)"""
        required_locations = conditions.get('required_locations', [])
        timeframe_days = conditions.get('timeframe_days', 7)
        chain_bonus = conditions.get('chain_bonus', 0)
        
        cutoff_time = timezone.now() - timedelta(days=timeframe_days)
        
        # Get unique locations visited in timeframe
        visited_locations = Transaction.objects.filter(
            loyalty_account=customer.loyalty_account,
            transaction_type='earn',
            location__isnull=False,
            timestamp__gte=cutoff_time
        ).values_list('location_id', flat=True).distinct()
        
        visited_count = len(set(visited_locations))
        required_count = len(required_locations) if required_locations else conditions.get('min_locations', 3)
        
        if visited_count < required_count:
            return {
                'applicable': True,
                'points': rule.points,
                'bonus_points': 0,
                'chain_progress': f'{visited_count}/{required_count}',
                'reason': f'Location chain progress: {visited_count}/{required_count}'
            }
        
        return {
            'applicable': True,
            'points': rule.points + chain_bonus,
            'bonus_points': chain_bonus,
            'chain_completed': True,
            'locations_visited': visited_count,
            'reason': f'Location chain completed! {chain_bonus} bonus points'
        }
    
    def _process_basic_rule(self, rule: Rule, customer: Customer, 
                          conditions: Dict, action_data: Dict, location) -> Dict[str, Any]:
        """Process basic rules (fallback)"""
        return {
            'applicable': True,
            'points': rule.points,
            'bonus_points': 0,
            'reason': 'Basic rule applied'
        }
    
    def _calculate_streak(self, customer: Customer, rule: Rule) -> int:
        """Calculate consecutive days streak for a rule"""
        consecutive_days = 0
        current_date = timezone.now().date()
        
        for i in range(30):  # Check last 30 days
            check_date = current_date - timedelta(days=i)
            day_start = timezone.make_aware(datetime.combine(check_date, datetime.min.time()))
            day_end = day_start + timedelta(days=1)
            
            has_transaction = Transaction.objects.filter(
                loyalty_account=customer.loyalty_account,
                rule_applied=rule,
                timestamp__gte=day_start,
                timestamp__lt=day_end,
                status='completed'
            ).exists()
            
            if has_transaction:
                consecutive_days += 1
            else:
                break
        
        return consecutive_days


class RuleTemplateManager:
    """Manager for creating rule templates for common scenarios"""
    
    @staticmethod
    def create_happy_hour_rule(program, start_time="17:00", end_time="19:00", 
                              multiplier=2.0, days=None):
        """Create a happy hour rule template"""
        if days is None:
            days = [0, 1, 2, 3, 4]  # Weekdays
        
        conditions = {
            'type': 'time_based',
            'time_windows': [{
                'start': start_time,
                'end': end_time,
                'days': days
            }],
            'multiplier': multiplier
        }
        
        return Rule.objects.create(
            program=program,
            name=f"Happy Hour {start_time}-{end_time}",
            description=f"Earn {multiplier}x points during happy hour",
            trigger_event="checkin",
            conditions=json.dumps(conditions),
            points=10,  # Base points
            is_active=True
        )
    
    @staticmethod
    def create_streak_rule(program, streak_bonus=5, frequency='daily'):
        """Create a streak-based rule template"""
        conditions = {
            'type': 'frequency_based',
            'frequency_type': frequency,
            'limit': 1,
            'streak_bonus': streak_bonus
        }
        
        return Rule.objects.create(
            program=program,
            name=f"{frequency.title()} Streak Bonus",
            description=f"Earn {streak_bonus} bonus points per consecutive day",
            trigger_event="checkin",
            conditions=json.dumps(conditions),
            points=10,
            is_active=True
        )
    
    @staticmethod
    def create_tier_multiplier_rule(program, tier_multipliers=None):
        """Create a tier-based multiplier rule"""
        if tier_multipliers is None:
            tier_multipliers = {
                'bronze': 1.0,
                'silver': 1.5,
                'gold': 2.0,
                'platinum': 2.5
            }
        
        conditions = {
            'type': 'tier_based',
            'tier_multipliers': tier_multipliers
        }
        
        return Rule.objects.create(
            program=program,
            name="Tier Multiplier Bonus",
            description="Earn bonus points based on your tier level",
            trigger_event="checkin",
            conditions=json.dumps(conditions),
            points=10,
            is_active=True
        )
    
    @staticmethod
    def create_location_chain_rule(program, min_locations=3, timeframe_days=7, chain_bonus=50):
        """Create a location chain rule template"""
        conditions = {
            'type': 'location_chain',
            'min_locations': min_locations,
            'timeframe_days': timeframe_days,
            'chain_bonus': chain_bonus
        }
        
        return Rule.objects.create(
            program=program,
            name=f"Location Explorer ({min_locations} locations)",
            description=f"Visit {min_locations} different locations in {timeframe_days} days for bonus",
            trigger_event="checkin",
            conditions=json.dumps(conditions),
            points=10,
            is_active=True
        )
