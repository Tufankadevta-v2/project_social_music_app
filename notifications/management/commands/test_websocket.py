"""
Management command to test WebSocket notification functionality.
"""
from django.core.management.base import BaseCommand
from notifications.utils import notification_sender
from user_accounts.models import User


class Command(BaseCommand):
    help = 'Test WebSocket notification functionality'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='User ID to send test notification to',
        )
        parser.add_argument(
            '--notification-type',
            type=str,
            default='general_notification',
            help='Type of notification to send',
        )
    
    def handle(self, *args, **options):
        user_id = options.get('user_id')
        notification_type = options.get('notification_type')
        
        if not user_id:
            # Get first user if no user ID provided
            try:
                user = User.objects.first()
                if not user:
                    self.stdout.write(
                        self.style.ERROR('No users found in database')
                    )
                    return
                user_id = user.id
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error getting user: {e}')
                )
                return
        
        # Test notification data
        test_data = {
            'notification_id': 999,
            'title': 'Test Notification',
            'message': 'This is a test WebSocket notification',
            'data': {'test': True}
        }
        
        # Send test notification
        success = notification_sender.send_to_user(
            user_id, 
            notification_type, 
            test_data
        )
        
        if success:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully sent {notification_type} to user {user_id}'
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    f'Failed to send notification to user {user_id}'
                )
            )