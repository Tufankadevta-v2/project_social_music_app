from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .privacy_models import PrivacySettings, FriendPrivacySettings, PrivateTask
from task_management.models import Task
from friendships.models import Friendship

User = get_user_model()


@receiver(post_save, sender=User)
def create_default_privacy_settings(sender, instance, created, **kwargs):
    """
    Create default privacy settings when a new user is created
    """
    if created:
        PrivacySettings.get_or_create_for_user(instance)


@receiver(post_save, sender=Friendship)
def handle_friendship_privacy_settings(sender, instance, created, **kwargs):
    """
    Handle privacy settings when friendships are created or updated
    """
    if created and instance.status == 'accepted':
        # Create default friend privacy settings for both users
        FriendPrivacySettings.get_or_create_for_friendship(
            instance.requester, 
            instance.addressee
        )
        FriendPrivacySettings.get_or_create_for_friendship(
            instance.addressee, 
            instance.requester
        )
    
    elif instance.status == 'blocked':
        # When a user is blocked, set their privacy settings to blocked
        try:
            friend_settings = FriendPrivacySettings.objects.get(
                user=instance.addressee,
                friend=instance.requester
            )
            friend_settings.visibility_level = 'blocked'
            friend_settings.apply_visibility_level()
            friend_settings.save()
        except FriendPrivacySettings.DoesNotExist:
            # Create blocked settings
            FriendPrivacySettings.objects.create(
                user=instance.addressee,
                friend=instance.requester,
                visibility_level='blocked'
            )


@receiver(post_delete, sender=Friendship)
def cleanup_friendship_privacy_settings(sender, instance, **kwargs):
    """
    Clean up privacy settings when friendships are deleted
    """
    # Remove friend-specific privacy settings
    FriendPrivacySettings.objects.filter(
        user=instance.requester,
        friend=instance.addressee
    ).delete()
    
    FriendPrivacySettings.objects.filter(
        user=instance.addressee,
        friend=instance.requester
    ).delete()


@receiver(pre_save, sender=Task)
def handle_task_privacy_on_save(sender, instance, **kwargs):
    """
    Handle task privacy settings when tasks are saved
    """
    # If task is being marked as private, create PrivateTask settings
    if hasattr(instance, 'is_private') and instance.is_private:
        # This will be handled after the task is saved
        pass


@receiver(post_save, sender=Task)
def create_private_task_settings(sender, instance, created, **kwargs):
    """
    Create private task settings if task is marked as private
    """
    if hasattr(instance, 'is_private') and instance.is_private:
        # Check if PrivateTask settings already exist
        if not hasattr(instance, 'private_settings'):
            PrivateTask.objects.get_or_create(
                task=instance,
                defaults={
                    'is_completely_private': True,
                    'hide_from_activity_feed': True,
                    'hide_from_leaderboards': True
                }
            )


@receiver(post_save, sender=PrivacySettings)
def handle_privacy_settings_change(sender, instance, **kwargs):
    """
    Handle side effects when privacy settings are changed
    """
    user = instance.user
    
    # If user disabled friend requests, decline all pending requests
    if not instance.allow_friend_requests:
        Friendship.objects.filter(
            addressee=user,
            status='pending'
        ).update(status='declined')
    
    # If user disabled shared task invites, remove pending participations
    if not instance.allow_shared_task_invites:
        from task_management.models import TaskParticipation
        TaskParticipation.objects.filter(
            user=user,
            status='pending'
        ).delete()
    
    # If user made profile completely private, update friend settings
    if instance.profile_visibility == 'private':
        # Optionally update all friend settings to be more restrictive
        FriendPrivacySettings.objects.filter(
            user=user,
            visibility_level='full'
        ).update(visibility_level='limited')


@receiver(post_save, sender=FriendPrivacySettings)
def handle_friend_privacy_change(sender, instance, **kwargs):
    """
    Handle changes to friend-specific privacy settings
    """
    # If friend is blocked, remove them from any shared tasks
    if instance.visibility_level == 'blocked':
        from task_management.models import TaskParticipation, SharedTask
        
        # Remove friend from user's shared tasks
        shared_tasks = SharedTask.objects.filter(creator=instance.user)
        TaskParticipation.objects.filter(
            shared_task__in=shared_tasks,
            user=instance.friend
        ).delete()
        
        # Remove user from friend's shared tasks
        friend_shared_tasks = SharedTask.objects.filter(creator=instance.friend)
        TaskParticipation.objects.filter(
            shared_task__in=friend_shared_tasks,
            user=instance.user
        ).delete()


@receiver(post_delete, sender=PrivateTask)
def handle_private_task_deletion(sender, instance, **kwargs):
    """
    Handle cleanup when private task settings are deleted
    """
    # Update the task to not be private anymore
    try:
        task = instance.task
        if hasattr(task, 'is_private'):
            task.is_private = False
            task.save(update_fields=['is_private'])
    except Task.DoesNotExist:
        pass


# Signal to handle activity feed privacy
@receiver(post_save, sender='social_feed.ActivityFeed')
def handle_activity_feed_privacy(sender, instance, created, **kwargs):
    """
    Handle privacy settings for activity feed entries
    """
    if created:
        # Check if this activity should be public based on user's privacy settings
        privacy_settings = PrivacySettings.get_or_create_for_user(instance.user)
        
        # Update activity visibility based on privacy settings
        should_be_public = privacy_settings.should_show_in_activity_feed(instance.activity_type)
        
        if not should_be_public:
            instance.is_public = False
            instance.save(update_fields=['is_public'])


# Signal to handle notification privacy
@receiver(post_save, sender='notifications.Notification')
def handle_notification_privacy(sender, instance, created, **kwargs):
    """
    Handle privacy settings for notifications
    """
    if created and hasattr(instance, 'sender_user'):
        from user_accounts.privacy_utils import should_notify_user
        
        # Check if the target user should receive this notification
        if not should_notify_user(instance.user, instance.sender_user, instance.notification_type):
            # Delete the notification if privacy settings don't allow it
            instance.delete()


def connect_privacy_signals():
    """
    Connect all privacy-related signals
    """
    # Signals are automatically connected when this module is imported
    pass