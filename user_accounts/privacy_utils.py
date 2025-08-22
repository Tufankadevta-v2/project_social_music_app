from django.contrib.auth import get_user_model
from .privacy_models import PrivacySettings, FriendPrivacySettings, PrivateTask

User = get_user_model()


class PrivacyChecker:
    """
    Utility class for checking privacy permissions across the application
    """
    
    def __init__(self, requesting_user):
        self.requesting_user = requesting_user
    
    def can_view_user_profile(self, target_user):
        """Check if requesting user can view target user's profile"""
        if self.requesting_user == target_user:
            return True
        
        privacy_settings = PrivacySettings.get_or_create_for_user(target_user)
        return privacy_settings.can_view_profile(self.requesting_user)
    
    def can_view_user_tasks(self, target_user):
        """Check if requesting user can view target user's tasks"""
        if self.requesting_user == target_user:
            return True
        
        privacy_settings = PrivacySettings.get_or_create_for_user(target_user)
        base_permission = privacy_settings.can_view_tasks(self.requesting_user)
        
        if not base_permission:
            return False
        
        # Check friend-specific settings
        try:
            friend_settings = FriendPrivacySettings.objects.get(
                user=target_user,
                friend=self.requesting_user
            )
            return friend_settings.can_see_tasks
        except FriendPrivacySettings.DoesNotExist:
            return base_permission
    
    def can_view_task_completions(self, target_user):
        """Check if requesting user can view target user's task completions"""
        if self.requesting_user == target_user:
            return True
        
        privacy_settings = PrivacySettings.get_or_create_for_user(target_user)
        base_permission = privacy_settings.can_view_task_completions(self.requesting_user)
        
        if not base_permission:
            return False
        
        # Check friend-specific settings
        try:
            friend_settings = FriendPrivacySettings.objects.get(
                user=target_user,
                friend=self.requesting_user
            )
            return friend_settings.can_see_task_completions
        except FriendPrivacySettings.DoesNotExist:
            return base_permission
    
    def can_view_achievements(self, target_user):
        """Check if requesting user can view target user's achievements"""
        if self.requesting_user == target_user:
            return True
        
        privacy_settings = PrivacySettings.get_or_create_for_user(target_user)
        base_permission = privacy_settings.can_view_achievements(self.requesting_user)
        
        if not base_permission:
            return False
        
        # Check friend-specific settings
        try:
            friend_settings = FriendPrivacySettings.objects.get(
                user=target_user,
                friend=self.requesting_user
            )
            return friend_settings.can_see_achievements
        except FriendPrivacySettings.DoesNotExist:
            return base_permission
    
    def can_view_activity_feed(self, target_user):
        """Check if requesting user can view target user's activity feed"""
        if self.requesting_user == target_user:
            return True
        
        # Check if users are friends first
        from friendships.models import Friendship
        if not Friendship.are_friends(self.requesting_user, target_user):
            return False
        
        # Check friend-specific settings
        try:
            friend_settings = FriendPrivacySettings.objects.get(
                user=target_user,
                friend=self.requesting_user
            )
            return friend_settings.can_see_activity_feed
        except FriendPrivacySettings.DoesNotExist:
            return True  # Default to allowing friends to see activity feed
    
    def can_invite_to_shared_task(self, target_user):
        """Check if requesting user can invite target user to shared tasks"""
        if self.requesting_user == target_user:
            return False  # Can't invite yourself
        
        privacy_settings = PrivacySettings.get_or_create_for_user(target_user)
        if not privacy_settings.allow_shared_task_invites:
            return False
        
        # Check friend-specific settings
        try:
            friend_settings = FriendPrivacySettings.objects.get(
                user=target_user,
                friend=self.requesting_user
            )
            return friend_settings.can_invite_to_shared_tasks
        except FriendPrivacySettings.DoesNotExist:
            return True  # Default to allowing invites from friends
    
    def can_see_in_leaderboard(self, target_user):
        """Check if target user should appear in leaderboards for requesting user"""
        if self.requesting_user == target_user:
            return True
        
        privacy_settings = PrivacySettings.get_or_create_for_user(target_user)
        if not privacy_settings.show_in_leaderboards:
            return False
        
        # Check friend-specific settings
        try:
            friend_settings = FriendPrivacySettings.objects.get(
                user=target_user,
                friend=self.requesting_user
            )
            return friend_settings.can_see_leaderboard_position
        except FriendPrivacySettings.DoesNotExist:
            return True  # Default to showing in leaderboards
    
    def can_view_specific_task(self, task):
        """Check if requesting user can view a specific task"""
        if task.user == self.requesting_user:
            return True
        
        # Check if task has private settings
        try:
            private_task = PrivateTask.objects.get(task=task)
            return private_task.can_view_task(self.requesting_user)
        except PrivateTask.DoesNotExist:
            # No private settings, use general task visibility
            return self.can_view_user_tasks(task.user)


