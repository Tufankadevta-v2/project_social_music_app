from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import ActivityFeed, ActivityFeedSettings, ActivityFeedCache

User = get_user_model()


@receiver(post_save, sender=User)
def create_activity_feed_settings(sender, instance, created, **kwargs):
    """Create default activity feed settings for new users"""
    if created:
        ActivityFeedSettings.get_or_create_for_user(instance)


def create_activity_feed_entry(user, activity_type, title, description='', content=None, 
                             points_earned=0, is_public=True, **kwargs):
    """
    Helper function to create activity feed entries
    """
    # Check user's activity feed settings
    settings = ActivityFeedSettings.get_or_create_for_user(user)
    
    # Check if this type of activity should be shown
    show_activity = True
    if activity_type in ['task_completed', 'workout_completed'] and not settings.show_task_completions:
        show_activity = False
    elif activity_type in ['achievement_earned', 'goal_achieved'] and not settings.show_achievements:
        show_activity = False
    elif activity_type in ['milestone_reached', 'streak_achieved'] and not settings.show_milestones:
        show_activity = False
    elif activity_type in ['shared_task_completed', 'shared_task_created'] and not settings.show_shared_task_activities:
        show_activity = False
    elif activity_type == 'leaderboard_position' and not settings.show_leaderboard_positions:
        show_activity = False
    
    if not show_activity:
        return None
    
    # Apply privacy settings
    if settings.friends_only:
        is_public = True  # Will be filtered by friendship in views
    
    # Create activity feed entry
    activity = ActivityFeed.objects.create(
        user=user,
        activity_type=activity_type,
        title=title,
        description=description,
        content=content or {},
        points_earned=points_earned,
        is_public=is_public,
        **kwargs
    )
    
    # Clear user's activity feed cache
    ActivityFeedCache.clear_user_cache(user)
    
    return activity


# Task completion signals
def handle_task_completion(task, points_earned):
    """Handle task completion activity feed entry"""
    if task.is_shared:
        # For shared tasks, this will be handled by shared task completion
        return
    
    title = f"Completed task: {task.title}"
    description = f"Earned {points_earned} points"
    content = {
        'task_id': task.id,
        'task_title': task.title,
        'task_priority': task.priority,
        'points_earned': points_earned,
        'completion_time': task.completed_at.isoformat() if task.completed_at else None
    }
    
    create_activity_feed_entry(
        user=task.user,
        activity_type='task_completed',
        title=title,
        description=description,
        content=content,
        points_earned=points_earned,
        related_task_id=task.id
    )


def handle_shared_task_completion(participation):
    """Handle shared task completion activity feed entry"""
    shared_task = participation.shared_task
    task = shared_task.task
    
    title = f"Completed shared task: {task.title}"
    description = f"Earned {participation.points_earned} points"
    
    if participation.completion_rank:
        if participation.completion_rank == 1:
            description += " (1st place! 🏆)"
        elif participation.completion_rank == 2:
            description += " (2nd place! 🥈)"
        elif participation.completion_rank == 3:
            description += " (3rd place! 🥉)"
    
    content = {
        'shared_task_id': shared_task.id,
        'task_id': task.id,
        'task_title': task.title,
        'points_earned': participation.points_earned,
        'completion_rank': participation.completion_rank,
        'total_participants': shared_task.get_participant_count(),
        'completion_time': participation.completed_at.isoformat() if participation.completed_at else None
    }
    
    create_activity_feed_entry(
        user=participation.user,
        activity_type='shared_task_completed',
        title=title,
        description=description,
        content=content,
        points_earned=participation.points_earned,
        related_shared_task_id=shared_task.id
    )


def handle_achievement_earned(user, achievement_name, achievement_description, points_earned=0):
    """Handle achievement earned activity feed entry"""
    title = f"Achievement unlocked: {achievement_name}"
    description = achievement_description
    
    if points_earned > 0:
        description += f" (+{points_earned} points)"
    
    content = {
        'achievement_name': achievement_name,
        'achievement_description': achievement_description,
        'points_earned': points_earned
    }
    
    create_activity_feed_entry(
        user=user,
        activity_type='achievement_earned',
        title=title,
        description=description,
        content=content,
        points_earned=points_earned
    )


