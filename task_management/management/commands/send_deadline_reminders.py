"""
Management command to send deadline reminders for shared tasks
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from task_management.models import SharedTask, TaskParticipation
from task_management.notifications import prepare_shared_task_reminder_notification, send_notifications


class Command(BaseCommand):
    help = 'Send deadline reminders for shared tasks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Send reminders for tasks due within this many hours (default: 24)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually sending notifications'
        )

    def handle(self, *args, **options):
        hours = options['hours']
        dry_run = options['dry_run']
        
        # Calculate the time threshold
        now = timezone.now()
        threshold = now + timedelta(hours=hours)
        
        # Find shared tasks with deadlines approaching
        shared_tasks_with_deadlines = SharedTask.objects.filter(
            task__deadline__isnull=False,
            task__deadline__gte=now,  # Not overdue yet
            task__deadline__lte=threshold,  # Due within threshold
            task__status='pending'  # Still pending
        ).select_related('task', 'creator')
        
        total_notifications = 0
        
        for shared_task in shared_tasks_with_deadlines:
            # Calculate hours until deadline
            time_until_deadline = shared_task.task.deadline - now
            hours_until_deadline = int(time_until_deadline.total_seconds() / 3600)
            
            # Skip if already overdue (shouldn't happen due to filter, but safety check)
            if hours_until_deadline < 0:
                continue
            
            # Prepare reminder notifications
            notification_data = prepare_shared_task_reminder_notification(
                shared_task, 
                hours_until_deadline
            )
            
            if notification_data:
                if dry_run:
                    self.stdout.write(
                        f'DRY RUN: Would send {len(notification_data)} reminders for '
                        f'"{shared_task.task.title}" (due in {hours_until_deadline}h)'
                    )
                else:
                    send_notifications(notification_data)
                    self.stdout.write(
                        f'Sent {len(notification_data)} reminders for '
                        f'"{shared_task.task.title}" (due in {hours_until_deadline}h)'
                    )
                
                total_notifications += len(notification_data)
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN: Would send {total_notifications} deadline reminder notifications'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully sent {total_notifications} deadline reminder notifications'
                )
            )