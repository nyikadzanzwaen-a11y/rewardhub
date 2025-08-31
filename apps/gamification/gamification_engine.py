"""
Gamification engine for managing badges, challenges, and achievements
"""
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from django.utils import timezone
from django.db.models import Count, Sum, Q, F
from django.db import transaction

from apps.customers.models import Customer
from apps.loyalty.models import Transaction
from apps.locations.models import CheckIn
from .models import (
    Badge, Challenge, Achievement, CustomerBadge, 
    CustomerChallenge, CustomerAchievement, Leaderboard
)


class BadgeEngine:
    """Engine for managing badge awards and tracking"""
    
    def __init__(self):
        self.badge_checkers = {
            'milestone': self._check_milestone_badges,
            'frequency': self._check_frequency_badges,
            'streak': self._check_streak_badges,
            'social': self._check_social_badges,
            'seasonal': self._check_seasonal_badges,
            'special': self._check_special_badges
        }
    
    def check_and_award_badges(self, customer: Customer, event_type: str = None) -> List[Badge]:
        """Check and award applicable badges to customer"""
        
        awarded_badges = []
        tenant_badges = Badge.objects.filter(tenant=customer.tenant, is_active=True)
        
        for badge in tenant_badges:
            # Skip if customer already has this badge
            if CustomerBadge.objects.filter(customer=customer, badge=badge).exists():
                continue
            
            # Check if badge criteria is met
            if self._check_badge_criteria(customer, badge, event_type):
                awarded_badge = self._award_badge(customer, badge)
                if awarded_badge:
                    awarded_badges.append(badge)
        
        return awarded_badges
    
    def _check_badge_criteria(self, customer: Customer, badge: Badge, event_type: str = None) -> bool:
        """Check if customer meets badge criteria"""
        
        checker = self.badge_checkers.get(badge.badge_type)
        if not checker:
            return False
        
        return checker(customer, badge, event_type)
    
    def _check_milestone_badges(self, customer: Customer, badge: Badge, event_type: str = None) -> bool:
        """Check milestone-based badges"""
        
        criteria = badge.criteria
        milestone_type = criteria.get('type', 'points')
        target_value = criteria.get('target', 0)
        
        if milestone_type == 'points':
            current_value = customer.loyalty_account.lifetime_points
        elif milestone_type == 'visits':
            current_value = CheckIn.objects.filter(customer=customer).count()
        elif milestone_type == 'transactions':
            current_value = Transaction.objects.filter(loyalty_account=customer.loyalty_account).count()
        else:
            return False
        
        return current_value >= target_value
    
    def _check_frequency_badges(self, customer: Customer, badge: Badge, event_type: str = None) -> bool:
        """Check frequency-based badges"""
        
        criteria = badge.criteria
        action_type = criteria.get('action', 'visit')
        frequency = criteria.get('frequency', 1)
        timeframe_days = criteria.get('timeframe_days', 30)
        
        start_date = timezone.now() - timedelta(days=timeframe_days)
        
        if action_type == 'visit':
            count = CheckIn.objects.filter(
                customer=customer,
                timestamp__gte=start_date
            ).count()
        elif action_type == 'transaction':
            count = Transaction.objects.filter(
                loyalty_account=customer.loyalty_account,
                timestamp__gte=start_date
            ).count()
        else:
            return False
        
        return count >= frequency
    
    def _check_streak_badges(self, customer: Customer, badge: Badge, event_type: str = None) -> bool:
        """Check streak-based badges"""
        
        criteria = badge.criteria
        streak_type = criteria.get('type', 'visit')
        target_streak = criteria.get('target', 7)
        
        if streak_type == 'visit':
            return self._calculate_visit_streak(customer) >= target_streak
        
        return False
    
    def _check_social_badges(self, customer: Customer, badge: Badge, event_type: str = None) -> bool:
        """Check social interaction badges"""
        
        criteria = badge.criteria
        social_type = criteria.get('type', 'referral')
        target_count = criteria.get('target', 1)
        
        # Placeholder for social features
        # In a real implementation, you'd check referrals, reviews, shares, etc.
        return False
    
    def _check_seasonal_badges(self, customer: Customer, badge: Badge, event_type: str = None) -> bool:
        """Check seasonal/time-based badges"""
        
        criteria = badge.criteria
        season = criteria.get('season')
        required_actions = criteria.get('required_actions', 1)
        
        # Check if we're in the right season
        current_month = timezone.now().month
        
        seasonal_months = {
            'spring': [3, 4, 5],
            'summer': [6, 7, 8],
            'fall': [9, 10, 11],
            'winter': [12, 1, 2]
        }
        
        if season and current_month not in seasonal_months.get(season, []):
            return False
        
        # Check actions in current season
        season_start = timezone.now().replace(month=seasonal_months[season][0], day=1)
        actions_count = Transaction.objects.filter(
            loyalty_account=customer.loyalty_account,
            timestamp__gte=season_start
        ).count()
        
        return actions_count >= required_actions
    
    def _check_special_badges(self, customer: Customer, badge: Badge, event_type: str = None) -> bool:
        """Check special event badges"""
        
        criteria = badge.criteria
        event_name = criteria.get('event')
        
        # Check if special event is active
        # This would integrate with your events system
        return False
    
    def _calculate_visit_streak(self, customer: Customer) -> int:
        """Calculate current visit streak for customer"""
        
        checkins = CheckIn.objects.filter(customer=customer).order_by('-timestamp')
        
        if not checkins.exists():
            return 0
        
        streak = 0
        current_date = timezone.now().date()
        
        for checkin in checkins:
            checkin_date = checkin.timestamp.date()
            
            if checkin_date == current_date or checkin_date == current_date - timedelta(days=streak):
                streak += 1
                current_date = checkin_date
            else:
                break
        
        return streak
    
    def _award_badge(self, customer: Customer, badge: Badge) -> Optional[CustomerBadge]:
        """Award badge to customer"""
        
        try:
            with transaction.atomic():
                customer_badge = CustomerBadge.objects.create(
                    customer=customer,
                    badge=badge
                )
                
                # Award points if specified
                if badge.points_reward > 0:
                    Transaction.objects.create(
                        loyalty_account=customer.loyalty_account,
                        transaction_type='earn',
                        points=badge.points_reward,
                        description=f'Badge earned: {badge.name}',
                        metadata={'badge_id': badge.id, 'badge_name': badge.name}
                    )
                    
                    # Update points balance
                    customer.loyalty_account.points_balance = F('points_balance') + badge.points_reward
                    customer.loyalty_account.lifetime_points = F('lifetime_points') + badge.points_reward
                    customer.loyalty_account.save()
                
                return customer_badge
                
        except Exception as e:
            return None