def handle_milestone_reached(user, milestone_type, milestone_value, points_earned=0):
    """Handle milestone reached activity feed entry"""
    title = f"Milestone reached: {milestone_value} {milestone_type}"
    description = f"Achieved {milestone_value} {milestone_type}!"
    
    if points_earned > 0:
        description += f" (+{points_earned} points)"
    
    content = {
        'milestone_type': milestone_type,
        'milestone_value': milestone_value,
        'points_earned': points_earned
    }
    
    create_activity_feed_entry(
        user=user,
        activity_type='milestone_reached',
        title=title,
        description=description,
        content=content,
        points_earned=points_earned
    )


def handle_shared_task_created(shared_task):
    """Handle shared task creation activity feed entry"""
    task = shared_task.task
    participant_count = shared_task.get_participant_count()
    
    title = f"Created shared task: {task.title}"
    description = f"Invited {participant_count - 1} friends to join"
    
    content = {
        'shared_task_id': shared_task.id,
        'task_id': task.id,
        'task_title': task.title,
        'participant_count': participant_count,
        'is_competitive': shared_task.is_competitive,
        'deadline': task.deadline.isoformat() if task.deadline else None
    }
    
    create_activity_feed_entry(
        user=shared_task.creator,
        activity_type='shared_task_created',
        title=title,
        description=description,
        content=content,
        related_shared_task_id=shared_task.id
    )


def handle_friend_joined(user):
    """Handle new friend joining activity feed entry"""
    title = f"Welcome to the community!"
    description = "Started their task management journey"
    
    content = {
        'join_date': user.date_joined.isoformat() if hasattr(user, 'date_joined') else None
    }
    
    create_activity_feed_entry(
        user=user,
        activity_type='friend_joined',
        title=title,
        description=description,
        content=content
    )


def handle_streak_achieved(user, streak_length, streak_type='task_completion'):
    """Handle streak achievement activity feed entry"""
    title = f"🔥 {streak_length}-day {streak_type.replace('_', ' ')} streak!"
    description = f"Maintained a {streak_length}-day streak"
    
    content = {
        'streak_length': streak_length,
        'streak_type': streak_type
    }
    
    create_activity_feed_entry(
        user=user,
        activity_type='streak_achieved',
        title=title,
        description=description,
        content=content,
        points_earned=streak_length * 5  # 5 points per day in streak
    )


def handle_leaderboard_position(user, position, leaderboard_type='global', time_period='weekly'):
    """Handle leaderboard position activity feed entry"""
    if position > 10:  # Only show top 10 positions
        return
    
    position_text = {1: '1st', 2: '2nd', 3: '3rd'}.get(position, f'{position}th')
    title = f"🏆 {position_text} place on {time_period} {leaderboard_type} leaderboard!"
    description = f"Ranked #{position} among friends"
    
    content = {
        'position': position,
        'leaderboard_type': leaderboard_type,
        'time_period': time_period
    }
    
    points_earned = max(50 - (position * 5), 10)  # More points for higher positions
    
    create_activity_feed_entry(
        user=user,
        activity_type='leaderboard_position',
        title=title,
        description=description,
        content=content,
        points_earned=points_earned
    )


# Signal handlers for clearing cache when settings change
@receiver(post_save, sender=ActivityFeedSettings)
def clear_cache_on_settings_change(sender, instance, **kwargs):
    """Clear user's activity feed cache when settings change"""
    ActivityFeedCache.clear_user_cache(instance.user)


@receiver(post_delete, sender=ActivityFeed)
def clear_cache_on_activity_delete(sender, instance, **kwargs):
    """Clear user's activity feed cache when activity is deleted"""
    ActivityFeedCache.clear_user_cache(instance.user)