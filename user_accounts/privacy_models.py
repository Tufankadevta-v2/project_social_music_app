from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings


class PrivacySettings(models.Model):
    """
    Model for storing user privacy preferences and settings
    """
    VISIBILITY_CHOICES = [
        ('public', 'Public'),
        ('friends', 'Friends Only'),
        ('private', 'Private'),
    ]
    
    ACTIVITY_VISIBILITY_CHOICES = [
        ('all', 'All Activities'),
        ('achievements_only', 'Achievements Only'),
        ('tasks_only', 'Tasks Only'),
        ('none', 'None'),
    ]
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='privacy_settings',
        help_text="User these privacy settings belong to"
    )
    
    # Profile visibility settings
    profile_visibility = models.CharField(
        max_length=20,
        choices=VISIBILITY_CHOICES,
        default='friends',
        help_text="Who can view user's profile"
    )
    
    # Task visibility settings
    task_visibility = models.CharField(
        max_length=20,
        choices=VISIBILITY_CHOICES,
        default='friends',
        help_text="Who can see user's tasks"
    )
    
    task_completion_visibility = models.CharField(
        max_length=20,
        choices=VISIBILITY_CHOICES,
        default='friends',
        help_text="Who can see when user completes tasks"
    )
    
    # Achievement visibility settings
    achievement_visibility = models.CharField(
        max_length=20,
        choices=VISIBILITY_CHOICES,
        default='friends',
        help_text="Who can see user's achievements"
    )
    
    # Activity feed settings
    activity_feed_visibility = models.CharField(
        max_length=20,
        choices=ACTIVITY_VISIBILITY_CHOICES,
        default='all',
        help_text="What activities to show in feed"
    )
    
    show_in_leaderboards = models.BooleanField(
        default=True,
        help_text="Whether to appear in friend leaderboards"
    )
    
    # Social interaction settings
    allow_friend_requests = models.BooleanField(
        default=True,
        help_text="Whether to accept friend requests"
    )
    
    allow_shared_task_invites = models.BooleanField(
        default=True,
        help_text="Whether to receive shared task invitations"
    )
    
    # Location and contact settings
    share_location = models.BooleanField(
        default=False,
        help_text="Whether to share location for nearby friend suggestions"
    )
    
    allow_contact_sync = models.BooleanField(
        default=True,
        help_text="Whether to allow contact syncing for friend discovery"
    )
    
    # Notification privacy settings
    show_online_status = models.BooleanField(
        default=True,
        help_text="Whether to show online/offline status to friends"
    )
    
    show_last_seen = models.BooleanField(
        default=True,
        help_text="Whether to show last seen timestamp to friends"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_accounts_privacy_settings'
        verbose_name = 'Privacy Settings'
        verbose_name_plural = 'Privacy Settings'
    
    def __str__(self):
        return f"Privacy Settings for {self.user.phone_number}"
    
    @classmethod
    def get_or_create_for_user(cls, user):
        """Get or create privacy settings for a user with default values"""
        settings, created = cls.objects.get_or_create(
            user=user,
            defaults={
                'profile_visibility': 'friends',
                'task_visibility': 'friends',
                'task_completion_visibility': 'friends',
                'achievement_visibility': 'friends',
                'activity_feed_visibility': 'all',
                'show_in_leaderboards': True,
                'allow_friend_requests': True,
                'allow_shared_task_invites': True,
                'share_location': False,
                'allow_contact_sync': True,
                'show_online_status': True,
                'show_last_seen': True,
            }
        )
        return settings
    
    def can_view_profile(self, requesting_user):
        """Check if requesting user can view this user's profile"""
        if self.user == requesting_user:
            return True
        
        if self.profile_visibility == 'public':
            return True
        elif self.profile_visibility == 'friends':
            from friendships.models import Friendship
            return Friendship.are_friends(requesting_user, self.user)
        else:  # private
            return False
    
    def can_view_tasks(self, requesting_user):
        """Check if requesting user can view this user's tasks"""
        if self.user == requesting_user:
            return True
        
        if self.task_visibility == 'public':
            return True
        elif self.task_visibility == 'friends':
            from friendships.models import Friendship
            return Friendship.are_friends(requesting_user, self.user)
        else:  # private
            return False
    
    def can_view_task_completions(self, requesting_user):
        """Check if requesting user can see this user's task completions"""
        if self.user == requesting_user:
            return True
        
        if self.task_completion_visibility == 'public':
            return True
        elif self.task_completion_visibility == 'friends':
            from friendships.models import Friendship
            return Friendship.are_friends(requesting_user, self.user)
        else:  # private
            return False
    
    def can_view_achievements(self, requesting_user):
        """Check if requesting user can view this user's achievements"""
        if self.user == requesting_user:
            return True
        
        if self.achievement_visibility == 'public':
            return True
        elif self.achievement_visibility == 'friends':
            from friendships.models import Friendship
            return Friendship.are_friends(requesting_user, self.user)
        else:  # private
            return False
    
    def should_show_in_activity_feed(self, activity_type):
        """Check if an activity type should be shown based on privacy settings"""
        if self.activity_feed_visibility == 'none':
            return False
        elif self.activity_feed_visibility == 'all':
            return True
        elif self.activity_feed_visibility == 'achievements_only':
            return activity_type in ['achievement_earned', 'milestone_reached']
        elif self.activity_feed_visibility == 'tasks_only':
            return activity_type in ['task_completed', 'shared_task_completed']
        
        return True


class FriendPrivacySettings(models.Model):
    """
    Model for friend-specific privacy settings (per-friend customization)
    """
    FRIEND_VISIBILITY_CHOICES = [
        ('full', 'Full Access'),
        ('limited', 'Limited Access'),
        ('minimal', 'Minimal Access'),
        ('blocked', 'Blocked'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='friend_privacy_settings',
        help_text="User who owns these privacy settings"
    )
    
    friend = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='privacy_settings_for_me',
        help_text="Friend these settings apply to"
    )
    
    visibility_level = models.CharField(
        max_length=20,
        choices=FRIEND_VISIBILITY_CHOICES,
        default='full',
        help_text="Level of access this friend has"
    )
    
    # Specific permissions
    can_see_tasks = models.BooleanField(
        default=True,
        help_text="Whether friend can see user's tasks"
    )
    
    can_see_task_completions = models.BooleanField(
        default=True,
        help_text="Whether friend can see task completions"
    )
    
    can_see_achievements = models.BooleanField(
        default=True,
        help_text="Whether friend can see achievements"
    )
    
    can_invite_to_shared_tasks = models.BooleanField(
        default=True,
        help_text="Whether friend can invite user to shared tasks"
    )
    
    can_see_activity_feed = models.BooleanField(
        default=True,
        help_text="Whether friend can see user's activity feed"
    )
    
    can_see_leaderboard_position = models.BooleanField(
        default=True,
        help_text="Whether friend can see user in leaderboards"
    )
    
    # Notification settings for this friend
    notify_on_activities = models.BooleanField(
        default=True,
        help_text="Whether to notify this friend of user's activities"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_accounts_friend_privacy_settings'
        verbose_name = 'Friend Privacy Settings'
        verbose_name_plural = 'Friend Privacy Settings'
        unique_together = ('user', 'friend')
        indexes = [
            models.Index(fields=['user', 'visibility_level']),
            models.Index(fields=['friend']),
        ]
    
    def __str__(self):
        return f"{self.user.phone_number} -> {self.friend.phone_number}: {self.get_visibility_level_display()}"
    
    def clean(self):
        """Validate that user and friend are different"""
        if self.user == self.friend:
            raise ValidationError("User cannot set privacy settings for themselves")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    @classmethod
    def get_or_create_for_friendship(cls, user, friend):
        """Get or create friend privacy settings with default values"""
        settings, created = cls.objects.get_or_create(
            user=user,
            friend=friend,
            defaults={
                'visibility_level': 'full',
                'can_see_tasks': True,
                'can_see_task_completions': True,
                'can_see_achievements': True,
                'can_invite_to_shared_tasks': True,
                'can_see_activity_feed': True,
                'can_see_leaderboard_position': True,
                'notify_on_activities': True,
            }
        )
        return settings
    
    def apply_visibility_level(self):
        """Apply preset visibility level to individual permissions"""
        if self.visibility_level == 'full':
            self.can_see_tasks = True
            self.can_see_task_completions = True
            self.can_see_achievements = True
            self.can_invite_to_shared_tasks = True
            self.can_see_activity_feed = True
            self.can_see_leaderboard_position = True
            self.notify_on_activities = True
        elif self.visibility_level == 'limited':
            self.can_see_tasks = False
            self.can_see_task_completions = True
            self.can_see_achievements = True
            self.can_invite_to_shared_tasks = True
            self.can_see_activity_feed = True
            self.can_see_leaderboard_position = True
            self.notify_on_activities = True
        elif self.visibility_level == 'minimal':
            self.can_see_tasks = False
            self.can_see_task_completions = False
            self.can_see_achievements = True
            self.can_invite_to_shared_tasks = False
            self.can_see_activity_feed = False
            self.can_see_leaderboard_position = False
            self.notify_on_activities = False
        elif self.visibility_level == 'blocked':
            self.can_see_tasks = False
            self.can_see_task_completions = False
            self.can_see_achievements = False
            self.can_invite_to_shared_tasks = False
            self.can_see_activity_feed = False
            self.can_see_leaderboard_position = False
            self.notify_on_activities = False


class PrivateTask(models.Model):
    """
    Model for marking specific tasks as private regardless of global settings
    """
    task = models.OneToOneField(
        'task_management.Task',
        on_delete=models.CASCADE,
        related_name='private_settings',
        help_text="Task that has private settings"
    )
    
    is_completely_private = models.BooleanField(
        default=True,
        help_text="Whether task is completely hidden from all friends"
    )
    
    visible_to_friends = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='visible_private_tasks',
        help_text="Specific friends who can see this private task"
    )
    
    hide_from_activity_feed = models.BooleanField(
        default=True,
        help_text="Whether to hide task completion from activity feed"
    )
    
    hide_from_leaderboards = models.BooleanField(
        default=True,
        help_text="Whether to exclude points from leaderboards"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_accounts_private_task'
        verbose_name = 'Private Task'
        verbose_name_plural = 'Private Tasks'
    
    def __str__(self):
        return f"Private settings for: {self.task.title}"
    
    def can_view_task(self, requesting_user):
        """Check if requesting user can view this private task"""
        # Task owner can always see their own tasks
        if self.task.user == requesting_user:
            return True
        
        # If completely private, only owner can see
        if self.is_completely_private:
            return False
        
        # Check if user is in the visible_to_friends list
        return self.visible_to_friends.filter(id=requesting_user.id).exists()