class ChallengeEngine:
    """Engine for managing challenges and progress tracking"""
    
    def create_challenge_participation(self, customer: Customer, challenge: Challenge) -> Optional[CustomerChallenge]:
        """Create challenge participation for customer"""
        
        if not challenge.is_ongoing:
            return None
        
        # Check if customer already participating
        if CustomerChallenge.objects.filter(customer=customer, challenge=challenge).exists():
            return None
        
        return CustomerChallenge.objects.create(
            customer=customer,
            challenge=challenge,
            status='active'
        )
    
    def update_challenge_progress(self, customer: Customer, event_type: str, event_data: Dict = None):
        """Update progress for all active challenges"""
        
        active_challenges = CustomerChallenge.objects.filter(
            customer=customer,
            status='active',
            challenge__is_active=True,
            challenge__end_date__gte=timezone.now()
        )
        
        for customer_challenge in active_challenges:
            self._update_single_challenge_progress(customer_challenge, event_type, event_data)
    
    def _update_single_challenge_progress(self, customer_challenge: CustomerChallenge, 
                                        event_type: str, event_data: Dict = None):
        """Update progress for a single challenge"""
        
        challenge = customer_challenge.challenge
        customer = customer_challenge.customer
        
        # Calculate new progress based on challenge type
        new_progress = self._calculate_challenge_progress(customer, challenge, event_type)
        
        if new_progress > customer_challenge.current_progress:
            customer_challenge.update_progress(new_progress)
            
            # Check if challenge is completed
            if customer_challenge.status == 'completed':
                self._complete_challenge(customer_challenge)
    
    def _calculate_challenge_progress(self, customer: Customer, challenge: Challenge, event_type: str) -> int:
        """Calculate current progress for challenge"""
        
        challenge_type = challenge.challenge_type
        criteria = challenge.criteria
        
        if challenge_type == 'points':
            # Points earned during challenge period
            return Transaction.objects.filter(
                loyalty_account=customer.loyalty_account,
                transaction_type='earn',
                timestamp__gte=challenge.start_date,
                timestamp__lte=challenge.end_date
            ).aggregate(total=Sum('points'))['total'] or 0
        
        elif challenge_type == 'visits':
            # Visits during challenge period
            return CheckIn.objects.filter(
                customer=customer,
                timestamp__gte=challenge.start_date,
                timestamp__lte=challenge.end_date
            ).count()
        
        elif challenge_type == 'streak':
            # Current streak (simplified)
            badge_engine = BadgeEngine()
            return badge_engine._calculate_visit_streak(customer)
        
        elif challenge_type == 'spending':
            # Total spending during challenge period
            return Transaction.objects.filter(
                loyalty_account=customer.loyalty_account,
                transaction_type='earn',
                timestamp__gte=challenge.start_date,
                timestamp__lte=challenge.end_date
            ).aggregate(total=Sum('points'))['total'] or 0
        
        return 0
    
    def _complete_challenge(self, customer_challenge: CustomerChallenge):
        """Handle challenge completion"""
        
        challenge = customer_challenge.challenge
        customer = customer_challenge.customer
        
        try:
            with transaction.atomic():
                # Award points
                if challenge.points_reward > 0:
                    Transaction.objects.create(
                        loyalty_account=customer.loyalty_account,
                        transaction_type='earn',
                        points=challenge.points_reward,
                        description=f'Challenge completed: {challenge.name}',
                        metadata={'challenge_id': challenge.id, 'challenge_name': challenge.name}
                    )
                    
                    # Update points balance
                    customer.loyalty_account.points_balance = F('points_balance') + challenge.points_reward
                    customer.loyalty_account.lifetime_points = F('lifetime_points') + challenge.points_reward
                    customer.loyalty_account.save()
                
                # Award badge if specified
                if challenge.badge_reward:
                    CustomerBadge.objects.get_or_create(
                        customer=customer,
                        badge=challenge.badge_reward
                    )
        
        except Exception as e:
            pass


