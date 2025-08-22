"""
Achievement system for competitive shared tasks
This module defines achievements that can be unlocked based on competitive performance
"""
from typing import List, Dict, Any
from django.contrib.auth import get_user_model
from .models import TaskParticipation, SharedTask

User = get_user_model()


class Achievement:
    """Base achievement class"""
    
    def __init__(self, id: str, name: str, description: str, icon: str, points_reward: int = 0):
        self.id = id
        self.name = name
        self.description = description
        self.icon = icon
        self.points_reward = points_reward
    
    def check_unlocked(self, user: User) -> bool:
        """Check if user has unlocked this achievement"""
        raise NotImplementedError
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert achievement to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'icon': self.icon,
            'points_reward': self.points_reward
        }


class FirstWinAchievement(Achievement):
    """Achievement for first competitive win"""
    
    def __init__(self):
        super().__init__(
            id='first_win',
            name='First Victory',
            description='Win your first competitive shared task',
            icon='trophy',
            points_reward=50
        )
    
    def check_unlocked(self, user: User) -> bool:
        # Check if user has any first place finishes
        participations = TaskParticipation.objects.filter(
            user=user,
            shared_task__is_competitive=True,
            status='completed'
        )
        
        for participation in participations:
            if participation.completion_rank == 1:
                return True
        
        return False


class WinStreakAchievement(Achievement):
    """Achievement for winning multiple tasks in a row"""
    
    def __init__(self, streak_length: int):
        self.streak_length = streak_length
        super().__init__(
            id=f'win_streak_{streak_length}',
            name=f'{streak_length}-Win Streak',
            description=f'Win {streak_length} competitive tasks in a row',
            icon='fire',
            points_reward=streak_length * 25
        )
    
    def check_unlocked(self, user: User) -> bool:
        # Get user's completed competitive participations ordered by completion time
        participations = TaskParticipation.objects.filter(
            user=user,
            shared_task__is_competitive=True,
            status='completed'
        ).order_by('-completed_at')
        
        current_streak = 0
        for participation in participations:
            if participation.completion_rank == 1:
                current_streak += 1
                if current_streak >= self.streak_length:
                    return True
            else:
                break  # Streak broken
        
        return False


class SpeedDemonAchievement(Achievement):
    """Achievement for completing tasks very quickly"""
    
    def __init__(self):
        super().__init__(
            id='speed_demon',
            name='Speed Demon',
            description='Complete 10 competitive tasks within 1 hour of creation',
            icon='lightning',
            points_reward=100
        )
    
    def check_unlocked(self, user: User) -> bool:
        from django.utils import timezone
        
        quick_completions = 0
        participations = TaskParticipation.objects.filter(
            user=user,
            shared_task__is_competitive=True,
            status='completed'
        ).select_related('shared_task__task')
        
        for participation in participations:
            task_created = participation.shared_task.task.created_at
            completed_at = participation.completed_at
            
            if completed_at and (completed_at - task_created).total_seconds() <= 3600:  # 1 hour
                quick_completions += 1
                if quick_completions >= 10:
                    return True
        
        return False


class ConsistentPerformerAchievement(Achievement):
    """Achievement for consistent top-3 finishes"""
    
    def __init__(self):
        super().__init__(
            id='consistent_performer',
            name='Consistent Performer',
            description='Finish in top 3 in 20 competitive tasks',
            icon='medal',
            points_reward=150
        )
    
    def check_unlocked(self, user: User) -> bool:
        # Count top 3 finishes manually
        participations = TaskParticipation.objects.filter(
            user=user,
            shared_task__is_competitive=True,
            status='completed'
        )
        
        top_3_finishes = 0
        for participation in participations:
            if participation.completion_rank and participation.completion_rank <= 3:
                top_3_finishes += 1
        
        return top_3_finishes >= 20


class PointMasterAchievement(Achievement):
    """Achievement for earning high points in competitive tasks"""
    
    def __init__(self, points_threshold: int):
        self.points_threshold = points_threshold
        super().__init__(
            id=f'point_master_{points_threshold}',
            name=f'Point Master ({points_threshold})',
            description=f'Earn {points_threshold} total points from competitive tasks',
            icon='star',
            points_reward=points_threshold // 10
        )
    
    def check_unlocked(self, user: User) -> bool:
        from django.db.models import Sum
        
        total_points = TaskParticipation.objects.filter(
            user=user,
            shared_task__is_competitive=True,
            status='completed'
        ).aggregate(total_points=Sum('points_earned'))['total_points'] or 0
        
        return total_points >= self.points_threshold


class TeamPlayerAchievement(Achievement):
    """Achievement for participating in many shared tasks"""
    
    def __init__(self):
        super().__init__(
            id='team_player',
            name='Team Player',
            description='Participate in 50 shared tasks',
            icon='users',
            points_reward=200
        )
    
    def check_unlocked(self, user: User) -> bool:
        participation_count = TaskParticipation.objects.filter(
            user=user
        ).count()
        
        return participation_count >= 50


# Define all available achievements
AVAILABLE_ACHIEVEMENTS = [
    FirstWinAchievement(),
    WinStreakAchievement(3),
    WinStreakAchievement(5),
    WinStreakAchievement(10),
    SpeedDemonAchievement(),
    ConsistentPerformerAchievement(),
    PointMasterAchievement(1000),
    PointMasterAchievement(5000),
    PointMasterAchievement(10000),
    TeamPlayerAchievement(),
]


def check_user_achievements(user: User) -> List[Dict[str, Any]]:
    """
    Check which achievements a user has unlocked
    
    Args:
        user: User instance
        
    Returns:
        List of unlocked achievement dictionaries
    """
    unlocked_achievements = []
    
    for achievement in AVAILABLE_ACHIEVEMENTS:
        if achievement.check_unlocked(user):
            achievement_data = achievement.to_dict()
            achievement_data['unlocked'] = True
            unlocked_achievements.append(achievement_data)
    
    return unlocked_achievements


def get_all_achievements() -> List[Dict[str, Any]]:
    """
    Get all available achievements
    
    Returns:
        List of all achievement dictionaries
    """
    return [achievement.to_dict() for achievement in AVAILABLE_ACHIEVEMENTS]


def check_new_achievements(user: User, previous_achievements: List[str]) -> List[Dict[str, Any]]:
    """
    Check for newly unlocked achievements
    
    Args:
        user: User instance
        previous_achievements: List of previously unlocked achievement IDs
        
    Returns:
        List of newly unlocked achievement dictionaries
    """
    current_achievements = check_user_achievements(user)
    current_achievement_ids = {ach['id'] for ach in current_achievements}
    previous_achievement_ids = set(previous_achievements)
    
    new_achievement_ids = current_achievement_ids - previous_achievement_ids
    
    return [
        ach for ach in current_achievements 
        if ach['id'] in new_achievement_ids
    ]