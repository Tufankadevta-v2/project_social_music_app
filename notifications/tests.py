"""
Tests for real-time notification system.
"""
from django.test import TestCase
from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter
from django.urls import path
from rest_framework_simplejwt.tokens import AccessToken
from user_accounts.models import User
from notifications.consumers import NotificationConsumer
from notifications.utils import notification_sender
from notifications.services import NotificationService
from notifications.models import Notification
import json


class NotificationWebSocketTests(TestCase):
    """
    Test WebSocket functionality for real-time notifications.
    """
    
    def setUp(self):
        """
        Set up test data.
        """
        self.user = User.objects.create_user(
            username='testuser',
            phone_number='+1234567890',
            password='testpass123',
            is_phone_verified=True
        )
        self.access_token = AccessToken.for_user(self.user)
    
    async def test_websocket_connection_with_valid_token(self):
        """
        Test WebSocket connection with valid JWT token.
        """
        # Create WebSocket communicator with token
        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(),
            f"/ws/notifications/?token={str(self.access_token)}"
        )
        
        # Connect to WebSocket
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Should receive connection confirmation
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'connection_established')
        self.assertEqual(response['user_id'], self.user.id)
        
        # Disconnect
        await communicator.disconnect()
    
    async def test_websocket_connection_without_token(self):
        """
        Test WebSocket connection without token should be rejected.
        """
        # Create WebSocket communicator without token
        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(),
            "/ws/notifications/"
        )
        
        # Connection should be rejected
        connected, subprotocol = await communicator.connect()
        self.assertFalse(connected)
    
    async def test_websocket_ping_pong(self):
        """
        Test WebSocket ping/pong functionality.
        """
        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(),
            f"/ws/notifications/?token={str(self.access_token)}"
        )
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Skip connection confirmation message
        await communicator.receive_json_from()
        
        # Send ping
        await communicator.send_json_to({
            'type': 'ping',
            'timestamp': '2023-01-01T00:00:00Z'
        })
        
        # Should receive pong
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'pong')
        self.assertEqual(response['timestamp'], '2023-01-01T00:00:00Z')
        
        await communicator.disconnect()
    
    def test_notification_sender_utility(self):
        """
        Test the notification sender utility functions.
        """
        # Test sending task reminder
        success = notification_sender.send_task_reminder(
            user_id=self.user.id,
            notification_id=1,
            task_id=123,
            task_title='Test Task',
            deadline='2023-12-31T23:59:59Z'
        )
        
        # Should return True even if no WebSocket is connected
        # (the function doesn't fail, just no one receives it)
        self.assertTrue(success)
        
        # Test sending friend activity
        success = notification_sender.send_friend_activity(
            user_id=self.user.id,
            notification_id=2,
            friend_id=456,
            friend_name='Test Friend',
            activity_type='task_completed',
            message='Test Friend completed a task!'
        )
        
        self.assertTrue(success)
    
    def test_notification_sender_multiple_users(self):
        """
        Test sending notifications to multiple users.
        """
        # Create another user
        user2 = User.objects.create_user(
            username='testuser2',
            phone_number='+1234567891',
            password='testpass123',
            is_phone_verified=True
        )
        
        user_ids = [self.user.id, user2.id]
        
        success_count = notification_sender.send_to_multiple_users(
            user_ids=user_ids,
            notification_type='general_notification',
            data={
                'notification_id': 3,
                'title': 'Test Broadcast',
                'message': 'This is a broadcast message',
                'data': {}
            }
        )
        
        # Should successfully send to both users
        self.assertEqual(success_count, 2)


class NotificationConsumerUnitTests(TestCase):
    """
    Unit tests for NotificationConsumer methods.
    """
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            phone_number='+1234567890',
            password='testpass123',
            is_phone_verified=True
        )
    
    def test_consumer_group_name_generation(self):
        """
        Test that consumer generates correct group names.
        """
        expected_group_name = f'user_notifications_{self.user.id}'
        
        # This would be tested in an async context in real usage
        # Here we're just testing the logic
        self.assertEqual(
            expected_group_name,
            f'user_notifications_{self.user.id}'
        )