class AchievementEngine:
    """Engine for managing achievements"""
    
    def check_and_award_achievements(self, customer: Customer, event_type: str = None) -> List[Achievement]:
        """Check and award applicable achievements"""
        
        awarded_achievements = []
        tenant_achievements = Achievement.objects.filter(tenant=customer.tenant, is_active=True)
        
        for achievement in tenant_achievements:
            # Skip if customer already has this achievement
            if CustomerAchievement.objects.filter(customer=customer, achievement=achievement).exists():
                continue
            
            # Check if achievement criteria is met
            if self._check_achievement_criteria(customer, achievement, event_type):
                awarded_achievement = self._award_achievement(customer, achievement)
                if awarded_achievement:
                    awarded_achievements.append(achievement)
        
        return awarded_achievements
    
    def _check_achievement_criteria(self, customer: Customer, achievement: Achievement, event_type: str = None) -> bool:
        """Check if customer meets achievement criteria"""
        
        criteria = achievement.criteria
        achievement_type = achievement.achievement_type
        
        if achievement_type == 'first_time':
            return self._check_first_time_achievement(customer, criteria)
        elif achievement_type == 'milestone':
            return self._check_milestone_achievement(customer, criteria)
        elif achievement_type == 'perfect':
            return self._check_perfect_achievement(customer, criteria)
        elif achievement_type == 'speed':
            return self._check_speed_achievement(customer, criteria)
        elif achievement_type == 'consistency':
            return self._check_consistency_achievement(customer, criteria)
        
        return False
    
    def _check_first_time_achievement(self, customer: Customer, criteria: Dict) -> bool:
        """Check first-time achievements"""
        
        action_type = criteria.get('action', 'visit')
        
        if action_type == 'visit':
            return CheckIn.objects.filter(customer=customer).count() == 1
        elif action_type == 'redemption':
            return Transaction.objects.filter(
                loyalty_account=customer.loyalty_account,
                transaction_type='redeem'
            ).count() == 1
        
        return False
    
    def _check_milestone_achievement(self, customer: Customer, criteria: Dict) -> bool:
        """Check milestone achievements"""
        
        milestone_type = criteria.get('type', 'points')
        target_value = criteria.get('target', 0)
        
        if milestone_type == 'points':
            return customer.loyalty_account.lifetime_points >= target_value
        elif milestone_type == 'badges':
            return CustomerBadge.objects.filter(customer=customer).count() >= target_value
        
        return False
    
    def _check_perfect_achievement(self, customer: Customer, criteria: Dict) -> bool:
        """Check perfect score achievements"""
        
        # Example: Perfect attendance for a month
        perfect_type = criteria.get('type', 'attendance')
        timeframe_days = criteria.get('timeframe_days', 30)
        
        if perfect_type == 'attendance':
            start_date = timezone.now() - timedelta(days=timeframe_days)
            expected_days = timeframe_days
            actual_days = CheckIn.objects.filter(
                customer=customer,
                timestamp__gte=start_date
            ).values('timestamp__date').distinct().count()
            
            return actual_days >= expected_days
        
        return False
    
    def _check_speed_achievement(self, customer: Customer, criteria: Dict) -> bool:
        """Check speed-based achievements"""
        
        # Example: Reach milestone in record time
        milestone_points = criteria.get('milestone_points', 1000)
        max_days = criteria.get('max_days', 30)
        
        first_transaction = Transaction.objects.filter(
            loyalty_account=customer.loyalty_account
        ).order_by('timestamp').first()
        
        if not first_transaction:
            return False
        
        days_to_milestone = (timezone.now() - first_transaction.timestamp).days
        current_points = customer.loyalty_account.lifetime_points
        
        return current_points >= milestone_points and days_to_milestone <= max_days
    
    def _check_consistency_achievement(self, customer: Customer, criteria: Dict) -> bool:
        """Check consistency achievements"""
        
        # Example: Visit every week for X weeks
        required_weeks = criteria.get('weeks', 4)
        
        weeks_with_visits = 0
        current_date = timezone.now().date()
        
        for week in range(required_weeks):
            week_start = current_date - timedelta(days=current_date.weekday() + (week * 7))
            week_end = week_start + timedelta(days=6)
            
            if CheckIn.objects.filter(
                customer=customer,
                timestamp__date__gte=week_start,
                timestamp__date__lte=week_end
            ).exists():
                weeks_with_visits += 1
        
        return weeks_with_visits >= required_weeks
    
    def _award_achievement(self, customer: Customer, achievement: Achievement) -> Optional[CustomerAchievement]:
        """Award achievement to customer"""
        
        try:
            with transaction.atomic():
                customer_achievement = CustomerAchievement.objects.create(
                    customer=customer,
                    achievement=achievement,
                    context_data={'awarded_at': timezone.now().isoformat()}
                )
                
                # Award points if specified
                if achievement.points_reward > 0:
                    Transaction.objects.create(
                        loyalty_account=customer.loyalty_account,
                        transaction_type='earn',
                        points=achievement.points_reward,
                        description=f'Achievement unlocked: {achievement.name}',
                        metadata={'achievement_id': achievement.id, 'achievement_name': achievement.name}
                    )
                    
                    # Update points balance
                    customer.loyalty_account.points_balance = F('points_balance') + achievement.points_reward
                    customer.loyalty_account.lifetime_points = F('lifetime_points') + achievement.points_reward
                    customer.loyalty_account.save()
                
                # Award badge if specified
                if achievement.badge_reward:
                    CustomerBadge.objects.get_or_create(
                        customer=customer,
                        badge=achievement.badge_reward
                    )
                
                return customer_achievement
                
        except Exception as e:
            return None


