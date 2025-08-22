from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from user_accounts.models import User


class Task(models.Model):
    """
    Core Task model for individual and shared tasks
    """
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('overdue', 'Overdue'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='tasks',
        help_text="The user who owns this task"
    )
    
    title = models.CharField(
        max_length=200,
        help_text="Task title"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Detailed task description"
    )
    
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='medium',
        help_text="Task priority level"
    )
    
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending',
        help_text="Current task status"
    )
    
    deadline = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Task deadline (optional)"
    )
    
    points_value = models.PositiveIntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Points awarded for completing this task"
    )
    
    is_shared = models.BooleanField(
        default=False,
        help_text="Whether this task is shared with friends"
    )
    
    is_private = models.BooleanField(
        default=False,
        help_text="Whether this task is private (not visible in social feed)"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the task was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the task was last updated"
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the task was completed"
    )
    
    class Meta:
        db_table = 'task_management_task'
        verbose_name = 'Task'
        verbose_name_plural = 'Tasks'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['user', 'priority']),
            models.Index(fields=['deadline']),
            models.Index(fields=['status', 'deadline']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.phone_number}"
    
    def save(self, *args, **kwargs):
        # Auto-calculate points based on priority if not set
        if not self.pk and self.points_value == 10:  # Default value
            self.points_value = self.calculate_default_points()
        
        # Update status to overdue if deadline has passed
        if self.deadline and self.status == 'pending' and timezone.now() > self.deadline:
            self.status = 'overdue'
        
        super().save(*args, **kwargs)
    
    def calculate_default_points(self):
        """Calculate default points based on priority"""
        priority_points = {
            'low': 5,
            'medium': 10,
            'high': 20,
        }
        return priority_points.get(self.priority, 10)
    
    def calculate_completion_points(self):
        """
        Calculate points to award based on task completion timing
        Returns the actual points to award (may be different from points_value)
        """
        if self.status != 'completed':
            return 0
        
        base_points = self.points_value
        
        # Bonus for completing before deadline
        if self.deadline and self.completed_at and self.completed_at <= self.deadline:
            # 50% bonus for early completion
            time_remaining = self.deadline - self.completed_at
            total_time = self.deadline - self.created_at
            
            if total_time.total_seconds() > 0:
                completion_ratio = time_remaining.total_seconds() / total_time.total_seconds()
                if completion_ratio > 0.5:  # Completed in first half of time
                    base_points = int(base_points * 1.5)
                elif completion_ratio > 0.25:  # Completed in first 3/4 of time
                    base_points = int(base_points * 1.25)
        
        # Penalty for overdue completion
        elif self.deadline and self.completed_at and self.completed_at > self.deadline:
            # 25% penalty for late completion
            base_points = int(base_points * 0.75)
        
        return max(1, base_points)  # Minimum 1 point
    
    def mark_completed(self):
        """Mark the task as completed and set completion timestamp"""
        if self.status != 'completed':
            self.status = 'completed'
            self.completed_at = timezone.now()
            self.save(update_fields=['status', 'completed_at'])
            return True
        return False
    
    def is_overdue(self):
        """Check if the task is overdue"""
        if not self.deadline or self.status == 'completed':
            return False
        return timezone.now() > self.deadline
    
    def update_overdue_status(self):
        """Update status to overdue if deadline has passed"""
        if self.is_overdue() and self.status == 'pending':
            self.status = 'overdue'
            self.save(update_fields=['status'])
            return True
        return False
    
    @property
    def days_until_deadline(self):
        """Get number of days until deadline (negative if overdue)"""
        if not self.deadline:
            return None
        
        delta = self.deadline - timezone.now()
        return delta.days
    
    @property
    def completion_percentage(self):
        """Get completion percentage (100 if completed, 0 if not started)"""
        return 100 if self.status == 'completed' else 0


class SharedTask(models.Model):
    """
    Model for tasks shared between friends with competitive features
    """
    task = models.OneToOneField(
        Task,
        on_delete=models.CASCADE,
        related_name='shared_details',
        help_text="The base task that is shared"
    )
    
    participants = models.ManyToManyField(
        User,
        through='TaskParticipation',
        related_name='shared_tasks',
        help_text="Users participating in this shared task"
    )
    
    creator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_shared_tasks',
        help_text="User who created this shared task"
    )
    
    is_competitive = models.BooleanField(
        default=True,
        help_text="Whether this shared task has competitive scoring"
    )
    
    max_participants = models.PositiveIntegerField(
        default=10,
        validators=[MinValueValidator(2), MaxValueValidator(50)],
        help_text="Maximum number of participants allowed"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the shared task was created"
    )
    
    class Meta:
        db_table = 'task_management_shared_task'
        verbose_name = 'Shared Task'
        verbose_name_plural = 'Shared Tasks'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Shared: {self.task.title}"
    
    def get_participant_count(self):
        """Get the number of participants"""
        return self.participants.count()
    
    def can_add_participant(self):
        """Check if more participants can be added"""
        return self.get_participant_count() < self.max_participants
    
    def get_completion_stats(self):
        """Get completion statistics for all participants"""
        participations = self.taskparticipation_set.all()
        total = participations.count()
        completed = participations.filter(status='completed').count()
        
        return {
            'total_participants': total,
            'completed_count': completed,
            'completion_rate': (completed / total * 100) if total > 0 else 0,
            'pending_count': total - completed
        }


