"""
Notification services for creating and managing notifications.
"""
from django.contrib.auth import get_user_model
from .models import Notification
from .utils import notification_sender
from typing import Dict, Any, List, Optional

User = get_user_model()


class NotificationService:
    """
    Service class for creating and managing notifications.
    """
    
    @staticmethod
    def create_notification(
        user: User,
        notification_type: str,
        title: str,
        message: str,
        data: Dict[str, Any] = None,
        send_realtime: bool = True
    ) -> Notification:
        """
        Create a notification and optionally send it via WebSocket.
        
        Args:
            user: User to send notification to
            notification_type: Type of notification
            title: Notification title
            message: Notification message
            data: Additional notification data
            send_realtime: Whether to send via WebSocket
            
        Returns:
            Created Notification instance
        """
        # Create notification in database
        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            data=data or {}
        )
        
        # Send real-time notification if requested
        if send_realtime:
            notification_data = {
                'notification_id': notification.id,
                'title': title,
                'message': message,
                'data': data or {}
            }
            
            notification_sender.send_to_user(
                user.id,
                notification_type,
                notification_data
            )
        
        return notification
    
    @staticmethod
    def create_task_reminder(
        user: User,
        task_id: int,
        task_title: str,
        deadline: str,
        message: str = None
    ) -> Notification:
        """
        Create a task reminder notification.
        """
        title = "Task Reminder"
        message = message or f'Task "{task_title}" is due soon!'
        
        data = {
            'task_id': task_id,
            'task_title': task_title,
            'deadline': deadline
        }
        
        notification = NotificationService.create_notification(
            user=user,
            notification_type='task_reminder',
            title=title,
            message=message,
            data=data
        )
        
        # Send specific task reminder via WebSocket
        notification_sender.send_task_reminder(
            user_id=user.id,
            notification_id=notification.id,
            task_id=task_id,
            task_title=task_title,
            deadline=deadline,
            message=message
        )
        
        return notification
    
    @staticmethod
    def create_friend_request_notification(
        user: User,
        requester: User
    ) -> Notification:
        """
        Create a friend request notification.
        """
        title = "Friend Request"
        message = f"{requester.username} sent you a friend request"
        
        data = {
            'requester_id': requester.id,
            'requester_username': requester.username
        }
        
        notification = NotificationService.create_notification(
            user=user,
            notification_type='friend_request',
            title=title,
            message=message,
            data=data
        )
        
        # Send specific friend request via WebSocket
        notification_sender.send_friend_request(
            user_id=user.id,
            notification_id=notification.id,
            requester_id=requester.id,
            requester_name=requester.username,
            message=message
        )
        
        return notification
    
    @staticmethod
    def create_task_completion_notification(
        user: User,
        task_id: int,
        task_title: str,
        completed_by: User,
        points_earned: int
    ) -> Notification:
        """
        Create a task completion notification.
        """
        title = "Task Completed"
        message = f"{completed_by.username} completed \"{task_title}\""
        
        data = {
            'task_id': task_id,
            'task_title': task_title,
            'completed_by_id': completed_by.id,
            'completed_by_username': completed_by.username,
            'points_earned': points_earned
        }
        
        notification = NotificationService.create_notification(
            user=user,
            notification_type='task_completed',
            title=title,
            message=message,
            data=data
        )
        
        # Send specific task completion via WebSocket
        notification_sender.send_task_completed(
            user_id=user.id,
            notification_id=notification.id,
            task_id=task_id,
            task_title=task_title,
            completed_by_id=completed_by.id,
            completed_by_name=completed_by.username,
            points_earned=points_earned,
            message=message
        )
        
        return notification
    
    @staticmethod
    def create_achievement_notification(
        user: User,
        achievement_id: int,
        achievement_name: str,
        points_earned: int
    ) -> Notification:
        """
        Create an achievement earned notification.
        """
        title = "Achievement Unlocked!"
        message = f'You earned the "{achievement_name}" achievement!'
        
        data = {
            'achievement_id': achievement_id,
            'achievement_name': achievement_name,
            'points_earned': points_earned
        }
        
        notification = NotificationService.create_notification(
            user=user,
            notification_type='achievement_earned',
            title=title,
            message=message,
            data=data
        )
        
        # Send specific achievement via WebSocket
        notification_sender.send_achievement_earned(
            user_id=user.id,
            notification_id=notification.id,
            achievement_id=achievement_id,
            achievement_name=achievement_name,
            points_earned=points_earned,
            message=message
        )
        
        return notification
    
    @staticmethod
    def create_shared_task_invite_notification(
        user: User,
        task_id: int,
        task_title: str,
        inviter: User
    ) -> Notification:
        """
        Create a shared task invitation notification.
        """
        title = "Shared Task Invitation"
        message = f'{inviter.username} invited you to join "{task_title}"'
        
        data = {
            'task_id': task_id,
            'task_title': task_title,
            'inviter_id': inviter.id,
            'inviter_username': inviter.username
        }
        
        notification = NotificationService.create_notification(
            user=user,
            notification_type='shared_task_invite',
            title=title,
            message=message,
            data=data
        )
        
        # Send specific shared task invite via WebSocket
        notification_sender.send_shared_task_invite(
            user_id=user.id,
            notification_id=notification.id,
            task_id=task_id,
            task_title=task_title,
            inviter_id=inviter.id,
            inviter_name=inviter.username,
            message=message
        )
        
        return notification
    
    @staticmethod
    def create_friend_activity_notification(
        user: User,
        friend: User,
        activity_type: str,
        activity_message: str
    ) -> Notification:
        """
        Create a friend activity notification.
        """
        title = "Friend Activity"
        message = activity_message
        
        data = {
            'friend_id': friend.id,
            'friend_username': friend.username,
            'activity_type': activity_type
        }
        
        notification = NotificationService.create_notification(
            user=user,
            notification_type='friend_activity',
            title=title,
            message=message,
            data=data
        )
        
        # Send specific friend activity via WebSocket
        notification_sender.send_friend_activity(
            user_id=user.id,
            notification_id=notification.id,
            friend_id=friend.id,
            friend_name=friend.username,
            activity_type=activity_type,
            message=message
        )
        
        return notification
    
    @staticmethod
    def notify_multiple_users(
        users: List[User],
        notification_type: str,
        title: str,
        message: str,
        data: Dict[str, Any] = None
    ) -> List[Notification]:
        """
        Create notifications for multiple users.
        """
        notifications = []
        
        for user in users:
            notification = NotificationService.create_notification(
                user=user,
                notification_type=notification_type,
                title=title,
                message=message,
                data=data
            )
            notifications.append(notification)
        
        return notifications
    
    @staticmethod
    def mark_notifications_read(user: User, notification_ids: List[int] = None) -> int:
        """
        Mark notifications as read for a user.
        
        Args:
            user: User whose notifications to mark as read
            notification_ids: Specific notification IDs to mark (None for all)
            
        Returns:
            Number of notifications marked as read
        """
        queryset = Notification.objects.filter(user=user, is_read=False)
        
        if notification_ids:
            queryset = queryset.filter(id__in=notification_ids)
        
        return queryset.update(is_read=True)
    
    @staticmethod
    def get_unread_count(user: User) -> int:
        """
        Get count of unread notifications for a user.
        """
        return Notification.objects.filter(user=user, is_read=False).count()
    
    @staticmethod
    def cleanup_old_notifications(days: int = 30) -> int:
        """
        Clean up old read notifications.
        
        Args:
            days: Number of days to keep notifications
            
        Returns:
            Number of notifications deleted
        """
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        deleted_count, _ = Notification.objects.filter(
            is_read=True,
            created_at__lt=cutoff_date
        ).delete()
        
        return deleted_count