class LeaderboardEngine:
    """Engine for managing leaderboards"""
    
    def generate_leaderboard(self, leaderboard: Leaderboard) -> List[Dict]:
        """Generate leaderboard data"""
        
        tenant = leaderboard.tenant
        leaderboard_type = leaderboard.leaderboard_type
        timeframe = leaderboard.timeframe
        max_entries = leaderboard.max_entries
        
        # Calculate timeframe dates
        end_date = timezone.now()
        start_date = self._get_timeframe_start_date(timeframe, end_date)
        
        # Get leaderboard data based on type
        if leaderboard_type == 'points':
            return self._generate_points_leaderboard(tenant, start_date, end_date, max_entries)
        elif leaderboard_type == 'visits':
            return self._generate_visits_leaderboard(tenant, start_date, end_date, max_entries)
        elif leaderboard_type == 'badges':
            return self._generate_badges_leaderboard(tenant, start_date, end_date, max_entries)
        elif leaderboard_type == 'challenges':
            return self._generate_challenges_leaderboard(tenant, start_date, end_date, max_entries)
        
        return []
    
    def _get_timeframe_start_date(self, timeframe: str, end_date: datetime) -> datetime:
        """Calculate start date for timeframe"""
        
        if timeframe == 'daily':
            return end_date.replace(hour=0, minute=0, second=0, microsecond=0)
        elif timeframe == 'weekly':
            days_since_monday = end_date.weekday()
            return end_date - timedelta(days=days_since_monday)
        elif timeframe == 'monthly':
            return end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif timeframe == 'quarterly':
            quarter_start_month = ((end_date.month - 1) // 3) * 3 + 1
            return end_date.replace(month=quarter_start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        elif timeframe == 'yearly':
            return end_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:  # all_time
            return datetime.min.replace(tzinfo=timezone.get_current_timezone())
    
    def _generate_points_leaderboard(self, tenant, start_date, end_date, max_entries) -> List[Dict]:
        """Generate points-based leaderboard"""
        
        customers = Customer.objects.filter(tenant=tenant).annotate(
            period_points=Sum(
                'loyalty_account__transactions__points',
                filter=Q(
                    loyalty_account__transactions__timestamp__gte=start_date,
                    loyalty_account__transactions__timestamp__lte=end_date,
                    loyalty_account__transactions__transaction_type='earn'
                )
            )
        ).order_by('-period_points')[:max_entries]
        
        leaderboard = []
        for rank, customer in enumerate(customers, 1):
            leaderboard.append({
                'rank': rank,
                'customer_id': customer.id,
                'customer_name': f"{customer.first_name} {customer.last_name}".strip() or customer.email,
                'score': customer.period_points or 0,
                'score_type': 'points'
            })
        
        return leaderboard
    
    def _generate_visits_leaderboard(self, tenant, start_date, end_date, max_entries) -> List[Dict]:
        """Generate visits-based leaderboard"""
        
        customers = Customer.objects.filter(tenant=tenant).annotate(
            period_visits=Count(
                'checkins',
                filter=Q(
                    checkins__timestamp__gte=start_date,
                    checkins__timestamp__lte=end_date
                )
            )
        ).order_by('-period_visits')[:max_entries]
        
        leaderboard = []
        for rank, customer in enumerate(customers, 1):
            leaderboard.append({
                'rank': rank,
                'customer_id': customer.id,
                'customer_name': f"{customer.first_name} {customer.last_name}".strip() or customer.email,
                'score': customer.period_visits,
                'score_type': 'visits'
            })
        
        return leaderboard
    
    def _generate_badges_leaderboard(self, tenant, start_date, end_date, max_entries) -> List[Dict]:
        """Generate badges-based leaderboard"""
        
        customers = Customer.objects.filter(tenant=tenant).annotate(
            period_badges=Count(
                'badges',
                filter=Q(
                    badges__earned_at__gte=start_date,
                    badges__earned_at__lte=end_date
                )
            )
        ).order_by('-period_badges')[:max_entries]
        
        leaderboard = []
        for rank, customer in enumerate(customers, 1):
            leaderboard.append({
                'rank': rank,
                'customer_id': customer.id,
                'customer_name': f"{customer.first_name} {customer.last_name}".strip() or customer.email,
                'score': customer.period_badges,
                'score_type': 'badges'
            })
        
        return leaderboard
    
    def _generate_challenges_leaderboard(self, tenant, start_date, end_date, max_entries) -> List[Dict]:
        """Generate challenges-based leaderboard"""
        
        customers = Customer.objects.filter(tenant=tenant).annotate(
            completed_challenges=Count(
                'challenges',
                filter=Q(
                    challenges__status='completed',
                    challenges__completed_at__gte=start_date,
                    challenges__completed_at__lte=end_date
                )
            )
        ).order_by('-completed_challenges')[:max_entries]
        
        leaderboard = []
        for rank, customer in enumerate(customers, 1):
            leaderboard.append({
                'rank': rank,
                'customer_id': customer.id,
                'customer_name': f"{customer.first_name} {customer.last_name}".strip() or customer.email,
                'score': customer.completed_challenges,
                'score_type': 'challenges'
            })
        
        return leaderboard


class GamificationManager:
    """Main gamification manager that coordinates all engines"""
    
    def __init__(self):
        self.badge_engine = BadgeEngine()
        self.challenge_engine = ChallengeEngine()
        self.achievement_engine = AchievementEngine()
        self.leaderboard_engine = LeaderboardEngine()
    
    def process_customer_event(self, customer: Customer, event_type: str, event_data: Dict = None):
        """Process customer event and update gamification elements"""
        
        # Update challenge progress
        self.challenge_engine.update_challenge_progress(customer, event_type, event_data)
        
        # Check and award badges
        awarded_badges = self.badge_engine.check_and_award_badges(customer, event_type)
        
        # Check and award achievements
        awarded_achievements = self.achievement_engine.check_and_award_achievements(customer, event_type)
        
        return {
            'badges_awarded': len(awarded_badges),
            'achievements_awarded': len(awarded_achievements),
            'badges': [badge.name for badge in awarded_badges],
            'achievements': [achievement.name for achievement in awarded_achievements]
        }
    
    def get_customer_gamification_summary(self, customer: Customer) -> Dict[str, Any]:
        """Get comprehensive gamification summary for customer"""
        
        # Get badges
        customer_badges = CustomerBadge.objects.filter(customer=customer).select_related('badge')
        
        # Get active challenges
        active_challenges = CustomerChallenge.objects.filter(
            customer=customer,
            status='active'
        ).select_related('challenge')
        
        # Get achievements
        customer_achievements = CustomerAchievement.objects.filter(customer=customer).select_related('achievement')
        
        # Calculate streaks
        visit_streak = self.badge_engine._calculate_visit_streak(customer)
        
        return {
            'badges': {
                'total': customer_badges.count(),
                'recent': [
                    {
                        'name': cb.badge.name,
                        'description': cb.badge.description,
                        'icon': cb.badge.icon,
                        'rarity': cb.badge.rarity,
                        'earned_at': cb.earned_at.isoformat()
                    }
                    for cb in customer_badges.order_by('-earned_at')[:5]
                ]
            },
            'challenges': {
                'active': len(active_challenges),
                'details': [
                    {
                        'name': cc.challenge.name,
                        'description': cc.challenge.description,
                        'progress': cc.progress_percentage,
                        'target': cc.challenge.target_value,
                        'current': cc.current_progress,
                        'end_date': cc.challenge.end_date.isoformat()
                    }
                    for cc in active_challenges
                ]
            },
            'achievements': {
                'total': customer_achievements.count(),
                'recent': [
                    {
                        'name': ca.achievement.name,
                        'description': ca.achievement.description,
                        'earned_at': ca.earned_at.isoformat()
                    }
                    for ca in customer_achievements.order_by('-earned_at')[:5]
                ]
            },
            'streaks': {
                'visit_streak': visit_streak
            }
        }
