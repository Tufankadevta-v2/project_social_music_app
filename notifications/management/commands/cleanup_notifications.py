"""
Management command to clean up old notifications.
"""
from django.core.management.base import BaseCommand
from notifications.services import NotificationService


class Command(BaseCommand):
    help = 'Clean up old read notifications'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to keep notifications (default: 30)',
        )
    
    def handle(self, *args, **options):
        days = options['days']
        
        deleted_count = NotificationService.cleanup_old_notifications(days)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully deleted {deleted_count} old notifications '
                f'(older than {days} days)'
            )
        )