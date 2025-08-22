from django.core.management.base import BaseCommand
from django.utils import timezone
from task_management.models import Task


class Command(BaseCommand):
    help = 'Update overdue status for all pending tasks with past deadlines'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Find all pending tasks with past deadlines
        now = timezone.now()
        overdue_tasks = Task.objects.filter(
            status='pending',
            deadline__lt=now
        )
        
        count = overdue_tasks.count()
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'DRY RUN: Would update {count} tasks to overdue status')
            )
            for task in overdue_tasks[:10]:  # Show first 10 as examples
                self.stdout.write(f'  - Task {task.id}: "{task.title}" (deadline: {task.deadline})')
            if count > 10:
                self.stdout.write(f'  ... and {count - 10} more tasks')
        else:
            # Update tasks to overdue status
            updated_count = overdue_tasks.update(status='overdue')
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully updated {updated_count} tasks to overdue status')
            )
            
            if updated_count > 0:
                self.stdout.write('Updated tasks:')
                for task in Task.objects.filter(status='overdue', deadline__lt=now)[:10]:
                    self.stdout.write(f'  - Task {task.id}: "{task.title}"')