class TaskParticipation(models.Model):
    """
    Through model for SharedTask participants with individual completion tracking
    """
    shared_task = models.ForeignKey(
        SharedTask,
        on_delete=models.CASCADE,
        help_text="The shared task"
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        help_text="The participating user"
    )
    
    status = models.CharField(
        max_length=10,
        choices=Task.STATUS_CHOICES,
        default='pending',
        help_text="Participant's completion status"
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this participant completed the task"
    )
    
    points_earned = models.PositiveIntegerField(
        default=0,
        help_text="Points earned by this participant"
    )
    
    joined_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the user joined this shared task"
    )
    
    class Meta:
        db_table = 'task_management_task_participation'
        verbose_name = 'Task Participation'
        verbose_name_plural = 'Task Participations'
        unique_together = ('shared_task', 'user')
        ordering = ['completed_at', '-points_earned']
    
    def __str__(self):
        return f"{self.user.phone_number} - {self.shared_task.task.title}"
    
    def mark_completed(self):
        """Mark this participation as completed"""
        if self.status != 'completed':
            self.status = 'completed'
            self.completed_at = timezone.now()
            
            # Calculate points for competitive tasks
            if self.shared_task.is_competitive:
                self.points_earned = self.calculate_competitive_points()
            else:
                self.points_earned = self.shared_task.task.points_value
            
            self.save(update_fields=['status', 'completed_at', 'points_earned'])
            return True
        return False
    
    def calculate_competitive_points(self):
        """Calculate competitive points based on completion order and timing"""
        base_points = self.shared_task.task.points_value
        
        # Get completion rank (1st, 2nd, 3rd, etc.)
        completed_before = TaskParticipation.objects.filter(
            shared_task=self.shared_task,
            status='completed',
            completed_at__lt=self.completed_at
        ).count()
        
        rank = completed_before + 1
        
        # Bonus points for early completion
        if rank == 1:
            return int(base_points * 2.0)  # 100% bonus for 1st place
        elif rank == 2:
            return int(base_points * 1.5)  # 50% bonus for 2nd place
        elif rank == 3:
            return int(base_points * 1.25)  # 25% bonus for 3rd place
        else:
            return base_points  # Standard points for others
    
    @property
    def completion_rank(self):
        """Get the completion rank among all participants"""
        if self.status != 'completed':
            return None
        
        return TaskParticipation.objects.filter(
            shared_task=self.shared_task,
            status='completed',
            completed_at__lt=self.completed_at
        ).count() + 1


