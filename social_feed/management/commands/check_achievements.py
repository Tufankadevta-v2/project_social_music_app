"""
Management command to check and create activity feed entries for achievements
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from social_feed.utils import ActivityFeedManager
from task_management.achievements import check_user_achievements

User = get_user_model()


class Command(BaseCommand):
    help = 'Check user achievements and create activity feed entries'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='Check achievements for specific user ID'
        )
        parser.add_argument(
            '--all-users',
            action='store_true',
            help='Check achievements for all users'
        )

    def handle(self, *args, **options):
        user_id = options.get('user_id')
        all_users = options.get('all_users')
        
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                self.check_user_achievements(user)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'User with ID {user_id} not found')
                )
        elif all_users:
            users = User.objects.all()
            for user in users:
                self.check_user_achievements(user)
        else:
            self.stdout.write(
                self.style.ERROR('Please specify --user-id or --all-users')
            )
    
    def check_user_achievements(self, user):
        """Check achievements for a specific user"""
        try:
            achievements = check_user_achievements(user)
            
            for achievement in achievements:
                # Create activity feed entry for each achievement
                ActivityFeedManager.create_achievement_activity(
                    user=user,
                    achievement_name=achievement['name'],
                    achievement_description=achievement['description'],
                    points_earned=achievement.get('points_reward', 0)
                )
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Created activity for {user.phone_number}: {achievement["name"]}'
                    )
                )
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f'Error checking achievements for {user.phone_number}: {str(e)}'
                )
            )