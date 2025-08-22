"""
WebSocket consumers for real-time notifications.
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from user_accounts.models import User


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for handling real-time notifications.
    Supports user-specific notification channels with JWT authentication.
    """
    
    async def connect(self):
        """
        Handle WebSocket connection.
        Authenticate user and join their notification group.
        """
        # Get user from authentication
        self.user = await self.get_user_from_token()
        
        if self.user and not isinstance(self.user, AnonymousUser):
            # Create user-specific group name
            self.user_group_name = f'user_notifications_{self.user.id}'
            
            # Join user notification group
            await self.channel_layer.group_add(
                self.user_group_name,
                self.channel_name
            )
            
            # Accept the WebSocket connection
            await self.accept()
            
            # Send connection confirmation
            await self.send(text_data=json.dumps({
                'type': 'connection_established',
                'message': 'Connected to notification channel',
                'user_id': self.user.id
            }))
        else:
            # Reject connection for unauthenticated users
            await self.close(code=4001)
    
    async def disconnect(self, close_code):
        """
        Handle WebSocket disconnection.
        Leave the user notification group.
        """
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """
        Handle messages received from WebSocket.
        Currently supports ping/pong for connection health checks.
        """
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': text_data_json.get('timestamp')
                }))
            elif message_type == 'mark_notification_read':
                # Handle marking notifications as read
                notification_id = text_data_json.get('notification_id')
                if notification_id:
                    await self.mark_notification_read(notification_id)
                    
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
    
    # Group message handlers for different notification types
    
    async def task_reminder(self, event):
        """
        Handle task reminder notifications.
        """
        await self.send(text_data=json.dumps({
            'type': 'task_reminder',
            'notification_id': event['notification_id'],
            'title': event['title'],
            'message': event['message'],
            'task_id': event.get('task_id'),
            'deadline': event.get('deadline'),
            'timestamp': event['timestamp']
        }))
    
    async def friend_activity(self, event):
        """
        Handle friend activity notifications.
        """
        await self.send(text_data=json.dumps({
            'type': 'friend_activity',
            'notification_id': event['notification_id'],
            'title': event['title'],
            'message': event['message'],
            'friend_id': event.get('friend_id'),
            'friend_name': event.get('friend_name'),
            'activity_type': event.get('activity_type'),
            'timestamp': event['timestamp']
        }))
    
    async def achievement_earned(self, event):
        """
        Handle achievement earned notifications.
        """
        await self.send(text_data=json.dumps({
            'type': 'achievement_earned',
            'notification_id': event['notification_id'],
            'title': event['title'],
            'message': event['message'],
            'achievement_id': event.get('achievement_id'),
            'achievement_name': event.get('achievement_name'),
            'points_earned': event.get('points_earned'),
            'timestamp': event['timestamp']
        }))
    
    async def friend_request(self, event):
        """
        Handle friend request notifications.
        """
        await self.send(text_data=json.dumps({
            'type': 'friend_request',
            'notification_id': event['notification_id'],
            'title': event['title'],
            'message': event['message'],
            'requester_id': event.get('requester_id'),
            'requester_name': event.get('requester_name'),
            'timestamp': event['timestamp']
        }))
    
    async def shared_task_invite(self, event):
        """
        Handle shared task invitation notifications.
        """
        await self.send(text_data=json.dumps({
            'type': 'shared_task_invite',
            'notification_id': event['notification_id'],
            'title': event['title'],
            'message': event['message'],
            'task_id': event.get('task_id'),
            'task_title': event.get('task_title'),
            'inviter_id': event.get('inviter_id'),
            'inviter_name': event.get('inviter_name'),
            'timestamp': event['timestamp']
        }))
    
    async def task_completed(self, event):
        """
        Handle task completion notifications.
        """
        await self.send(text_data=json.dumps({
            'type': 'task_completed',
            'notification_id': event['notification_id'],
            'title': event['title'],
            'message': event['message'],
            'task_id': event.get('task_id'),
            'task_title': event.get('task_title'),
            'user_id': event.get('user_id'),
            'user_name': event.get('user_name'),
            'points_earned': event.get('points_earned'),
            'timestamp': event['timestamp']
        }))
    
    async def general_notification(self, event):
        """
        Handle general notifications.
        """
        await self.send(text_data=json.dumps({
            'type': 'general_notification',
            'notification_id': event['notification_id'],
            'title': event['title'],
            'message': event['message'],
            'data': event.get('data', {}),
            'timestamp': event['timestamp']
        }))
    
    # Helper methods
    
    async def get_user_from_token(self):
        """
        Extract and validate user from JWT token in query parameters.
        """
        try:
            # Get token from query string
            query_string = self.scope.get('query_string', b'').decode()
            token = None
            
            for param in query_string.split('&'):
                if param.startswith('token='):
                    token = param.split('=', 1)[1]
                    break
            
            if not token:
                return AnonymousUser()
            
            # Validate JWT token
            access_token = AccessToken(token)
            user_id = access_token['user_id']
            
            # Get user from database
            user = await self.get_user_by_id(user_id)
            return user
            
        except (InvalidToken, TokenError, KeyError):
            return AnonymousUser()
        except Exception:
            return AnonymousUser()
    
    @database_sync_to_async
    def get_user_by_id(self, user_id):
        """
        Get user by ID from database.
        """
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return AnonymousUser()
    
    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """
        Mark a notification as read.
        """
        try:
            from .models import Notification
            notification = Notification.objects.get(
                id=notification_id,
                user=self.user
            )
            notification.is_read = True
            notification.save()
            return True
        except Notification.DoesNotExist:
            return False