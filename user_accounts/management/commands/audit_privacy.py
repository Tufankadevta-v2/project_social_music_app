from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from user_accounts.privacy_models import PrivacySettings, FriendPrivacySettings, PrivateTask
from task_management.models import Task
from social_feed.models import ActivityFeed
from friendships.models import Friendship

User = get_user_model()


class Command(BaseCommand):
    help = 'Audit and fix privacy settings across the application'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Fix privacy issues found during audit',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='Audit privacy settings for a specific user',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output',
        )
    
    def handle(self, *args, **options):
        self.fix_issues = options['fix']
        self.verbose = options['verbose']
        user_id = options.get('user_id')
        
        self.stdout.write(
            self.style.SUCCESS('Starting privacy audit...')
        )
        
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                users = [user]
                self.stdout.write(f'Auditing privacy for user: {user.phone_number}')
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'User with ID {user_id} not found')
                )
                return
        else:
            users = User.objects.all()
            self.stdout.write(f'Auditing privacy for {users.count()} users')
        
        issues_found = 0
        issues_fixed = 0
        
        for user in users:
            user_issues = self.audit_user_privacy(user)
            issues_found += len(user_issues)
            
            if self.fix_issues:
                fixed = self.fix_user_privacy_issues(user, user_issues)
                issues_fixed += fixed
        
        # Audit system-wide privacy issues
        system_issues = self.audit_system_privacy()
        issues_found += len(system_issues)
        
        if self.fix_issues:
            fixed = self.fix_system_privacy_issues(system_issues)
            issues_fixed += fixed
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Privacy audit complete. Found {issues_found} issues.'
            )
        )
        
        if self.fix_issues:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Fixed {issues_fixed} privacy issues.'
                )
            )
    
    def audit_user_privacy(self, user):
        """Audit privacy settings for a specific user"""
        issues = []
        
        # Check if user has privacy settings
        try:
            privacy_settings = user.privacy_settings
        except PrivacySettings.DoesNotExist:
            issues.append({
                'type': 'missing_privacy_settings',
                'user': user,
                'description': 'User missing privacy settings'
            })
            return issues
        
        # Check for inconsistent privacy settings
        if privacy_settings.profile_visibility == 'private':
            if privacy_settings.task_visibility == 'public':
                issues.append({
                    'type': 'inconsistent_privacy',
                    'user': user,
                    'description': 'Profile is private but tasks are public'
                })
            
            if privacy_settings.achievement_visibility == 'public':
                issues.append({
                    'type': 'inconsistent_privacy',
                    'user': user,
                    'description': 'Profile is private but achievements are public'
                })
        
        # Check for tasks that should be private
        sensitive_tasks = Task.objects.filter(
            user=user,
            title__icontains='personal'
        ).exclude(
            id__in=PrivateTask.objects.filter(task__user=user).values_list('task_id', flat=True)
        )
        
        for task in sensitive_tasks:
            issues.append({
                'type': 'potentially_private_task',
                'user': user,
                'task': task,
                'description': f'Task "{task.title}" might need privacy settings'
            })
        
        # Check for orphaned friend privacy settings
        friend_settings = FriendPrivacySettings.objects.filter(user=user)
        for setting in friend_settings:
            if not Friendship.are_friends(user, setting.friend):
                issues.append({
                    'type': 'orphaned_friend_settings',
                    'user': user,
                    'friend': setting.friend,
                    'description': 'Friend privacy settings exist but users are not friends'
                })
        
        # Check for public activities when user has private settings
        if privacy_settings.activity_feed_visibility == 'none':
            public_activities = ActivityFeed.objects.filter(
                user=user,
                is_public=True
            )
            if public_activities.exists():
                issues.append({
                    'type': 'public_activities_private_user',
                    'user': user,
                    'count': public_activities.count(),
                    'description': 'User has public activities but activity feed is set to none'
                })
        
        if self.verbose and issues:
            self.stdout.write(f'  Found {len(issues)} issues for {user.phone_number}')
        
        return issues
    
    def audit_system_privacy(self):
        """Audit system-wide privacy issues"""
        issues = []
        
        # Check for users without privacy settings
        users_without_settings = User.objects.filter(
            privacy_settings__isnull=True
        )
        
        for user in users_without_settings:
            issues.append({
                'type': 'missing_privacy_settings',
                'user': user,
                'description': 'User missing privacy settings'
            })
        
        # Check for private tasks without PrivateTask settings
        private_tasks = Task.objects.filter(is_private=True).exclude(
            id__in=PrivateTask.objects.values_list('task_id', flat=True)
        )
        
        for task in private_tasks:
            issues.append({
                'type': 'private_task_missing_settings',
                'task': task,
                'description': f'Task "{task.title}" is marked private but has no PrivateTask settings'
            })
        
        return issues
    
    def fix_user_privacy_issues(self, user, issues):
        """Fix privacy issues for a specific user"""
        fixed_count = 0
        
        with transaction.atomic():
            for issue in issues:
                if issue['type'] == 'missing_privacy_settings':
                    PrivacySettings.get_or_create_for_user(user)
                    fixed_count += 1
                    if self.verbose:
                        self.stdout.write(f'  Created privacy settings for {user.phone_number}')
                
                elif issue['type'] == 'inconsistent_privacy':
                    privacy_settings = user.privacy_settings
                    if 'tasks are public' in issue['description']:
                        privacy_settings.task_visibility = 'private'
                        privacy_settings.save()
                        fixed_count += 1
                        if self.verbose:
                            self.stdout.write(f'  Fixed task visibility for {user.phone_number}')
                    
                    elif 'achievements are public' in issue['description']:
                        privacy_settings.achievement_visibility = 'private'
                        privacy_settings.save()
                        fixed_count += 1
                        if self.verbose:
                            self.stdout.write(f'  Fixed achievement visibility for {user.phone_number}')
                
                elif issue['type'] == 'potentially_private_task':
                    # Don't auto-fix this, just report
                    if self.verbose:
                        self.stdout.write(f'  Flagged potentially private task: {issue["task"].title}')
                
                elif issue['type'] == 'orphaned_friend_settings':
                    FriendPrivacySettings.objects.filter(
                        user=user,
                        friend=issue['friend']
                    ).delete()
                    fixed_count += 1
                    if self.verbose:
                        self.stdout.write(f'  Removed orphaned friend settings for {user.phone_number}')
                
                elif issue['type'] == 'public_activities_private_user':
                    ActivityFeed.objects.filter(
                        user=user,
                        is_public=True
                    ).update(is_public=False)
                    fixed_count += 1
                    if self.verbose:
                        self.stdout.write(f'  Made activities private for {user.phone_number}')
        
        return fixed_count
    
    def fix_system_privacy_issues(self, issues):
        """Fix system-wide privacy issues"""
        fixed_count = 0
        
        with transaction.atomic():
            for issue in issues:
                if issue['type'] == 'missing_privacy_settings':
                    PrivacySettings.get_or_create_for_user(issue['user'])
                    fixed_count += 1
                    if self.verbose:
                        self.stdout.write(f'  Created privacy settings for {issue["user"].phone_number}')
                
                elif issue['type'] == 'private_task_missing_settings':
                    PrivateTask.objects.get_or_create(
                        task=issue['task'],
                        defaults={
                            'is_completely_private': True,
                            'hide_from_activity_feed': True,
                            'hide_from_leaderboards': True
                        }
                    )
                    fixed_count += 1
                    if self.verbose:
                        self.stdout.write(f'  Created PrivateTask settings for task: {issue["task"].title}')
        
        return fixed_count