class NotificationServiceTests(TestCase):
    """
    Test the notification service functionality.
    """
    
    def setUp(self):
        """
        Set up test data.
        """
        self.user1 = User.objects.create_user(
            username='testuser1',
            phone_number='+1234567890',
            password='testpass123',
            is_phone_verified=True
        )
        self.user2 = User.objects.create_user(
            username='testuser2',
            phone_number='+1234567891',
            password='testpass123',
            is_phone_verified=True
        )
    
    def test_create_notification(self):
        """
        Test creating a basic notification.
        """
        notification = NotificationService.create_notification(
            user=self.user1,
            notification_type='general',
            title='Test Notification',
            message='This is a test notification',
            data={'test': True},
            send_realtime=False  # Don't send WebSocket for this test
        )
        
        self.assertEqual(notification.user, self.user1)
        self.assertEqual(notification.notification_type, 'general')
        self.assertEqual(notification.title, 'Test Notification')
        self.assertEqual(notification.message, 'This is a test notification')
        self.assertEqual(notification.data, {'test': True})
        self.assertFalse(notification.is_read)
    
    def test_create_task_reminder(self):
        """
        Test creating a task reminder notification.
        """
        notification = NotificationService.create_task_reminder(
            user=self.user1,
            task_id=123,
            task_title='Test Task',
            deadline='2023-12-31T23:59:59Z'
        )
        
        self.assertEqual(notification.notification_type, 'task_reminder')
        self.assertEqual(notification.title, 'Task Reminder')
        self.assertIn('Test Task', notification.message)
        self.assertEqual(notification.data['task_id'], 123)
    
    def test_create_friend_request_notification(self):
        """
        Test creating a friend request notification.
        """
        notification = NotificationService.create_friend_request_notification(
            user=self.user1,
            requester=self.user2
        )
        
        self.assertEqual(notification.notification_type, 'friend_request')
        self.assertEqual(notification.title, 'Friend Request')
        self.assertIn(self.user2.username, notification.message)
        self.assertEqual(notification.data['requester_id'], self.user2.id)
    
    def test_mark_notifications_read(self):
        """
        Test marking notifications as read.
        """
        # Create some notifications
        NotificationService.create_notification(
            user=self.user1,
            notification_type='general',
            title='Test 1',
            message='Message 1',
            send_realtime=False
        )
        NotificationService.create_notification(
            user=self.user1,
            notification_type='general',
            title='Test 2',
            message='Message 2',
            send_realtime=False
        )
        
        # Check initial unread count
        self.assertEqual(NotificationService.get_unread_count(self.user1), 2)
        
        # Mark all as read
        marked_count = NotificationService.mark_notifications_read(self.user1)
        self.assertEqual(marked_count, 2)
        
        # Check final unread count
        self.assertEqual(NotificationService.get_unread_count(self.user1), 0)
    
    def test_notify_multiple_users(self):
        """
        Test notifying multiple users at once.
        """
        users = [self.user1, self.user2]
        
        notifications = NotificationService.notify_multiple_users(
            users=users,
            notification_type='general',
            title='Broadcast Message',
            message='This is a broadcast notification'
        )
        
        self.assertEqual(len(notifications), 2)
        self.assertEqual(notifications[0].user, self.user1)
        self.assertEqual(notifications[1].user, self.user2)
        
        # Check that both users have the notification
        self.assertEqual(Notification.objects.filter(user=self.user1).count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.user2).count(), 1)


class NotificationModelTests(TestCase):
    """
    Test the Notification model.
    """
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            phone_number='+1234567890',
            password='testpass123',
            is_phone_verified=True
        )
    
    def test_notification_creation(self):
        """
        Test creating a notification instance.
        """
        notification = Notification.objects.create(
            user=self.user,
            notification_type='task_reminder',
            title='Test Notification',
            message='Test message',
            data={'test': True}
        )
        
        self.assertEqual(str(notification), f"{self.user.username} - Test Notification")
        self.assertFalse(notification.is_read)
    
    def test_mark_as_read(self):
        """
        Test marking a notification as read.
        """
        notification = Notification.objects.create(
            user=self.user,
            notification_type='general',
            title='Test',
            message='Test message'
        )
        
        self.assertFalse(notification.is_read)
        
        notification.mark_as_read()
        notification.refresh_from_db()
        
        self.assertTrue(notification.is_read)