def filter_tasks_by_privacy(queryset, requesting_user):
    """
    Filter a task queryset based on privacy settings
    """
    if not requesting_user.is_authenticated:
        return queryset.none()
    
    # Get user's own tasks
    own_tasks = queryset.filter(user=requesting_user)
    
    # Get tasks from friends that are visible
    from friendships.models import Friendship
    friends = Friendship.get_friends(requesting_user)
    
    visible_friend_tasks = queryset.none()
    
    for friend in friends:
        privacy_checker = PrivacyChecker(requesting_user)
        if privacy_checker.can_view_user_tasks(friend):
            friend_tasks = queryset.filter(user=friend)
            
            # Exclude private tasks unless specifically allowed
            private_task_ids = PrivateTask.objects.filter(
                task__user=friend,
                is_completely_private=True
            ).exclude(
                visible_to_friends=requesting_user
            ).values_list('task_id', flat=True)
            
            friend_tasks = friend_tasks.exclude(id__in=private_task_ids)
            if visible_friend_tasks.exists():
                visible_friend_tasks = visible_friend_tasks | friend_tasks
            else:
                visible_friend_tasks = friend_tasks
    
    if visible_friend_tasks.exists():
        return own_tasks | visible_friend_tasks
    else:
        return own_tasks


def filter_activity_feed_by_privacy(queryset, requesting_user):
    """
    Filter activity feed queryset based on privacy settings
    """
    if not requesting_user.is_authenticated:
        return queryset.none()
    
    # Get user's own activities
    own_activities = queryset.filter(user=requesting_user)
    
    # Get activities from friends that are visible
    from friendships.models import Friendship
    friends = Friendship.get_friends(requesting_user)
    
    visible_friend_activities = queryset.none()
    
    for friend in friends:
        privacy_checker = PrivacyChecker(requesting_user)
        if privacy_checker.can_view_activity_feed(friend):
            friend_activities = queryset.filter(user=friend, is_public=True)
            
            # Filter based on friend's activity feed visibility settings
            privacy_settings = PrivacySettings.get_or_create_for_user(friend)
            
            if privacy_settings.activity_feed_visibility == 'none':
                continue
            elif privacy_settings.activity_feed_visibility == 'achievements_only':
                friend_activities = friend_activities.filter(
                    activity_type__in=['achievement_earned', 'milestone_reached']
                )
            elif privacy_settings.activity_feed_visibility == 'tasks_only':
                friend_activities = friend_activities.filter(
                    activity_type__in=['task_completed', 'shared_task_completed']
                )
            
            if visible_friend_activities.exists():
                visible_friend_activities = visible_friend_activities | friend_activities
            else:
                visible_friend_activities = friend_activities
    
    if visible_friend_activities.exists():
        return own_activities | visible_friend_activities
    else:
        return own_activities


def should_notify_user(target_user, requesting_user, notification_type):
    """
    Check if target user should receive a notification from requesting user
    """
    if target_user == requesting_user:
        return False
    
    # Check if users are friends
    from friendships.models import Friendship
    if not Friendship.are_friends(requesting_user, target_user):
        return False
    
    # Check friend-specific notification settings
    try:
        friend_settings = FriendPrivacySettings.objects.get(
            user=target_user,
            friend=requesting_user
        )
        return friend_settings.notify_on_activities
    except FriendPrivacySettings.DoesNotExist:
        return True  # Default to sending notifications


def get_visible_users_for_leaderboard(requesting_user, user_queryset):
    """
    Filter users who should be visible in leaderboards for the requesting user
    """
    if not requesting_user.is_authenticated:
        return user_queryset.none()
    
    visible_users = []
    privacy_checker = PrivacyChecker(requesting_user)
    
    for user in user_queryset:
        if user == requesting_user or privacy_checker.can_see_in_leaderboard(user):
            visible_users.append(user.id)
    
    return user_queryset.filter(id__in=visible_users)


def create_privacy_aware_activity(user, activity_type, title, description, content=None, points_earned=0):
    """
    Create an activity feed entry that respects privacy settings
    """
    from social_feed.models import ActivityFeed
    
    privacy_settings = PrivacySettings.get_or_create_for_user(user)
    
    # Check if this activity type should be shown
    if not privacy_settings.should_show_in_activity_feed(activity_type):
        return None
    
    # Create the activity
    activity = ActivityFeed.objects.create(
        user=user,
        activity_type=activity_type,
        title=title,
        description=description,
        content=content or {},
        points_earned=points_earned,
        is_public=True  # Will be filtered by privacy settings when viewed
    )
    
    return activity