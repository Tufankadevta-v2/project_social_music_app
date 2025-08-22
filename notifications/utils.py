"""
Utility functions for sending real-time notifications.
"""
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from datetime import datetime
from typing import Dict, Any, List, Optional


class NotificationSender:
    """
    Utility class for sending real-time notifications through WebSocket channels.
    """
    
    def __init__(self):
        self.channel_layer = get_channel_layer()
    
    def send_to_user(self, user_id: int, notification_type: str, data: Dict[str, Any]):
        """
        Send a notification to a specific user.
        
        Args:
            user_id: ID of the user to send notification to
            notification_type: Type of notification (task_reminder, friend_activity, etc.)
            data: Notification data including title, message, and additional fields
        """
        if not self.channel_layer:
            return False
        
        group_name = f'user_notifications_{user_id}'
        
        # Add timestamp if not provided
        if 'timestamp' not in data:
            data['timestamp'] = datetime.now().isoformat()
        
        try:
            async_to_sync(self.channel_layer.group_send)(
                group_name,
                {
                    'type': notification_type,
                    **data
                }
            )
            return True
        except Exception as e:
            # Log error in production
            print(f"Failed to send notification to user {user_id}: {e}")
            return False
    
    def send_to_multiple_users(self, user_ids: List[int], notification_type: str, data: Dict[str, Any]):
        """
        Send a notification to multiple users.
        
        Args:
            user_ids: List of user IDs to send notification to
            notification_type: Type of notification
            data: Notification data
        """
        success_count = 0
        for user_id in user_ids:
            if self.send_to_user(user_id, notification_type, data):
                success_count += 1
        return success_count
    
    def send_task_reminder(self, user_id: int, notification_id: int, task_id: int, 
                          task_title: str, deadline: str, message: str = None):
        """
        Send a task reminder notification.
        """
        data = {
            'notification_id': notification_id,
            'title': 'Task Reminder',
            'message': message or f'Task "{task_title}" is due soon!',
            'task_id': task_id,
            'deadline': deadline,
        }
        return self.send_to_user(user_id, 'task_reminder', data)
    
    def send_friend_activity(self, user_id: int, notification_id: int, friend_id: int,
                           friend_name: str, activity_type: str, message: str):
        """
        Send a friend activity notification.
        """
        data = {
            'notification_id': notification_id,
            'title': 'Friend Activity',
            'message': message,
            'friend_id': friend_id,
            'friend_name': friend_name,
            'activity_type': activity_type,
        }
        return self.send_to_user(user_id, 'friend_activity', data)
    
    def send_achievement_earned(self, user_id: int, notification_id: int, 
                              achievement_id: int, achievement_name: str, 
                              points_earned: int, message: str = None):
        """
        Send an achievement earned notification.
        """
        data = {
            'notification_id': notification_id,
            'title': 'Achievement Unlocked!',
            'message': message or f'You earned the "{achievement_name}" achievement!',
            'achievement_id': achievement_id,
            'achievement_name': achievement_name,
            'points_earned': points_earned,
        }
        return self.send_to_user(user_id, 'achievement_earned', data)
    
    def send_friend_request(self, user_id: int, notification_id: int, 
                          requester_id: int, requester_name: str, message: str = None):
        """
        Send a friend request notification.
        """
        data = {
            'notification_id': notification_id,
            'title': 'Friend Request',
            'message': message or f'{requester_name} sent you a friend request',
            'requester_id': requester_id,
            'requester_name': requester_name,
        }
        return self.send_to_user(user_id, 'friend_request', data)
    
    def send_shared_task_invite(self, user_id: int, notification_id: int, 
                              task_id: int, task_title: str, inviter_id: int, 
                              inviter_name: str, message: str = None):
        """
        Send a shared task invitation notification.
        """
        data = {
            'notification_id': notification_id,
            'title': 'Shared Task Invitation',
            'message': message or f'{inviter_name} invited you to join "{task_title}"',
            'task_id': task_id,
            'task_title': task_title,
            'inviter_id': inviter_id,
            'inviter_name': inviter_name,
        }
        return self.send_to_user(user_id, 'shared_task_invite', data)
    
    def send_task_completed(self, user_id: int, notification_id: int, 
                          task_id: int, task_title: str, completed_by_id: int,
                          completed_by_name: str, points_earned: int, message: str = None):
        """
        Send a task completion notification.
        """
        data = {
            'notification_id': notification_id,
            'title': 'Task Completed',
            'message': message or f'{completed_by_name} completed "{task_title}"',
            'task_id': task_id,
            'task_title': task_title,
            'user_id': completed_by_id,
            'user_name': completed_by_name,
            'points_earned': points_earned,
        }
        return self.send_to_user(user_id, 'task_completed', data)
    
    def send_general_notification(self, user_id: int, notification_id: int, 
                                title: str, message: str, data: Dict[str, Any] = None):
        """
        Send a general notification.
        """
        notification_data = {
            'notification_id': notification_id,
            'title': title,
            'message': message,
            'data': data or {},
        }
        return self.send_to_user(user_id, 'general_notification', notification_data)


# Global instance for easy access
notification_sender = NotificationSender()


# Convenience functions
def send_notification_to_user(user_id: int, notification_type: str, data: Dict[str, Any]):
    """
    Convenience function to send notification to a user.
    """
    return notification_sender.send_to_user(user_id, notification_type, data)


def send_notification_to_users(user_ids: List[int], notification_type: str, data: Dict[str, Any]):
    """
    Convenience function to send notification to multiple users.
    """
    return notification_sender.send_to_multiple_users(user_ids, notification_type, data)