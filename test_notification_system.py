#!/usr/bin/env python3
"""
Test script to demonstrate the real-time notification system.
"""
import os
import django
import asyncio
import websockets
import json
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'social_task_backend.settings')
django.setup()

from user_accounts.models import User
from notifications.services import NotificationService
from rest_framework_simplejwt.tokens import AccessToken


def create_test_user():
    """Create a test user for demonstration."""
    try:
        user = User.objects.get(username='demo_user')
    except User.DoesNotExist:
        # Find a unique phone number
        phone_number = '+1234567999'
        counter = 0
        while User.objects.filter(phone_number=phone_number).exists():
            counter += 1
            phone_number = f'+123456799{counter}'
        
        user = User.objects.create_user(
            username='demo_user',
            phone_number=phone_number,
            password='demo123',
            is_phone_verified=True
        )
    return user


def test_notification_creation():
    """Test creating different types of notifications."""
    print("🔔 Testing Notification System")
    print("=" * 50)
    
    user = create_test_user()
    print(f"✅ Created/found test user: {user.username}")
    
    # Test 1: Basic notification
    notification1 = NotificationService.create_notification(
        user=user,
        notification_type='general',
        title='Welcome!',
        message='Welcome to the social task management app!',
        data={'welcome': True},
        send_realtime=False
    )
    print(f"✅ Created general notification: {notification1.title}")
    
    # Test 2: Task reminder
    notification2 = NotificationService.create_task_reminder(
        user=user,
        task_id=123,
        task_title='Complete project documentation',
        deadline='2024-01-15T18:00:00Z'
    )
    print(f"✅ Created task reminder: {notification2.title}")
    
    # Test 3: Achievement notification
    notification3 = NotificationService.create_achievement_notification(
        user=user,
        achievement_id=1,
        achievement_name='First Task Completed',
        points_earned=100
    )
    print(f"✅ Created achievement notification: {notification3.title}")
    
    # Check unread count
    unread_count = NotificationService.get_unread_count(user)
    print(f"📊 Unread notifications: {unread_count}")
    
    # Mark some as read
    marked_count = NotificationService.mark_notifications_read(user, [notification1.id])
    print(f"✅ Marked {marked_count} notification as read")
    
    # Check unread count again
    unread_count = NotificationService.get_unread_count(user)
    print(f"📊 Unread notifications after marking one as read: {unread_count}")
    
    return user


async def test_websocket_connection():
    """Test WebSocket connection and real-time notifications."""
    print("\n🌐 Testing WebSocket Connection")
    print("=" * 50)
    
    user = create_test_user()
    
    # Generate JWT token for WebSocket authentication
    access_token = AccessToken.for_user(user)
    token = str(access_token)
    
    try:
        # Connect to WebSocket
        uri = f"ws://localhost:8000/ws/notifications/?token={token}"
        print(f"🔗 Connecting to: {uri}")
        
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket connected successfully!")
            
            # Wait for connection confirmation
            response = await websocket.recv()
            data = json.loads(response)
            print(f"📨 Received: {data}")
            
            # Send a ping
            ping_data = {
                'type': 'ping',
                'timestamp': datetime.now().isoformat()
            }
            await websocket.send(json.dumps(ping_data))
            print("📤 Sent ping")
            
            # Wait for pong
            response = await websocket.recv()
            data = json.loads(response)
            print(f"📨 Received pong: {data}")
            
            print("✅ WebSocket test completed successfully!")
            
    except Exception as e:
        print(f"❌ WebSocket connection failed: {e}")
        print("💡 Make sure the Django server is running with: python3 manage.py runserver")


def main():
    """Main test function."""
    print("🚀 Social Task Management - Notification System Test")
    print("=" * 60)
    
    # Test notification creation
    user = test_notification_creation()
    
    # Test WebSocket (requires server to be running)
    print("\n⚠️  WebSocket test requires Django server to be running")
    print("   Run: python3 manage.py runserver")
    print("   Then run this script again to test WebSocket functionality")
    
    # Show final stats
    print(f"\n📈 Final Statistics for {user.username}:")
    print(f"   Total notifications: {user.notifications.count()}")
    print(f"   Unread notifications: {NotificationService.get_unread_count(user)}")
    
    print("\n✨ Notification system test completed!")


if __name__ == '__main__':
    main()