class Achievement(models.Model):
    """
    Model for storing achievement definitions and metadata
    """
    ACHIEVEMENT_CATEGORIES = [
        ('competitive', 'Competitive'),
        ('consistency', 'Consistency'),
        ('speed', 'Speed'),
        ('participation', 'Participation'),
        ('points', 'Points'),
        ('social', 'Social'),
        ('milestone', 'Milestone'),
    ]
    
    achievement_id = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique identifier for the achievement"
    )
    
    name = models.CharField(
        max_length=100,
        help_text="Achievement name"
    )
    
    description = models.TextField(
        help_text="Achievement description"
    )
    
    icon = models.CharField(
        max_length=50,
        help_text="Icon identifier for the achievement"
    )
    
    category = models.CharField(
        max_length=20,
        choices=ACHIEVEMENT_CATEGORIES,
        default='milestone',
        help_text="Achievement category"
    )
    
    points_reward = models.PositiveIntegerField(
        default=0,
        help_text="Points awarded when achievement is unlocked"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this achievement is currently active"
    )
    
    rarity = models.CharField(
        max_length=20,
        choices=[
            ('common', 'Common'),
            ('uncommon', 'Uncommon'),
            ('rare', 'Rare'),
            ('epic', 'Epic'),
            ('legendary', 'Legendary'),
        ],
        default='common',
        help_text="Achievement rarity level"
    )
    
    # Metadata for achievement requirements
    requirements_data = models.JSONField(
        default=dict,
        help_text="JSON data containing achievement requirements"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the achievement was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the achievement was last updated"
    )
    
    class Meta:
        db_table = 'task_management_achievement'
        verbose_name = 'Achievement'
        verbose_name_plural = 'Achievements'
        ordering = ['category', 'name']
        indexes = [
            models.Index(fields=['achievement_id']),
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['rarity']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"
    
    def to_dict(self):
        """Convert achievement to dictionary representation"""
        return {
            'id': self.achievement_id,
            'name': self.name,
            'description': self.description,
            'icon': self.icon,
            'category': self.category,
            'points_reward': self.points_reward,
            'rarity': self.rarity,
            'requirements_data': self.requirements_data,
        }


class UserAchievement(models.Model):
    """
    Model for tracking user achievement unlocks
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='achievements',
        help_text="User who unlocked the achievement"
    )
    
    achievement = models.ForeignKey(
        Achievement,
        on_delete=models.CASCADE,
        related_name='user_unlocks',
        help_text="Achievement that was unlocked"
    )
    
    earned_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the achievement was unlocked"
    )
    
    points_awarded = models.PositiveIntegerField(
        default=0,
        help_text="Points awarded when this achievement was unlocked"
    )
    
    # Progress tracking for achievements with incremental progress
    progress_data = models.JSONField(
        default=dict,
        help_text="JSON data for tracking achievement progress"
    )
    
    # Notification tracking
    notification_sent = models.BooleanField(
        default=False,
        help_text="Whether notification was sent for this achievement"
    )
    
    is_featured = models.BooleanField(
        default=False,
        help_text="Whether this achievement should be featured in user profile"
    )
    
    class Meta:
        db_table = 'task_management_user_achievement'
        verbose_name = 'User Achievement'
        verbose_name_plural = 'User Achievements'
        unique_together = ('user', 'achievement')
        ordering = ['-earned_at']
        indexes = [
            models.Index(fields=['user', 'earned_at']),
            models.Index(fields=['achievement', 'earned_at']),
            models.Index(fields=['is_featured']),
        ]
    
    def __str__(self):
        return f"{self.user.phone_number} - {self.achievement.name}"
    
    def to_dict(self):
        """Convert user achievement to dictionary representation"""
        return {
            'achievement': self.achievement.to_dict(),
            'earned_at': self.earned_at.isoformat(),
            'points_awarded': self.points_awarded,
            'progress_data': self.progress_data,
            'is_featured': self.is_featured,
        }


class AchievementProgress(models.Model):
    """
    Model for tracking user progress towards achievements
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='achievement_progress',
        help_text="User whose progress is being tracked"
    )
    
    achievement = models.ForeignKey(
        Achievement,
        on_delete=models.CASCADE,
        related_name='user_progress',
        help_text="Achievement being tracked"
    )
    
    current_progress = models.PositiveIntegerField(
        default=0,
        help_text="Current progress value"
    )
    
    target_progress = models.PositiveIntegerField(
        default=1,
        help_text="Target progress value for completion"
    )
    
    progress_data = models.JSONField(
        default=dict,
        help_text="Additional progress tracking data"
    )
    
    last_updated = models.DateTimeField(
        auto_now=True,
        help_text="When progress was last updated"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When progress tracking started"
    )
    
    class Meta:
        db_table = 'task_management_achievement_progress'
        verbose_name = 'Achievement Progress'
        verbose_name_plural = 'Achievement Progress'
        unique_together = ('user', 'achievement')
        ordering = ['-last_updated']
        indexes = [
            models.Index(fields=['user', 'last_updated']),
            models.Index(fields=['achievement']),
        ]
    
    def __str__(self):
        return f"{self.user.phone_number} - {self.achievement.name}: {self.current_progress}/{self.target_progress}"
    
    @property
    def completion_percentage(self):
        """Get completion percentage (0-100)"""
        if self.target_progress == 0:
            return 100
        return min(100, (self.current_progress / self.target_progress) * 100)
    
    @property
    def is_completed(self):
        """Check if achievement is completed"""
        return self.current_progress >= self.target_progress
    
    def update_progress(self, new_progress, progress_data=None):
        """Update progress and check for completion"""
        self.current_progress = new_progress
        if progress_data:
            self.progress_data.update(progress_data)
        self.save()
        
        # Check if achievement should be unlocked
        if self.is_completed:
            user_achievement, created = UserAchievement.objects.get_or_create(
                user=self.user,
                achievement=self.achievement,
                defaults={
                    'points_awarded': self.achievement.points_reward,
                    'progress_data': self.progress_data,
                }
            )
            
            if created:
                # Award points to user
                self.user.total_points += self.achievement.points_reward
                self.user.save(update_fields=['total_points'])
                
                return user_achievement
        
        return None