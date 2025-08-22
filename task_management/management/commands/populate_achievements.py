"""
Management command to populate the database with achievement definitions
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from task_management.models import Achievement
from task_management.achievements import AVAILABLE_ACHIEVEMENTS


class Command(BaseCommand):
    help = 'Populate the database with achievement definitions'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update existing achievements',
        )
    
    def handle(self, *args, **options):
        force_update = options['force']
        
        with transaction.atomic():
            created_count = 0
            updated_count = 0
            
            for achievement_def in AVAILABLE_ACHIEVEMENTS:
                achievement_data = {
                    'name': achievement_def.name,
                    'description': achievement_def.description,
                    'icon': achievement_def.icon,
                    'points_reward': achievement_def.points_reward,
                    'category': self._get_category_from_achievement(achievement_def),
                    'rarity': self._get_rarity_from_achievement(achievement_def),
                    'requirements_data': self._get_requirements_data(achievement_def),
                }
                
                achievement, created = Achievement.objects.update_or_create(
                    achievement_id=achievement_def.id,
                    defaults=achievement_data
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'Created achievement: {achievement.name}')
                    )
                elif force_update:
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'Updated achievement: {achievement.name}')
                    )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully processed achievements: {created_count} created, {updated_count} updated'
                )
            )
    
    def _get_category_from_achievement(self, achievement_def):
        """Determine category based on achievement type"""
        achievement_id = achievement_def.id
        
        if 'win' in achievement_id or 'first' in achievement_id:
            return 'competitive'
        elif 'streak' in achievement_id:
            return 'consistency'
        elif 'speed' in achievement_id:
            return 'speed'
        elif 'point' in achievement_id:
            return 'points'
        elif 'team' in achievement_id:
            return 'participation'
        elif 'consistent' in achievement_id:
            return 'consistency'
        else:
            return 'milestone'
    
    def _get_rarity_from_achievement(self, achievement_def):
        """Determine rarity based on achievement requirements"""
        points_reward = achievement_def.points_reward
        
        if points_reward >= 200:
            return 'legendary'
        elif points_reward >= 150:
            return 'epic'
        elif points_reward >= 100:
            return 'rare'
        elif points_reward >= 50:
            return 'uncommon'
        else:
            return 'common'
    
    def _get_requirements_data(self, achievement_def):
        """Extract requirements data from achievement definition"""
        requirements = {}
        
        # Extract specific requirements based on achievement type
        if hasattr(achievement_def, 'streak_length'):
            requirements['streak_length'] = achievement_def.streak_length
        
        if hasattr(achievement_def, 'points_threshold'):
            requirements['points_threshold'] = achievement_def.points_threshold
        
        # Add general requirements based on achievement ID
        achievement_id = achievement_def.id
        
        if achievement_id == 'speed_demon':
            requirements['task_count'] = 10
            requirements['time_limit_hours'] = 1
        elif achievement_id == 'consistent_performer':
            requirements['top_finishes'] = 20
            requirements['rank_threshold'] = 3
        elif achievement_id == 'team_player':
            requirements['participation_count'] = 50
        
        return requirements