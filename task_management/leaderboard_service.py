"""
Leaderboard service for managing different types of leaderboards and rankings
"""
from typing import List, Dict, Any, Optional
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count, Avg, Q, F, Case, When, IntegerField
from django.utils import timezone
from datetime import timedelta
from .models import TaskParticipation, Task, SharedTask

User = get_user_model()


class LeaderboardService:
    """Service class for managing leaderboards and rankings"""
    
    TIME_PERIODS = {
        'daily': 1,
        'weekly': 7,
        'monthly': 30,
        'quarterly': 90,
        'yearly': 365,
        'all_time': None
    }
    
    LEADERBOARD_CATEGORIES = {
        'competitive_points': 'Competitive Points',
        'task_completion': 'Task Completion',
        'win_rate': 'Win Rate',
        'consistency': 'Consistency',
        'speed': 'Speed',
        'participation': 'Participation'
    }
    
    @staticmethod
    def get_global_leaderboard(
        period: str = 'all_time',
        category: str = 'competitive_points',
        limit: int = 50,
        user_filter: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Get global leaderboard with various filtering options
        
        Args:
            period: Time period for the leaderboard
            category: Category of leaderboard
            limit: Maximum number of users to return
            user_filter: Optional list of user IDs to filter by (for friends-only)
            
        Returns:
            Dictionary containing leaderboard data
        """
        # Get base queryset
        participations = LeaderboardService._get_base_participations(period)
        
        # Apply user filter if provided (for friends-only leaderboards)
        if user_filter:
            participations = participations.filter(user__id__in=user_filter)
        
        # Get leaderboard data based on category
        if category == 'competitive_points':
            return LeaderboardService._get_points_leaderboard(participations, period, limit)
        elif category == 'task_completion':
            return LeaderboardService._get_completion_leaderboard(participations, period, limit)
        elif category == 'win_rate':
            return LeaderboardService._get_win_rate_leaderboard(participations, period, limit)
        elif category == 'consistency':
            return LeaderboardService._get_consistency_leaderboard(participations, period, limit)
        elif category == 'speed':
            return LeaderboardService._get_speed_leaderboard(participations, period, limit)
        elif category == 'participation':
            return LeaderboardService._get_participation_leaderboard(participations, period, limit)
        else:
            raise ValueError(f"Unknown leaderboard category: {category}")
    
    @staticmethod
    def get_friends_leaderboard(
        user: User,
        period: str = 'all_time',
        category: str = 'competitive_points',
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Get leaderboard filtered to user's friends only
        
        Args:
            user: User to get friends leaderboard for
            period: Time period for the leaderboard
            category: Category of leaderboard
            limit: Maximum number of users to return
            
        Returns:
            Dictionary containing friends leaderboard data
        """
        # Get user's friends
        from friendships.models import Friendship
        friend_ids = Friendship.get_friend_ids(user)
        friend_ids.append(user.id)  # Include the user themselves
        
        return LeaderboardService.get_global_leaderboard(
            period=period,
            category=category,
            limit=limit,
            user_filter=friend_ids
        )
    
    @staticmethod
    def get_user_ranking(
        user: User,
        period: str = 'all_time',
        category: str = 'competitive_points',
        friends_only: bool = False
    ) -> Dict[str, Any]:
        """
        Get a specific user's ranking and stats
        
        Args:
            user: User to get ranking for
            period: Time period for the ranking
            category: Category of ranking
            friends_only: Whether to rank among friends only
            
        Returns:
            Dictionary containing user's ranking information
        """
        # Get appropriate leaderboard
        if friends_only:
            leaderboard_data = LeaderboardService.get_friends_leaderboard(
                user, period, category, limit=1000
            )
        else:
            leaderboard_data = LeaderboardService.get_global_leaderboard(
                period, category, limit=1000
            )
        
        # Find user in leaderboard
        user_rank = None
        user_stats = None
        
        for entry in leaderboard_data['leaderboard']:
            if entry['user']['id'] == user.id:
                user_rank = entry['rank']
                user_stats = entry
                break
        
        return {
            'user_rank': user_rank,
            'user_stats': user_stats,
            'total_participants': leaderboard_data['total_participants'],
            'period': period,
            'category': category,
            'friends_only': friends_only
        }
    
    @staticmethod
    def get_leaderboard_summary(user: User) -> Dict[str, Any]:
        """
        Get comprehensive leaderboard summary for a user
        
        Args:
            user: User to get summary for
            
        Returns:
            Dictionary containing leaderboard summary
        """
        summary = {
            'global_rankings': {},
            'friends_rankings': {},
            'achievements_ranking': {},
            'recent_performance': {}
        }
        
        # Get rankings across different categories and periods
        categories = ['competitive_points', 'win_rate', 'consistency']
        periods = ['weekly', 'monthly', 'all_time']
        
        for category in categories:
            summary['global_rankings'][category] = {}
            summary['friends_rankings'][category] = {}
            
            for period in periods:
                # Global ranking
                global_rank = LeaderboardService.get_user_ranking(
                    user, period, category, friends_only=False
                )
                summary['global_rankings'][category][period] = global_rank
                
                # Friends ranking
                friends_rank = LeaderboardService.get_user_ranking(
                    user, period, category, friends_only=True
                )
                summary['friends_rankings'][category][period] = friends_rank
        
        # Get achievements ranking
        from .models import UserAchievement
        user_achievement_count = UserAchievement.objects.filter(user=user).count()
        total_users_with_achievements = User.objects.filter(
            achievements__isnull=False
        ).distinct().count()
        
        if total_users_with_achievements > 0:
            users_with_more_achievements = User.objects.annotate(
                achievement_count=Count('achievements')
            ).filter(achievement_count__gt=user_achievement_count).count()
            
            achievement_rank = users_with_more_achievements + 1
        else:
            achievement_rank = 1 if user_achievement_count > 0 else None
        
        summary['achievements_ranking'] = {
            'rank': achievement_rank,
            'total_achievements': user_achievement_count,
            'total_participants': total_users_with_achievements
        }
        
        # Get recent performance (last 7 days)
        week_ago = timezone.now() - timedelta(days=7)
        recent_participations = TaskParticipation.objects.filter(
            user=user,
            shared_task__is_competitive=True,
            status='completed',
            completed_at__gte=week_ago
        )
        
        # Calculate recent performance manually
        first_places = 0
        total_rank = 0
        completed_count = recent_participations.count()
        
        for participation in recent_participations:
            if participation.completion_rank == 1:
                first_places += 1
            if participation.completion_rank:
                total_rank += participation.completion_rank
        
        average_rank = (total_rank / completed_count) if completed_count > 0 else 0
        
        summary['recent_performance'] = {
            'tasks_completed': completed_count,
            'points_earned': recent_participations.aggregate(
                total=Sum('points_earned')
            )['total'] or 0,
            'first_places': first_places,
            'average_rank': round(average_rank, 2)
        }
        
        return summary
    
    @staticmethod
    def _get_base_participations(period: str):
        """Get base queryset for participations with time filtering"""
        participations = TaskParticipation.objects.filter(
            shared_task__is_competitive=True,
            status='completed'
        ).select_related('user', 'shared_task__task')
        
        # Apply time filter
        if period != 'all_time' and period in LeaderboardService.TIME_PERIODS:
            days = LeaderboardService.TIME_PERIODS[period]
            if days:
                cutoff_date = timezone.now() - timedelta(days=days)
                participations = participations.filter(completed_at__gte=cutoff_date)
        
        return participations
    
    @staticmethod
    def _get_points_leaderboard(participations, period: str, limit: int) -> Dict[str, Any]:
        """Get leaderboard based on competitive points"""
        user_stats = participations.values('user').annotate(
            total_points=Sum('points_earned'),
            total_tasks=Count('id'),
            average_points=Avg('points_earned')
        ).order_by('-total_points', '-total_tasks')[:limit]
        
        # Calculate first places manually since completion_rank is a property
        leaderboard_data = []
        for user_stat in user_stats:
            user_participations = participations.filter(user=user_stat['user'])
            first_places = 0
            
            for participation in user_participations:
                if participation.completion_rank == 1:
                    first_places += 1
            
            user_stat['first_places'] = first_places
            user_stat['win_rate'] = (first_places / user_stat['total_tasks'] * 100) if user_stat['total_tasks'] > 0 else 0
            leaderboard_data.append(user_stat)
        
        # Re-sort by total points and first places
        leaderboard_data.sort(key=lambda x: (-x['total_points'], -x['first_places'], -x['win_rate']))
        user_stats = leaderboard_data[:limit]
        
        return LeaderboardService._format_leaderboard_response(
            user_stats, period, 'competitive_points', 'total_points'
        )
    
    @staticmethod
    def _get_completion_leaderboard(participations, period: str, limit: int) -> Dict[str, Any]:
        """Get leaderboard based on task completion count"""
        user_stats = participations.values('user').annotate(
            total_tasks=Count('id'),
            total_points=Sum('points_earned'),
            average_points=Avg('points_earned')
        ).order_by('-total_tasks', '-total_points')[:limit]
        
        # Calculate first places manually
        leaderboard_data = []
        for user_stat in user_stats:
            user_participations = participations.filter(user=user_stat['user'])
            first_places = 0
            
            for participation in user_participations:
                if participation.completion_rank == 1:
                    first_places += 1
            
            user_stat['first_places'] = first_places
            user_stat['win_rate'] = (first_places / user_stat['total_tasks'] * 100) if user_stat['total_tasks'] > 0 else 0
            leaderboard_data.append(user_stat)
        
        user_stats = leaderboard_data[:limit]
        
        return LeaderboardService._format_leaderboard_response(
            user_stats, period, 'task_completion', 'total_tasks'
        )
    
    @staticmethod
    def _get_win_rate_leaderboard(participations, period: str, limit: int) -> Dict[str, Any]:
        """Get leaderboard based on win rate (minimum 5 tasks)"""
        user_stats = participations.values('user').annotate(
            total_tasks=Count('id'),
            total_points=Sum('points_earned'),
            average_points=Avg('points_earned')
        ).filter(total_tasks__gte=5).order_by('-total_tasks', '-total_points')[:limit]
        
        # Calculate win rate manually
        leaderboard_data = []
        for user_stat in user_stats:
            user_participations = participations.filter(user=user_stat['user'])
            first_places = 0
            
            for participation in user_participations:
                if participation.completion_rank == 1:
                    first_places += 1
            
            user_stat['first_places'] = first_places
            user_stat['win_rate'] = (first_places / user_stat['total_tasks'] * 100) if user_stat['total_tasks'] > 0 else 0
            leaderboard_data.append(user_stat)
        
        # Sort by win rate
        leaderboard_data.sort(key=lambda x: (-x['win_rate'], -x['total_points'], -x['first_places']))
        user_stats = leaderboard_data[:limit]
        
        return LeaderboardService._format_leaderboard_response(
            user_stats, period, 'win_rate', 'win_rate'
        )
    
    @staticmethod
    def _get_consistency_leaderboard(participations, period: str, limit: int) -> Dict[str, Any]:
        """Get leaderboard based on consistency (top 3 finishes)"""
        user_stats = participations.values('user').annotate(
            total_tasks=Count('id'),
            total_points=Sum('points_earned'),
            average_points=Avg('points_earned')
        ).filter(total_tasks__gte=3).order_by('-total_tasks', '-total_points')[:limit]
        
        # Calculate consistency manually
        leaderboard_data = []
        for user_stat in user_stats:
            user_participations = participations.filter(user=user_stat['user'])
            first_places = 0
            top_3_finishes = 0
            
            for participation in user_participations:
                rank = participation.completion_rank
                if rank == 1:
                    first_places += 1
                if rank and rank <= 3:
                    top_3_finishes += 1
            
            user_stat['first_places'] = first_places
            user_stat['top_3_finishes'] = top_3_finishes
            user_stat['consistency_rate'] = (top_3_finishes / user_stat['total_tasks'] * 100) if user_stat['total_tasks'] > 0 else 0
            leaderboard_data.append(user_stat)
        
        # Sort by consistency rate
        leaderboard_data.sort(key=lambda x: (-x['consistency_rate'], -x['total_points']))
        user_stats = leaderboard_data[:limit]
        
        return LeaderboardService._format_leaderboard_response(
            user_stats, period, 'consistency', 'consistency_rate'
        )
    
    @staticmethod
    def _get_speed_leaderboard(participations, period: str, limit: int) -> Dict[str, Any]:
        """Get leaderboard based on average completion speed"""
        # Calculate average completion time for each user
        from django.db.models import Avg, DurationField
        from django.db.models import ExpressionWrapper
        
        user_stats = participations.annotate(
            completion_time=ExpressionWrapper(
                F('completed_at') - F('shared_task__task__created_at'),
                output_field=DurationField()
            )
        ).values('user').annotate(
            total_tasks=Count('id'),
            total_points=Sum('points_earned'),
            first_places=Count('id', filter=Q(completion_rank=1)),
            average_completion_time=Avg('completion_time'),
            average_points=Avg('points_earned')
        ).filter(total_tasks__gte=3).order_by('average_completion_time', '-total_points')[:limit]
        
        return LeaderboardService._format_leaderboard_response(
            user_stats, period, 'speed', 'average_completion_time', reverse_order=True
        )
    
    @staticmethod
    def _get_participation_leaderboard(participations, period: str, limit: int) -> Dict[str, Any]:
        """Get leaderboard based on participation in shared tasks"""
        # Include all participations, not just completed ones
        all_participations = TaskParticipation.objects.filter(
            shared_task__is_competitive=True
        ).select_related('user', 'shared_task__task')
        
        # Apply time filter
        if period != 'all_time' and period in LeaderboardService.TIME_PERIODS:
            days = LeaderboardService.TIME_PERIODS[period]
            if days:
                cutoff_date = timezone.now() - timedelta(days=days)
                all_participations = all_participations.filter(joined_at__gte=cutoff_date)
        
        user_stats = all_participations.values('user').annotate(
            total_participations=Count('id'),
            completed_tasks=Count('id', filter=Q(status='completed')),
            total_points=Sum('points_earned')
        ).order_by('-total_participations', '-total_points')[:limit]
        
        # Calculate first places and completion rate manually
        leaderboard_data = []
        for user_stat in user_stats:
            user_participations = all_participations.filter(user=user_stat['user'])
            first_places = 0
            
            for participation in user_participations.filter(status='completed'):
                if participation.completion_rank == 1:
                    first_places += 1
            
            user_stat['first_places'] = first_places
            user_stat['completion_rate'] = (user_stat['completed_tasks'] / user_stat['total_participations'] * 100) if user_stat['total_participations'] > 0 else 0
            leaderboard_data.append(user_stat)
        
        # Sort by participation metrics
        leaderboard_data.sort(key=lambda x: (-x['total_participations'], -x['completion_rate'], -x['total_points']))
        user_stats = leaderboard_data[:limit]
        
        return LeaderboardService._format_leaderboard_response(
            user_stats, period, 'participation', 'total_participations'
        )
    
    @staticmethod
    def _format_leaderboard_response(
        user_stats, 
        period: str, 
        category: str, 
        primary_metric: str,
        reverse_order: bool = False
    ) -> Dict[str, Any]:
        """Format leaderboard response with user data"""
        from user_accounts.serializers import UserSerializer
        
        leaderboard_data = []
        for i, user_stat in enumerate(user_stats, 1):
            try:
                user = User.objects.get(id=user_stat['user'])
                
                # Apply privacy controls - for now, all users are included
                # In the future, this could check user privacy settings
                # if hasattr(user, 'privacy_settings') and user.privacy_settings.get('hide_from_leaderboards'):
                #     continue
                
                user_data = UserSerializer(user).data
                
                # Format the entry
                entry = {
                    'rank': i,
                    'user': user_data,
                    'primary_metric': user_stat.get(primary_metric, 0),
                    'total_points': user_stat.get('total_points', 0),
                    'total_tasks': user_stat.get('total_tasks', 0),
                    'first_places': user_stat.get('first_places', 0),
                }
                
                # Add category-specific metrics
                if category == 'competitive_points':
                    entry.update({
                        'average_points': round(user_stat.get('average_points', 0), 2),
                        'win_rate': round(user_stat.get('win_rate', 0), 2)
                    })
                elif category == 'win_rate':
                    entry['win_rate'] = round(user_stat.get('win_rate', 0), 2)
                elif category == 'consistency':
                    entry.update({
                        'top_3_finishes': user_stat.get('top_3_finishes', 0),
                        'consistency_rate': round(user_stat.get('consistency_rate', 0), 2)
                    })
                elif category == 'speed':
                    avg_time = user_stat.get('average_completion_time')
                    if avg_time:
                        entry['average_completion_hours'] = round(avg_time.total_seconds() / 3600, 2)
                    else:
                        entry['average_completion_hours'] = 0
                elif category == 'participation':
                    entry.update({
                        'total_participations': user_stat.get('total_participations', 0),
                        'completed_tasks': user_stat.get('completed_tasks', 0),
                        'completion_rate': round(user_stat.get('completion_rate', 0), 2)
                    })
                
                leaderboard_data.append(entry)
                
            except User.DoesNotExist:
                continue
        
        return {
            'period': period,
            'category': category,
            'category_display': LeaderboardService.LEADERBOARD_CATEGORIES.get(category, category),
            'leaderboard': leaderboard_data,
            'total_participants': len(leaderboard_data),
            'primary_metric': primary_metric
        }
    
    @staticmethod
    def get_available_periods() -> List[Dict[str, Any]]:
        """Get list of available time periods"""
        return [
            {'key': key, 'display': key.replace('_', ' ').title(), 'days': days}
            for key, days in LeaderboardService.TIME_PERIODS.items()
        ]
    
    @staticmethod
    def get_available_categories() -> List[Dict[str, Any]]:
        """Get list of available leaderboard categories"""
        return [
            {'key': key, 'display': display}
            for key, display in LeaderboardService.LEADERBOARD_CATEGORIES.items()
        ]