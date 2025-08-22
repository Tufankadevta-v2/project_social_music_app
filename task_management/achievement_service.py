"""
Achievement service for managing user achievements and progress tracking
"""
from typing import List, Dict, Any, Optional
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from .models import Achievement, UserAchievement, AchievementProgress
from .achievements import AVAILABLE_ACHIEVEMENTS, check_user_achievements

User = get_user_model()


class AchievementService:
    """Service class for managing achievements and user progress"""
    
    @staticmethod
    def check_and_unlock_achievements(user: User) -> List[UserAchievement]:
        """
        Check for newly unlocked achievements and create UserAchievement records
        
        Args:
            user: User instance to check achievements for
            
        Returns:
            List of newly unlocked UserAchievement instances
        """
        # Get previously unlocked achievement IDs
        existing_achievements = set(
            UserAchievement.objects.filter(user=user)
            .values_list('achievement__achievement_id', flat=True)
        )
        
        # Check current achievements using the existing logic
        current_achievements = check_user_achievements(user)
        current_achievement_ids = {ach['id'] for ach in current_achievements}
        
        # Find newly unlocked achievements
        new_achievement_ids = current_achievement_ids - existing_achievements
        
        newly_unlocked = []
        
        with transaction.atomic():
            for achievement_id in new_achievement_ids:
                try:
                    achievement = Achievement.objects.get(
                        achievement_id=achievement_id,
                        is_active=True
                    )
                    
                    user_achievement = UserAchievement.objects.create(
                        user=user,
                        achievement=achievement,
                        points_awarded=achievement.points_reward
                    )
                    
                    # Award points to user
                    user.total_points += achievement.points_reward
                    user.save(update_fields=['total_points'])
                    
                    newly_unlocked.append(user_achievement)
                    
                except Achievement.DoesNotExist:
                    # Achievement not in database yet, skip
                    continue
        
        return newly_unlocked
    
    @staticmethod
    def get_user_achievements(user: User, include_progress: bool = False) -> Dict[str, Any]:
        """
        Get user's achievements and optionally progress towards unearned achievements
        
        Args:
            user: User instance
            include_progress: Whether to include progress towards unearned achievements
            
        Returns:
            Dictionary containing user achievements and progress data
        """
        # Get unlocked achievements
        unlocked_achievements = UserAchievement.objects.filter(user=user).select_related('achievement')
        unlocked_data = [ua.to_dict() for ua in unlocked_achievements]
        
        result = {
            'unlocked_achievements': unlocked_data,
            'total_achievements': Achievement.objects.filter(is_active=True).count(),
            'unlocked_count': len(unlocked_data),
            'total_points_from_achievements': sum(ua.points_awarded for ua in unlocked_achievements),
        }
        
        if include_progress:
            # Get progress towards unearned achievements
            unlocked_ids = {ua.achievement.achievement_id for ua in unlocked_achievements}
            unearned_achievements = Achievement.objects.filter(
                is_active=True
            ).exclude(achievement_id__in=unlocked_ids)
            
            progress_data = []
            for achievement in unearned_achievements:
                progress = AchievementService._calculate_achievement_progress(user, achievement)
                if progress['current_progress'] > 0:  # Only include if there's some progress
                    progress_data.append(progress)
            
            result['progress_towards_achievements'] = progress_data
        
        return result
    
    @staticmethod
    def _calculate_achievement_progress(user: User, achievement: Achievement) -> Dict[str, Any]:
        """
        Calculate user's progress towards a specific achievement
        
        Args:
            user: User instance
            achievement: Achievement instance
            
        Returns:
            Dictionary containing progress information
        """
        # Find the corresponding achievement definition
        achievement_def = None
        for ach_def in AVAILABLE_ACHIEVEMENTS:
            if ach_def.id == achievement.achievement_id:
                achievement_def = ach_def
                break
        
        if not achievement_def:
            return {
                'achievement': achievement.to_dict(),
                'current_progress': 0,
                'target_progress': 1,
                'completion_percentage': 0,
                'progress_description': 'Progress calculation not available'
            }
        
        # Calculate progress based on achievement type
        progress_info = AchievementService._get_specific_progress(user, achievement_def)
        
        return {
            'achievement': achievement.to_dict(),
            'current_progress': progress_info['current'],
            'target_progress': progress_info['target'],
            'completion_percentage': min(100, (progress_info['current'] / progress_info['target']) * 100),
            'progress_description': progress_info['description']
        }
    
    @staticmethod
    def _get_specific_progress(user: User, achievement_def) -> Dict[str, Any]:
        """Get specific progress for different achievement types"""
        from .models import TaskParticipation
        from django.db.models import Sum
        
        achievement_id = achievement_def.id
        
        if achievement_id == 'first_win':
            # Check for any first place finishes
            first_place_count = TaskParticipation.objects.filter(
                user=user,
                shared_task__is_competitive=True,
                status='completed'
            ).extra(
                where=["task_management_task_participation.completed_at = (SELECT MIN(tp2.completed_at) FROM task_management_task_participation tp2 WHERE tp2.shared_task_id = task_management_task_participation.shared_task_id AND tp2.status = 'completed')"]
            ).count()
            
            return {
                'current': min(first_place_count, 1),
                'target': 1,
                'description': f'Win your first competitive task ({first_place_count}/1)'
            }
        
        elif 'win_streak' in achievement_id:
            streak_length = getattr(achievement_def, 'streak_length', 3)
            current_streak = AchievementService._calculate_current_win_streak(user)
            
            return {
                'current': min(current_streak, streak_length),
                'target': streak_length,
                'description': f'Current win streak: {current_streak}/{streak_length}'
            }
        
        elif achievement_id == 'speed_demon':
            quick_completions = AchievementService._count_quick_completions(user)
            
            return {
                'current': min(quick_completions, 10),
                'target': 10,
                'description': f'Quick completions (within 1 hour): {quick_completions}/10'
            }
        
        elif achievement_id == 'consistent_performer':
            top_3_count = AchievementService._count_top_3_finishes(user)
            
            return {
                'current': min(top_3_count, 20),
                'target': 20,
                'description': f'Top 3 finishes: {top_3_count}/20'
            }
        
        elif 'point_master' in achievement_id:
            points_threshold = getattr(achievement_def, 'points_threshold', 1000)
            total_points = TaskParticipation.objects.filter(
                user=user,
                shared_task__is_competitive=True,
                status='completed'
            ).aggregate(total=Sum('points_earned'))['total'] or 0
            
            return {
                'current': min(total_points, points_threshold),
                'target': points_threshold,
                'description': f'Competitive points earned: {total_points:,}/{points_threshold:,}'
            }
        
        elif achievement_id == 'team_player':
            participation_count = TaskParticipation.objects.filter(user=user).count()
            
            return {
                'current': min(participation_count, 50),
                'target': 50,
                'description': f'Shared tasks participated: {participation_count}/50'
            }
        
        else:
            return {
                'current': 0,
                'target': 1,
                'description': 'Progress calculation not implemented'
            }
    
    @staticmethod
    def _calculate_current_win_streak(user: User) -> int:
        """Calculate user's current win streak"""
        from .models import TaskParticipation
        
        participations = TaskParticipation.objects.filter(
            user=user,
            shared_task__is_competitive=True,
            status='completed'
        ).order_by('-completed_at')
        
        current_streak = 0
        for participation in participations:
            if participation.completion_rank == 1:
                current_streak += 1
            else:
                break
        
        return current_streak
    
    @staticmethod
    def _count_quick_completions(user: User) -> int:
        """Count tasks completed within 1 hour of creation"""
        from .models import TaskParticipation
        
        quick_completions = 0
        participations = TaskParticipation.objects.filter(
            user=user,
            shared_task__is_competitive=True,
            status='completed'
        ).select_related('shared_task__task')
        
        for participation in participations:
            task_created = participation.shared_task.task.created_at
            completed_at = participation.completed_at
            
            if completed_at and (completed_at - task_created).total_seconds() <= 3600:
                quick_completions += 1
        
        return quick_completions
    
    @staticmethod
    def _count_top_3_finishes(user: User) -> int:
        """Count top 3 finishes in competitive tasks"""
        from .models import TaskParticipation
        
        participations = TaskParticipation.objects.filter(
            user=user,
            shared_task__is_competitive=True,
            status='completed'
        )
        
        top_3_count = 0
        for participation in participations:
            if participation.completion_rank and participation.completion_rank <= 3:
                top_3_count += 1
        
        return top_3_count
    
    @staticmethod
    def get_achievement_leaderboard(achievement_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get leaderboard for a specific achievement
        
        Args:
            achievement_id: Achievement ID to get leaderboard for
            limit: Maximum number of users to return
            
        Returns:
            List of user achievement data sorted by earned date
        """
        try:
            achievement = Achievement.objects.get(achievement_id=achievement_id, is_active=True)
            
            user_achievements = UserAchievement.objects.filter(
                achievement=achievement
            ).select_related('user').order_by('earned_at')[:limit]
            
            leaderboard = []
            for i, ua in enumerate(user_achievements, 1):
                leaderboard.append({
                    'rank': i,
                    'user_id': ua.user.id,
                    'phone_number': ua.user.phone_number,
                    'earned_at': ua.earned_at.isoformat(),
                    'points_awarded': ua.points_awarded,
                })
            
            return leaderboard
            
        except Achievement.DoesNotExist:
            return []
    
    @staticmethod
    def get_featured_achievements(user: User) -> List[Dict[str, Any]]:
        """
        Get user's featured achievements for profile display
        
        Args:
            user: User instance
            
        Returns:
            List of featured achievement data
        """
        featured_achievements = UserAchievement.objects.filter(
            user=user,
            is_featured=True
        ).select_related('achievement').order_by('-earned_at')
        
        return [ua.to_dict() for ua in featured_achievements]
    
    @staticmethod
    def set_featured_achievements(user: User, achievement_ids: List[str]) -> bool:
        """
        Set which achievements should be featured for a user
        
        Args:
            user: User instance
            achievement_ids: List of achievement IDs to feature
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with transaction.atomic():
                # Clear existing featured status
                UserAchievement.objects.filter(user=user).update(is_featured=False)
                
                # Set new featured achievements
                if achievement_ids:
                    UserAchievement.objects.filter(
                        user=user,
                        achievement__achievement_id__in=achievement_ids
                    ).update(is_featured=True)
                
                return True
                
        except Exception:
            return False
    
    @staticmethod
    def get_achievement_statistics() -> Dict[str, Any]:
        """
        Get global achievement statistics
        
        Returns:
            Dictionary containing achievement statistics
        """
        total_achievements = Achievement.objects.filter(is_active=True).count()
        total_unlocks = UserAchievement.objects.count()
        
        # Get most popular achievements
        popular_achievements = Achievement.objects.filter(
            is_active=True
        ).annotate(
            unlock_count=models.Count('user_unlocks')
        ).order_by('-unlock_count')[:5]
        
        # Get rarest achievements
        rarest_achievements = Achievement.objects.filter(
            is_active=True
        ).annotate(
            unlock_count=models.Count('user_unlocks')
        ).order_by('unlock_count')[:5]
        
        from django.db import models
        
        return {
            'total_achievements': total_achievements,
            'total_unlocks': total_unlocks,
            'average_unlocks_per_achievement': total_unlocks / total_achievements if total_achievements > 0 else 0,
            'most_popular_achievements': [
                {
                    'achievement': ach.to_dict(),
                    'unlock_count': ach.unlock_count
                }
                for ach in popular_achievements
            ],
            'rarest_achievements': [
                {
                    'achievement': ach.to_dict(),
                    'unlock_count': ach.unlock_count
                }
                for ach in rarest_achievements
            ]
        }