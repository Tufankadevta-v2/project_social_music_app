"""
Signal handlers for automatic notification creation.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.db import models
from .services import NotificationService

User = get_user_model()


@receiver(post_save, sender='task_management.Task')
def task_completed_notification(sender, instance, created, **kwargs):
    """
    Send notifications when a task is completed.
    """
    if not created and instance.status == 'completed' and instance.completed_at:
        # Check if this is a shared task
        if hasattr(instance, 'shared_details') and instance.shared_details:
            shared_task = instance.shared_details
            
            # Notify all participants except the one who completed it
            participants = shared_task.participants.exclude(id=instance.user.id)
            
            for participant in participants:
                NotificationService.create_task_completion_notification(
                    user=participant,
                    task_id=instance.id,
                    task_title=instance.title,
                    completed_by=instance.user,
                    points_earned=instance.points_value
                )


@receiver(post_save, sender='task_management.UserAchievement')
def achievement_earned_notification(sender, instance, created, **kwargs):
    """
    Send notification when a user earns an achievement.
    """
    if created:
        NotificationService.create_achievement_notification(
            user=instance.user,
            achievement_id=instance.achievement.id,
            achievement_name=instance.achievement.name,
            points_earned=instance.achievement.points_required
        )


@receiver(post_save, sender='friendships.Friendship')
def friend_request_notification(sender, instance, created, **kwargs):
    """
    Send notification when a friend request is sent.
    """
    if created and instance.status == 'pending':
        NotificationService.create_friend_request_notification(
            user=instance.user2,  # Receiver of the request
            requester=instance.user1  # Sender of the request
        )


@receiver(post_save, sender='task_management.TaskParticipation')
def shared_task_invite_notification(sender, instance, created, **kwargs):
    """
    Send notification when a user is invited to a shared task.
    """
    if created:
        shared_task = instance.shared_task
        task = shared_task.task
        
        # Don't notify the creator
        if instance.user != shared_task.creator:
            NotificationService.create_shared_task_invite_notification(
                user=instance.user,
                task_id=task.id,
                task_title=task.title,
                inviter=shared_task.creator
            )


@receiver(post_save, sender='social_feed.ActivityFeed')
def friend_activity_notification(sender, instance, created, **kwargs):
    """
    Send notifications to friends when a user has activity.
    """
    if created and instance.is_public:
        # Get user's friends
        from friendships.models import Friendship
        
        friends = User.objects.filter(
            models.Q(sent_friend_requests__addressee=instance.user, sent_friend_requests__status='accepted') |
            models.Q(received_friend_requests__requester=instance.user, received_friend_requests__status='accepted')
        ).distinct()
        
        # Create activity message based on activity type
        activity_messages = {
            'task_completed': f"{instance.user.username} completed a task!",
            'achievement_earned': f"{instance.user.username} earned a new achievement!",
            'shared_task_completed': f"{instance.user.username} completed a shared task!",
            'milestone_reached': f"{instance.user.username} reached a new milestone!"
        }
        
        message = activity_messages.get(
            instance.activity_type,
            f"{instance.user.username} has new activity"
        )
        
        # Notify all friends
        for friend in friends:
            NotificationService.create_friend_activity_notification(
                user=friend,
                friend=instance.user,
                activity_type=instance.activity_type,
                activity_message=message
            )