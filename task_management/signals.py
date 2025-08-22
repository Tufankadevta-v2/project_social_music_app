"""
Signal handlers for task management events
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Task, TaskParticipation, UserAchievement
from .achievement_service import AchievementService

User = get_user_model()


@receiver(post_save, sender=Task)
def check_achievements_on_task_completion(sender, instance, created, **kwargs):
    """
    Check for achievements when a task is completed
    """
    if not created and instance.status == 'completed' and instance.completed_at:
        # Check for newly unlocked achievements
        newly_unlocked = AchievementService.check_and_unlock_achievements(instance.user)
        
        if newly_unlocked:
            # Create activity feed entries for new achievements
            from social_feed.utils import ActivityFeedManager
            
            for user_achievement in newly_unlocked:
                ActivityFeedManager.create_achievement_activity(
                    user=instance.user,
                    achievement_name=user_achievement.achievement.name,
                    achievement_description=user_achievement.achievement.description,
                    points_earned=user_achievement.points_awarded
                )


@receiver(post_save, sender=TaskParticipation)
def check_achievements_on_participation_completion(sender, instance, created, **kwargs):
    """
    Check for achievements when a task participation is completed
    """
    if not created and instance.status == 'completed' and instance.completed_at:
        # Check for newly unlocked achievements
        newly_unlocked = AchievementService.check_and_unlock_achievements(instance.user)
        
        if newly_unlocked:
            # Create activity feed entries for new achievements
            from social_feed.utils import create_achievement_activity
            
            for user_achievement in newly_unlocked:
                create_achievement_activity(
                    user=instance.user,
                    achievement=user_achievement.achievement,
                    points_earned=user_achievement.points_awarded,
                    related_shared_task_id=instance.shared_task.id
                )


@receiver(post_save, sender=UserAchievement)
def send_achievement_notification(sender, instance, created, **kwargs):
    """
    Send notification when a user unlocks an achievement
    """
    if created and not instance.notification_sent:
        # Import here to avoid circular imports
        try:
            from notifications.utils import send_achievement_notification
            
            # Send achievement notification
            send_achievement_notification(
                user=instance.user,
                achievement=instance.achievement,
                points_awarded=instance.points_awarded
            )
            
            # Mark notification as sent
            instance.notification_sent = True
            instance.save(update_fields=['notification_sent'])
            
        except ImportError:
            # Notifications app not available, skip
            pass