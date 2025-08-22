"""
Notification helpers for task management
These functions prepare notification data that can be sent when the notification system is implemented
"""
from typing import List, Dict, Any
from django.contrib.auth import get_user_model
from .models import SharedTask, TaskParticipation

User = get_user_model()


def prepare_shared_task_invitation_notification(shared_task: SharedTask, invited_users: List[User]) -> List[Dict[str, Any]]:
    """
    Prepare notification data for shared task invitations
    
    Args:
        shared_task: The shared task instance
        invited_users: List of users who were invited
        
    Returns:
        List of notification data dictionaries
    """
    notifications = []
    
    for user in invited_users:
        notification_data = {
            'user_id': user.id,
            'notification_type': 'shared_task_invite',
            'title': 'New Shared Task Invitation',
            'message': f'{shared_task.creator.phone_number} invited you to join "{shared_task.task.title}"',
            'data': {
                'shared_task_id': shared_task.id,
                'task_id': shared_task.task.id,
                'creator_id': shared_task.creator.id,
                'creator_phone': shared_task.creator.phone_number,
                'task_title': shared_task.task.title,
                'task_description': shared_task.task.description,
                'deadline': shared_task.task.deadline.isoformat() if shared_task.task.deadline else None,
                'points_value': shared_task.task.points_value,
                'is_competitive': shared_task.is_competitive,
            }
        }
        notifications.append(notification_data)
    
    return notifications


def prepare_shared_task_completion_notification(participation: TaskParticipation) -> List[Dict[str, Any]]:
    """
    Prepare notification data for shared task completion
    
    Args:
        participation: The completed task participation
        
    Returns:
        List of notification data dictionaries for other participants
    """
    notifications = []
    shared_task = participation.shared_task
    
    # Notify all other participants
    other_participants = TaskParticipation.objects.filter(
        shared_task=shared_task
    ).exclude(user=participation.user).select_related('user')
    
    for other_participation in other_participants:
        notification_data = {
            'user_id': other_participation.user.id,
            'notification_type': 'shared_task_completed',
            'title': 'Friend Completed Shared Task',
            'message': f'{participation.user.phone_number} completed "{shared_task.task.title}"',
            'data': {
                'shared_task_id': shared_task.id,
                'task_id': shared_task.task.id,
                'completed_by_id': participation.user.id,
                'completed_by_phone': participation.user.phone_number,
                'task_title': shared_task.task.title,
                'points_earned': participation.points_earned,
                'completion_rank': participation.completion_rank,
                'completed_at': participation.completed_at.isoformat() if participation.completed_at else None,
            }
        }
        notifications.append(notification_data)
    
    return notifications


def prepare_shared_task_reminder_notification(shared_task: SharedTask, hours_until_deadline: int) -> List[Dict[str, Any]]:
    """
    Prepare notification data for shared task deadline reminders
    
    Args:
        shared_task: The shared task instance
        hours_until_deadline: Hours remaining until deadline
        
    Returns:
        List of notification data dictionaries for pending participants
    """
    notifications = []
    
    # Notify participants who haven't completed the task
    pending_participants = TaskParticipation.objects.filter(
        shared_task=shared_task,
        status='pending'
    ).select_related('user')
    
    for participation in pending_participants:
        notification_data = {
            'user_id': participation.user.id,
            'notification_type': 'shared_task_reminder',
            'title': 'Shared Task Deadline Approaching',
            'message': f'"{shared_task.task.title}" is due in {hours_until_deadline} hours',
            'data': {
                'shared_task_id': shared_task.id,
                'task_id': shared_task.task.id,
                'task_title': shared_task.task.title,
                'deadline': shared_task.task.deadline.isoformat() if shared_task.task.deadline else None,
                'hours_until_deadline': hours_until_deadline,
                'points_value': shared_task.task.points_value,
                'creator_phone': shared_task.creator.phone_number,
            }
        }
        notifications.append(notification_data)
    
    return notifications


def prepare_participant_removed_notification(shared_task: SharedTask, removed_user: User) -> Dict[str, Any]:
    """
    Prepare notification data for participant removal
    
    Args:
        shared_task: The shared task instance
        removed_user: The user who was removed
        
    Returns:
        Notification data dictionary
    """
    return {
        'user_id': removed_user.id,
        'notification_type': 'shared_task_removed',
        'title': 'Removed from Shared Task',
        'message': f'You were removed from "{shared_task.task.title}" by {shared_task.creator.phone_number}',
        'data': {
            'shared_task_id': shared_task.id,
            'task_id': shared_task.task.id,
            'task_title': shared_task.task.title,
            'creator_id': shared_task.creator.id,
            'creator_phone': shared_task.creator.phone_number,
        }
    }


def prepare_shared_task_deleted_notification(shared_task: SharedTask, participants: List[User]) -> List[Dict[str, Any]]:
    """
    Prepare notification data for shared task deletion
    
    Args:
        shared_task: The shared task instance (before deletion)
        participants: List of participants (excluding creator)
        
    Returns:
        List of notification data dictionaries
    """
    notifications = []
    
    for user in participants:
        notification_data = {
            'user_id': user.id,
            'notification_type': 'shared_task_deleted',
            'title': 'Shared Task Cancelled',
            'message': f'{shared_task.creator.phone_number} cancelled the shared task "{shared_task.task.title}"',
            'data': {
                'task_title': shared_task.task.title,
                'creator_id': shared_task.creator.id,
                'creator_phone': shared_task.creator.phone_number,
                'cancelled_at': shared_task.created_at.isoformat(),  # Use created_at as reference
            }
        }
        notifications.append(notification_data)
    
    return notifications


# TODO: Integration functions for when notification system is implemented
def send_notifications(notification_data_list: List[Dict[str, Any]]) -> None:
    """
    Send notifications using the notification system
    This function should be implemented when the notification system is ready
    
    Args:
        notification_data_list: List of notification data dictionaries
    """
    # Placeholder for notification system integration
    # This would typically:
    # 1. Create Notification model instances
    # 2. Send push notifications via Firebase
    # 3. Send real-time notifications via WebSocket
    pass


def send_notification(notification_data: Dict[str, Any]) -> None:
    """
    Send a single notification using the notification system
    
    Args:
        notification_data: Notification data dictionary
    """
    send_notifications([notification_data])