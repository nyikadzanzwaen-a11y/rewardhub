"""
Gamification models for badges, challenges, and achievements
"""
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.tenants.models import Tenant
from apps.customers.models import Customer


class Badge(models.Model):
    """Badge definitions for achievements"""
    
    BADGE_TYPES = [
        ('milestone', 'Milestone'),
        ('frequency', 'Frequency'),
        ('streak', 'Streak'),
        ('social', 'Social'),
        ('seasonal', 'Seasonal'),
        ('special', 'Special Event')
    ]
    
    RARITY_LEVELS = [
        ('common', 'Common'),
        ('rare', 'Rare'),
        ('epic', 'Epic'),
        ('legendary', 'Legendary')
    ]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='badges')
    name = models.CharField(max_length=100)
    description = models.TextField()
    badge_type = models.CharField(max_length=20, choices=BADGE_TYPES)
    rarity = models.CharField(max_length=20, choices=RARITY_LEVELS, default='common')
    icon = models.CharField(max_length=50, default='🏆')  # Emoji or icon class
    points_reward = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    # Badge criteria (JSON field for flexibility)
    criteria = models.JSONField(default=dict, help_text="Badge earning criteria")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['tenant', 'name']
        ordering = ['rarity', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.tenant.name})"


class Challenge(models.Model):
    """Time-limited challenges for customers"""
    
    CHALLENGE_TYPES = [
        ('points', 'Points Challenge'),
        ('visits', 'Visit Challenge'),
        ('streak', 'Streak Challenge'),
        ('social', 'Social Challenge'),
        ('spending', 'Spending Challenge')
    ]
    
    DIFFICULTY_LEVELS = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
        ('extreme', 'Extreme')
    ]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='challenges')
    name = models.CharField(max_length=100)
    description = models.TextField()
    challenge_type = models.CharField(max_length=20, choices=CHALLENGE_TYPES)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_LEVELS, default='medium')
    
    # Challenge parameters
    target_value = models.IntegerField(validators=[MinValueValidator(1)])
    points_reward = models.IntegerField(validators=[MinValueValidator(0)])
    badge_reward = models.ForeignKey(Badge, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Time constraints
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    duration_days = models.IntegerField(null=True, blank=True, help_text="Challenge duration in days")
    
    # Challenge criteria and rules
    criteria = models.JSONField(default=dict, help_text="Challenge completion criteria")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.name} ({self.tenant.name})"
    
    @property
    def is_ongoing(self):
        now = timezone.now()
        return self.start_date <= now <= self.end_date and self.is_active


class CustomerBadge(models.Model):
    """Badges earned by customers"""
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE)
    earned_at = models.DateTimeField(auto_now_add=True)
    progress_data = models.JSONField(default=dict, help_text="Progress tracking data")
    
    class Meta:
        unique_together = ['customer', 'badge']
        ordering = ['-earned_at']
    
    def __str__(self):
        return f"{self.customer.email} - {self.badge.name}"


class CustomerChallenge(models.Model):
    """Customer participation in challenges"""
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('expired', 'Expired')
    ]
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='challenges')
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Progress tracking
    current_progress = models.IntegerField(default=0)
    progress_percentage = models.FloatField(default=0.0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Timestamps
    joined_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_progress_update = models.DateTimeField(auto_now=True)
    
    # Progress data
    progress_data = models.JSONField(default=dict, help_text="Detailed progress tracking")
    
    class Meta:
        unique_together = ['customer', 'challenge']
        ordering = ['-joined_at']
    
    def __str__(self):
        return f"{self.customer.email} - {self.challenge.name} ({self.status})"
    
    def update_progress(self, new_progress):
        """Update challenge progress"""
        self.current_progress = new_progress
        self.progress_percentage = min((new_progress / self.challenge.target_value) * 100, 100)
        
        if self.progress_percentage >= 100 and self.status == 'active':
            self.status = 'completed'
            self.completed_at = timezone.now()
        
        self.save()


class Achievement(models.Model):
    """Special achievements and milestones"""
    
    ACHIEVEMENT_TYPES = [
        ('first_time', 'First Time'),
        ('milestone', 'Milestone'),
        ('perfect', 'Perfect Score'),
        ('speed', 'Speed Achievement'),
        ('consistency', 'Consistency'),
        ('social', 'Social Achievement')
    ]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='achievements')
    name = models.CharField(max_length=100)
    description = models.TextField()
    achievement_type = models.CharField(max_length=20, choices=ACHIEVEMENT_TYPES)
    
    # Rewards
    points_reward = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    badge_reward = models.ForeignKey(Badge, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Achievement criteria
    criteria = models.JSONField(default=dict)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['tenant', 'name']
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.tenant.name})"


class CustomerAchievement(models.Model):
    """Achievements earned by customers"""
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='achievements')
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    earned_at = models.DateTimeField(auto_now_add=True)
    context_data = models.JSONField(default=dict, help_text="Context when achievement was earned")
    
    class Meta:
        unique_together = ['customer', 'achievement']
        ordering = ['-earned_at']
    
    def __str__(self):
        return f"{self.customer.email} - {self.achievement.name}"


class Leaderboard(models.Model):
    """Leaderboard configurations"""
    
    LEADERBOARD_TYPES = [
        ('points', 'Points Leaderboard'),
        ('visits', 'Visits Leaderboard'),
        ('streak', 'Streak Leaderboard'),
        ('badges', 'Badges Leaderboard'),
        ('challenges', 'Challenges Leaderboard')
    ]
    
    TIMEFRAMES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
        ('all_time', 'All Time')
    ]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='leaderboards')
    name = models.CharField(max_length=100)
    leaderboard_type = models.CharField(max_length=20, choices=LEADERBOARD_TYPES)
    timeframe = models.CharField(max_length=20, choices=TIMEFRAMES)
    
    # Configuration
    max_entries = models.IntegerField(default=100, validators=[MinValueValidator(1)])
    is_public = models.BooleanField(default=True)
    
    # Rewards for top positions
    rewards_config = models.JSONField(default=dict, help_text="Rewards for top positions")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['tenant', 'name']
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.tenant.name})"
