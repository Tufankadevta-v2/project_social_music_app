"""
Management command to clean up old activity feed entries
"""
from django.core.management.base import BaseCommand
from social_feed.utils import cleanup_old_activities


class Command(BaseCommand):
    help = 'Clean up old activity feed entries and expired cache'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Number of days to keep activities (default: 90)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )

    def handle(self, *args, **options):
        days_to_keep = options['days']
        dry_run = options['dry_run']
        
        if dry_run:
            from django.utils import timezone
            from social_feed.models import ActivityFeed, ActivityFeedCache
            
            cutoff_date = timezone.now() - timezone.timedelta(days=days_to_keep)
            
            activities_count = ActivityFeed.objects.filter(
                created_at__lt=cutoff_date
            ).count()
            
            expired_cache_count = ActivityFeedCache.objects.filter(
                expires_at__lt=timezone.now()
            ).count()
            
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN: Would delete {activities_count} activities older than {days_to_keep} days'
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN: Would delete {expired_cache_count} expired cache entries'
                )
            )
        else:
            result = cleanup_old_activities(days_to_keep)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully deleted {result["activities_deleted"]} old activities'
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully deleted {result["cache_entries_deleted"]} expired cache entries'
                )
            )