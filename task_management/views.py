from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Q, Count, Avg
from .models import Task, SharedTask, TaskParticipation
from .serializers import (
    TaskSerializer, TaskListSerializer, TaskCompletionSerializer,
    SharedTaskSerializer, SharedTaskCreateSerializer, TaskParticipationSerializer,
    SharedTaskInviteSerializer
)
from .filters import TaskFilter
from .notifications import (
    prepare_shared_task_invitation_notification,
    prepare_shared_task_completion_notification,
    prepare_participant_removed_notification,
    prepare_shared_task_deleted_notification,
    send_notifications,
    send_notification
)
from user_accounts.privacy_utils import (
    PrivacyChecker, 
    filter_tasks_by_privacy, 
    create_privacy_aware_activity
)


class TaskViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Task CRUD operations with filtering and completion
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = TaskFilter
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'deadline', 'priority', 'status', 'points_value']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Return tasks for the current user only"""
        return Task.objects.filter(user=self.request.user)
    
    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == 'list':
            return TaskListSerializer
        elif self.action == 'complete_task':
            return TaskCompletionSerializer
        return TaskSerializer
    
    def perform_create(self, serializer):
        """Set the user when creating a task"""
        serializer.save(user=self.request.user)
    
    def perform_update(self, serializer):
        """Prevent updating completed tasks"""
        task = self.get_object()
        if task.status == 'completed':
            # Allow updating only certain fields for completed tasks
            allowed_fields = ['title', 'description', 'is_private']
            update_data = {k: v for k, v in serializer.validated_data.items() if k in allowed_fields}
            if update_data:
                serializer.save(**update_data)
        else:
            serializer.save()
    
    @action(detail=True, methods=['post'])
    def complete_task(self, request, pk=None):
        """
        Complete a task and award points
        """
        task = self.get_object()
        
        if task.status == 'completed':
            return Response(
                {'error': 'Task is already completed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Mark task as completed
        task.mark_completed()
        
        # Calculate points earned
        points_earned = task.calculate_completion_points()
        
        # Update user's total points
        user_profile = getattr(request.user, 'profile', None)
        if user_profile:
            user_profile.total_points += points_earned
            user_profile.save(update_fields=['total_points'])
        
        # Create privacy-aware activity feed entry
        try:
            create_privacy_aware_activity(
                user=request.user,
                activity_type='task_completed',
                title=f'Completed task: {task.title}',
                description=f'Earned {points_earned} points',
                content={
                    'task_id': task.id,
                    'task_title': task.title,
                    'points_earned': points_earned,
                    'priority': task.priority
                },
                points_earned=points_earned
            )
        except Exception:
            pass  # Activity creation failed, continue
        
        # Return updated task data with points info
        serializer = TaskSerializer(task, context={'request': request})
        return Response({
            'task': serializer.data,
            'points_earned': points_earned,
            'message': f'Task completed! You earned {points_earned} points.'
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get task statistics for the current user
        """
        queryset = self.get_queryset()
        
        stats = {
            'total_tasks': queryset.count(),
            'completed_tasks': queryset.filter(status='completed').count(),
            'pending_tasks': queryset.filter(status='pending').count(),
            'overdue_tasks': queryset.filter(status='overdue').count(),
            'total_points_earned': sum(
                task.calculate_completion_points() 
                for task in queryset.filter(status='completed')
            ),
            'average_completion_time': None,
            'tasks_by_priority': {
                'high': queryset.filter(priority='high').count(),
                'medium': queryset.filter(priority='medium').count(),
                'low': queryset.filter(priority='low').count(),
            }
        }
        
        # Calculate average completion time
        completed_tasks = queryset.filter(status='completed', completed_at__isnull=False)
        if completed_tasks.exists():
            total_time = sum(
                (task.completed_at - task.created_at).total_seconds()
                for task in completed_tasks
            )
            avg_seconds = total_time / completed_tasks.count()
            stats['average_completion_time'] = avg_seconds / 3600  # Convert to hours
        
        return Response(stats)
    
    @action(detail=False, methods=['get'])
    def upcoming_deadlines(self, request):
        """
        Get tasks with upcoming deadlines (next 7 days)
        """
        now = timezone.now()
        week_from_now = now + timezone.timedelta(days=7)
        
        upcoming_tasks = self.get_queryset().filter(
            deadline__gte=now,
            deadline__lte=week_from_now,
            status='pending'
        ).order_by('deadline')
        
        serializer = TaskListSerializer(upcoming_tasks, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def update_overdue_tasks(self, request):
        """
        Update overdue status for all pending tasks
        """
        updated_count = 0
        for task in self.get_queryset().filter(status='pending'):
            if task.update_overdue_status():
                updated_count += 1
        
        return Response({
            'message': f'Updated {updated_count} tasks to overdue status',
            'updated_count': updated_count
        })
    
    @action(detail=False, methods=['get'])
    def filter_options(self, request):
        """
        Get available filter options for the frontend
        """
        return Response({
            'priorities': Task.PRIORITY_CHOICES,
            'statuses': Task.STATUS_CHOICES,
            'ordering_options': [
                ('created_at', 'Date Created'),
                ('-created_at', 'Date Created (Newest)'),
                ('deadline', 'Deadline'),
                ('-deadline', 'Deadline (Latest)'),
                ('priority', 'Priority'),
                ('-priority', 'Priority (High to Low)'),
                ('points_value', 'Points'),
                ('-points_value', 'Points (High to Low)'),
            ]
        })
    
    def destroy(self, request, *args, **kwargs):
        """
        Delete a task with proper cleanup
        """
        # Get task by ID, but allow access to shared tasks where user is a participant
        task_id = kwargs.get('pk')
        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist:
            return Response(
                {'error': 'Task not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if user has permission to delete/leave this task
        if task.user != request.user:
            # For non-owned tasks, check if it's a shared task where user is a participant
            if not task.is_shared:
                return Response(
                    {'error': 'You do not have permission to delete this task'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            try:
                shared_task = task.shared_details
                # Check if user is a participant
                if not TaskParticipation.objects.filter(shared_task=shared_task, user=request.user).exists():
                    return Response(
                        {'error': 'You are not a participant in this shared task'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except SharedTask.DoesNotExist:
                return Response(
                    {'error': 'You do not have permission to delete this task'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Check if task is shared and handle cleanup
        if task.is_shared:
            try:
                shared_task = task.shared_details
                
                # If user is the creator, delete the entire shared task
                if shared_task.creator == request.user:
                    # Get participants before deletion (excluding creator)
                    participants = list(shared_task.participants.exclude(id=request.user.id))
                    participant_count = shared_task.get_participant_count()
                    task_title = task.title
                    
                    # Send deletion notifications to participants
                    if participants:
                        notification_data = prepare_shared_task_deleted_notification(shared_task, participants)
                        send_notifications(notification_data)
                    
                    # Delete the base task, which will cascade delete the shared task
                    task.delete()
                    
                    return Response({
                        'message': f'Shared task "{task_title}" deleted successfully. {participant_count - 1} participants were notified.',
                        'deleted_shared_task': True
                    })
                else:
                    # If user is just a participant, remove them from the shared task
                    try:
                        participation = TaskParticipation.objects.get(
                            shared_task=shared_task,
                            user=request.user
                        )
                        participation.delete()
                        
                        return Response({
                            'message': 'You have been removed from the shared task.',
                            'left_shared_task': True
                        })
                    except TaskParticipation.DoesNotExist:
                        return Response(
                            {'error': 'You are not a participant in this shared task'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
            except SharedTask.DoesNotExist:
                # Task is marked as shared but no SharedTask exists, proceed with normal deletion
                pass
        
        # For regular tasks or shared tasks without SharedTask object
        task_title = task.title
        task.delete()
        
        return Response({
            'message': f'Task "{task_title}" deleted successfully.',
            'deleted_shared_task': False
        })


class SharedTaskViewSet(viewsets.ModelViewSet):
    """
    ViewSet for SharedTask operations
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['task__title', 'task__description']
    ordering_fields = ['created_at', 'task__deadline']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Return shared tasks where user is a participant"""
        return SharedTask.objects.filter(
            participants=self.request.user
        ).distinct()
    
    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == 'create':
            return SharedTaskCreateSerializer
        return SharedTaskSerializer
    
    @action(detail=True, methods=['post'])
    def join_task(self, request, pk=None):
        """
        Join a shared task as a participant
        """
        shared_task = self.get_object()
        
        # Check if user is already a participant
        if TaskParticipation.objects.filter(shared_task=shared_task, user=request.user).exists():
            return Response(
                {'error': 'You are already a participant in this task'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if task is full
        if not shared_task.can_add_participant():
            return Response(
                {'error': 'This shared task is full'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Add user as participant
        participation = TaskParticipation.objects.create(
            shared_task=shared_task,
            user=request.user
        )
        
        serializer = TaskParticipationSerializer(participation, context={'request': request})
        return Response({
            'message': 'Successfully joined the shared task',
            'participation': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def leave_task(self, request, pk=None):
        """
        Leave a shared task (if not the creator)
        """
        shared_task = self.get_object()
        
        if shared_task.creator == request.user:
            return Response(
                {'error': 'Task creator cannot leave the task'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            participation = TaskParticipation.objects.get(
                shared_task=shared_task,
                user=request.user
            )
            participation.delete()
            
            return Response({'message': 'Successfully left the shared task'})
        
        except TaskParticipation.DoesNotExist:
            return Response(
                {'error': 'You are not a participant in this task'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'])
    def complete_participation(self, request, pk=None):
        """
        Mark user's participation in shared task as completed
        """
        shared_task = self.get_object()
        
        try:
            participation = TaskParticipation.objects.get(
                shared_task=shared_task,
                user=request.user
            )
            
            if participation.status == 'completed':
                return Response(
                    {'error': 'You have already completed this task'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Mark participation as completed
            participation.mark_completed()
            
            # Update user's total points
            user_profile = getattr(request.user, 'profile', None)
            if user_profile:
                user_profile.total_points += participation.points_earned
                user_profile.save(update_fields=['total_points'])
            
            # Send completion notifications to other participants
            notification_data = prepare_shared_task_completion_notification(participation)
            send_notifications(notification_data)
            
            # Create activity feed entry for shared task completion
            try:
                from social_feed.utils import ActivityFeedManager
                ActivityFeedManager.create_shared_task_completion_activity(participation)
            except ImportError:
                pass  # Social feed not available
            
            serializer = TaskParticipationSerializer(participation, context={'request': request})
            return Response({
                'message': f'Task completed! You earned {participation.points_earned} points.',
                'participation': serializer.data,
                'points_earned': participation.points_earned
            })
        
        except TaskParticipation.DoesNotExist:
            return Response(
                {'error': 'You are not a participant in this task'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['get'])
    def leaderboard(self, request, pk=None):
        """
        Get leaderboard for a shared task
        """
        shared_task = self.get_object()
        
        participations = TaskParticipation.objects.filter(
            shared_task=shared_task
        ).order_by('-points_earned', 'completed_at')
        
        serializer = TaskParticipationSerializer(participations, many=True, context={'request': request})
        return Response({
            'shared_task_id': shared_task.id,
            'task_title': shared_task.task.title,
            'leaderboard': serializer.data,
            'completion_stats': shared_task.get_completion_stats()
        })
    
    @action(detail=True, methods=['post'])
    def invite_participants(self, request, pk=None):
        """
        Invite additional participants to a shared task (creator only)
        """
        shared_task = self.get_object()
        
        # Only creator can invite participants
        if shared_task.creator != request.user:
            return Response(
                {'error': 'Only the task creator can invite participants'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = SharedTaskInviteSerializer(
            data=request.data,
            context={'request': request, 'shared_task': shared_task}
        )
        
        if serializer.is_valid():
            participant_ids = serializer.validated_data['participant_ids']
            invited_users = []
            
            # Add participants
            from user_accounts.models import User
            for user_id in participant_ids:
                try:
                    user = User.objects.get(id=user_id)
                    participation, created = TaskParticipation.objects.get_or_create(
                        shared_task=shared_task,
                        user=user
                    )
                    if created:
                        invited_users.append(user)
                except User.DoesNotExist:
                    continue
            
            # Prepare and send invitation notifications
            if invited_users:
                notification_data = prepare_shared_task_invitation_notification(shared_task, invited_users)
                send_notifications(notification_data)
            
            return Response({
                'message': f'Successfully invited {len(invited_users)} participants',
                'invited_count': len(invited_users),
                'invited_users': [
                    {'id': user.id, 'phone_number': user.phone_number}
                    for user in invited_users
                ]
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def remove_participant(self, request, pk=None):
        """
        Remove a participant from a shared task (creator only)
        """
        shared_task = self.get_object()
        
        # Only creator can remove participants
        if shared_task.creator != request.user:
            return Response(
                {'error': 'Only the task creator can remove participants'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        participant_id = request.data.get('participant_id')
        if not participant_id:
            return Response(
                {'error': 'participant_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            participation = TaskParticipation.objects.get(
                shared_task=shared_task,
                user_id=participant_id
            )
            
            # Cannot remove the creator
            if participation.user == shared_task.creator:
                return Response(
                    {'error': 'Cannot remove the task creator'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            removed_user = participation.user
            user_phone = removed_user.phone_number
            participation.delete()
            
            # Send notification to removed user
            notification_data = prepare_participant_removed_notification(shared_task, removed_user)
            send_notification(notification_data)
            
            return Response({
                'message': f'Participant {user_phone} removed from shared task'
            })
            
        except TaskParticipation.DoesNotExist:
            return Response(
                {'error': 'Participant not found in this shared task'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['get'])
    def invitable_friends(self, request, pk=None):
        """
        Get list of friends who can be invited to this shared task
        """
        shared_task = self.get_object()
        
        # Only creator can see invitable friends
        if shared_task.creator != request.user:
            return Response(
                {'error': 'Only the task creator can view invitable friends'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        from friendships.models import Friendship
        from user_accounts.serializers import UserSerializer
        
        # Get all friends
        friends = Friendship.get_friends(request.user)
        
        # Exclude users who are already participants
        current_participant_ids = shared_task.participants.values_list('id', flat=True)
        invitable_friends = friends.exclude(id__in=current_participant_ids)
        
        serializer = UserSerializer(invitable_friends, many=True, context={'request': request})
        return Response({
            'invitable_friends': serializer.data,
            'count': invitable_friends.count(),
            'max_additional_participants': shared_task.max_participants - shared_task.get_participant_count()
        })
    
    @action(detail=False, methods=['get'])
    def my_shared_tasks(self, request):
        """
        Get shared tasks where user is a participant, grouped by status
        """
        user_participations = TaskParticipation.objects.filter(
            user=request.user
        ).select_related('shared_task__task', 'shared_task__creator')
        
        # Group by participation status
        pending_tasks = []
        completed_tasks = []
        
        for participation in user_participations:
            shared_task_data = SharedTaskSerializer(
                participation.shared_task, 
                context={'request': request}
            ).data
            shared_task_data['my_participation'] = TaskParticipationSerializer(
                participation, 
                context={'request': request}
            ).data
            
            if participation.status == 'completed':
                completed_tasks.append(shared_task_data)
            else:
                pending_tasks.append(shared_task_data)
        
        return Response({
            'pending_shared_tasks': pending_tasks,
            'completed_shared_tasks': completed_tasks,
            'total_pending': len(pending_tasks),
            'total_completed': len(completed_tasks)
        })
    
    @action(detail=False, methods=['get'])
    def competitive_stats(self, request):
        """
        Get competitive statistics for the current user across all shared tasks
        """
        user_participations = TaskParticipation.objects.filter(
            user=request.user,
            shared_task__is_competitive=True
        ).select_related('shared_task__task')
        
        # Calculate competitive statistics
        total_competitive_tasks = user_participations.count()
        completed_competitive_tasks = user_participations.filter(status='completed').count()
        
        # Rank statistics (need to calculate manually since completion_rank is a property)
        completed_participations = user_participations.filter(status='completed')
        first_place_finishes = 0
        second_place_finishes = 0
        third_place_finishes = 0
        
        for participation in completed_participations:
            rank = participation.completion_rank
            if rank == 1:
                first_place_finishes += 1
            elif rank == 2:
                second_place_finishes += 1
            elif rank == 3:
                third_place_finishes += 1
        
        # Points statistics
        total_competitive_points = sum(
            p.points_earned for p in user_participations.filter(status='completed')
        )
        
        average_points_per_task = (
            total_competitive_points / completed_competitive_tasks 
            if completed_competitive_tasks > 0 else 0
        )
        
        # Win rate (first place finishes / completed tasks)
        win_rate = (
            (first_place_finishes / completed_competitive_tasks * 100) 
            if completed_competitive_tasks > 0 else 0
        )
        
        # Podium rate (top 3 finishes / completed tasks)
        podium_finishes = first_place_finishes + second_place_finishes + third_place_finishes
        podium_rate = (
            (podium_finishes / completed_competitive_tasks * 100) 
            if completed_competitive_tasks > 0 else 0
        )
        
        return Response({
            'total_competitive_tasks': total_competitive_tasks,
            'completed_competitive_tasks': completed_competitive_tasks,
            'completion_rate': (
                (completed_competitive_tasks / total_competitive_tasks * 100) 
                if total_competitive_tasks > 0 else 0
            ),
            'rank_distribution': {
                'first_place': first_place_finishes,
                'second_place': second_place_finishes,
                'third_place': third_place_finishes,
                'other_ranks': completed_competitive_tasks - podium_finishes
            },
            'points_statistics': {
                'total_points': total_competitive_points,
                'average_points_per_task': round(average_points_per_task, 2)
            },
            'performance_metrics': {
                'win_rate': round(win_rate, 2),
                'podium_rate': round(podium_rate, 2)
            }
        })
    
    @action(detail=False, methods=['get'])
    def global_leaderboard(self, request):
        """
        Get global leaderboard across all competitive shared tasks
        """
        from .leaderboard_service import LeaderboardService
        
        # Get query parameters
        period = request.query_params.get('period', 'all_time')
        category = request.query_params.get('category', 'competitive_points')
        limit = int(request.query_params.get('limit', 50))
        
        try:
            leaderboard_data = LeaderboardService.get_global_leaderboard(
                period=period,
                category=category,
                limit=limit
            )
            
            # Get current user's ranking
            current_user_rank = None
            if request.user.is_authenticated:
                user_ranking = LeaderboardService.get_user_ranking(
                    user=request.user,
                    period=period,
                    category=category,
                    friends_only=False
                )
                current_user_rank = user_ranking['user_rank']
            
            leaderboard_data['current_user_rank'] = current_user_rank
            return Response(leaderboard_data)
            
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def friends_leaderboard(self, request):
        """
        Get leaderboard filtered to user's friends only
        """
        from .leaderboard_service import LeaderboardService
        
        # Get query parameters
        period = request.query_params.get('period', 'all_time')
        category = request.query_params.get('category', 'competitive_points')
        limit = int(request.query_params.get('limit', 20))
        
        try:
            leaderboard_data = LeaderboardService.get_friends_leaderboard(
                user=request.user,
                period=period,
                category=category,
                limit=limit
            )
            
            # Get current user's ranking among friends
            user_ranking = LeaderboardService.get_user_ranking(
                user=request.user,
                period=period,
                category=category,
                friends_only=True
            )
            
            leaderboard_data['current_user_rank'] = user_ranking['user_rank']
            return Response(leaderboard_data)
            
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def leaderboard_summary(self, request):
        """
        Get comprehensive leaderboard summary for current user
        """
        from .leaderboard_service import LeaderboardService
        
        summary = LeaderboardService.get_leaderboard_summary(request.user)
        return Response(summary)
    
    @action(detail=False, methods=['get'])
    def leaderboard_options(self, request):
        """
        Get available leaderboard periods and categories
        """
        from .leaderboard_service import LeaderboardService
        
        return Response({
            'periods': LeaderboardService.get_available_periods(),
            'categories': LeaderboardService.get_available_categories()
        })
    
    @action(detail=False, methods=['get'])
    def my_ranking(self, request):
        """
        Get current user's ranking across different categories
        """
        from .leaderboard_service import LeaderboardService
        
        period = request.query_params.get('period', 'all_time')
        category = request.query_params.get('category', 'competitive_points')
        friends_only = request.query_params.get('friends_only', 'false').lower() == 'true'
        
        try:
            ranking_data = LeaderboardService.get_user_ranking(
                user=request.user,
                period=period,
                category=category,
                friends_only=friends_only
            )
            
            return Response(ranking_data)
            
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def achievements(self, request):
        """
        Get user's competitive achievements
        """
        from .achievements import check_user_achievements, get_all_achievements
        
        unlocked_achievements = check_user_achievements(request.user)
        all_achievements = get_all_achievements()
        
        # Mark which achievements are unlocked
        unlocked_ids = {ach['id'] for ach in unlocked_achievements}
        for achievement in all_achievements:
            achievement['unlocked'] = achievement['id'] in unlocked_ids
        
        return Response({
            'unlocked_achievements': unlocked_achievements,
            'all_achievements': all_achievements,
            'total_unlocked': len(unlocked_achievements),
            'total_available': len(all_achievements),
            'completion_percentage': round(
                (len(unlocked_achievements) / len(all_achievements) * 100) 
                if all_achievements else 0, 2
            )
        })
    
    @action(detail=True, methods=['get'])
    def completion_analytics(self, request, pk=None):
        """
        Get detailed completion analytics for a shared task
        """
        shared_task = self.get_object()
        
        participations = TaskParticipation.objects.filter(
            shared_task=shared_task
        ).select_related('user').order_by('completed_at')
        
        # Calculate completion timeline
        completion_timeline = []
        for participation in participations.filter(status='completed'):
            completion_timeline.append({
                'user_id': participation.user.id,
                'user_phone': participation.user.phone_number,
                'completed_at': participation.completed_at,
                'points_earned': participation.points_earned,
                'completion_rank': participation.completion_rank,
                'time_to_complete': (
                    participation.completed_at - shared_task.created_at
                ).total_seconds() / 3600 if participation.completed_at else None  # hours
            })
        
        # Calculate statistics
        completed_count = len(completion_timeline)
        total_participants = participations.count()
        
        # Average completion time
        avg_completion_time = None
        if completion_timeline:
            total_time = sum(
                entry['time_to_complete'] for entry in completion_timeline 
                if entry['time_to_complete'] is not None
            )
            avg_completion_time = total_time / completed_count if completed_count > 0 else 0
        
        # Points distribution
        points_distribution = {
            'min_points': min((entry['points_earned'] for entry in completion_timeline), default=0),
            'max_points': max((entry['points_earned'] for entry in completion_timeline), default=0),
            'avg_points': (
                sum(entry['points_earned'] for entry in completion_timeline) / completed_count
                if completed_count > 0 else 0
            )
        }
        
        return Response({
            'shared_task_id': shared_task.id,
            'task_title': shared_task.task.title,
            'completion_timeline': completion_timeline,
            'statistics': {
                'total_participants': total_participants,
                'completed_count': completed_count,
                'completion_rate': (completed_count / total_participants * 100) if total_participants > 0 else 0,
                'average_completion_time_hours': round(avg_completion_time, 2) if avg_completion_time else None,
                'points_distribution': {
                    'min_points': points_distribution['min_points'],
                    'max_points': points_distribution['max_points'],
                    'avg_points': round(points_distribution['avg_points'], 2)
                }
            }
        })


class AchievementViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Achievement operations - read-only for users
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return active achievements"""
        from .models import Achievement
        return Achievement.objects.filter(is_active=True)
    
    def get_serializer_class(self):
        """Return appropriate serializer"""
        from .serializers import AchievementSerializer
        return AchievementSerializer
    
    @action(detail=False, methods=['get'])
    def my_achievements(self, request):
        """
        Get current user's achievements with progress information
        """
        from .achievement_service import AchievementService
        
        include_progress = request.query_params.get('include_progress', 'false').lower() == 'true'
        achievements_data = AchievementService.get_user_achievements(
            request.user, 
            include_progress=include_progress
        )
        
        return Response(achievements_data)
    
    @action(detail=False, methods=['post'])
    def check_achievements(self, request):
        """
        Manually trigger achievement checking for the current user
        """
        from .achievement_service import AchievementService
        
        newly_unlocked = AchievementService.check_and_unlock_achievements(request.user)
        
        return Response({
            'newly_unlocked_count': len(newly_unlocked),
            'newly_unlocked_achievements': [ua.to_dict() for ua in newly_unlocked],
            'message': f'Found {len(newly_unlocked)} new achievements!'
        })
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """
        Get user's featured achievements
        """
        from .achievement_service import AchievementService
        
        featured_achievements = AchievementService.get_featured_achievements(request.user)
        
        return Response({
            'featured_achievements': featured_achievements,
            'count': len(featured_achievements)
        })
    
    @action(detail=False, methods=['post'])
    def set_featured(self, request):
        """
        Set which achievements should be featured for the user
        """
        from .achievement_service import AchievementService
        
        achievement_ids = request.data.get('achievement_ids', [])
        
        if len(achievement_ids) > 5:  # Limit to 5 featured achievements
            return Response(
                {'error': 'Maximum 5 achievements can be featured'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        success = AchievementService.set_featured_achievements(request.user, achievement_ids)
        
        if success:
            return Response({'message': 'Featured achievements updated successfully'})
        else:
            return Response(
                {'error': 'Failed to update featured achievements'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def leaderboard(self, request, pk=None):
        """
        Get leaderboard for a specific achievement
        """
        from .achievement_service import AchievementService
        
        achievement = self.get_object()
        limit = int(request.query_params.get('limit', 10))
        
        leaderboard = AchievementService.get_achievement_leaderboard(
            achievement.achievement_id, 
            limit=limit
        )
        
        return Response({
            'achievement': achievement.to_dict(),
            'leaderboard': leaderboard,
            'total_unlocks': len(leaderboard)
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get global achievement statistics
        """
        from .achievement_service import AchievementService
        
        stats = AchievementService.get_achievement_statistics()
        
        return Response(stats)
    
    @action(detail=False, methods=['get'])
    def categories(self, request):
        """
        Get achievements grouped by category
        """
        from .models import Achievement
        from .serializers import AchievementSerializer
        
        achievements = Achievement.objects.filter(is_active=True).order_by('category', 'name')
        
        # Group by category
        categories = {}
        for achievement in achievements:
            category = achievement.category
            if category not in categories:
                categories[category] = {
                    'category': category,
                    'category_display': achievement.get_category_display(),
                    'achievements': []
                }
            
            achievement_data = AchievementSerializer(achievement).data
            
            # Check if user has unlocked this achievement
            if request.user.is_authenticated:
                from .models import UserAchievement
                achievement_data['unlocked'] = UserAchievement.objects.filter(
                    user=request.user,
                    achievement=achievement
                ).exists()
            else:
                achievement_data['unlocked'] = False
            
            categories[category]['achievements'].append(achievement_data)
        
        return Response({
            'categories': list(categories.values()),
            'total_categories': len(categories)
        })


class UserAchievementViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for UserAchievement operations - read-only
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return user's achievements"""
        from .models import UserAchievement
        return UserAchievement.objects.filter(user=self.request.user).select_related('achievement')
    
    def get_serializer_class(self):
        """Return appropriate serializer"""
        from .serializers import UserAchievementSerializer
        return UserAchievementSerializer
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """
        Get recently unlocked achievements
        """
        from django.utils import timezone
        
        days = int(request.query_params.get('days', 7))
        since_date = timezone.now() - timezone.timedelta(days=days)
        
        recent_achievements = self.get_queryset().filter(
            earned_at__gte=since_date
        ).order_by('-earned_at')
        
        serializer = self.get_serializer(recent_achievements, many=True)
        
        return Response({
            'recent_achievements': serializer.data,
            'count': recent_achievements.count(),
            'period_days': days
        })
    
    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """
        Get user's achievements grouped by category
        """
        achievements = self.get_queryset().select_related('achievement')
        
        # Group by category
        categories = {}
        for user_achievement in achievements:
            category = user_achievement.achievement.category
            if category not in categories:
                categories[category] = {
                    'category': category,
                    'category_display': user_achievement.achievement.get_category_display(),
                    'achievements': [],
                    'total_points': 0
                }
            
            achievement_data = user_achievement.to_dict()
            categories[category]['achievements'].append(achievement_data)
            categories[category]['total_points'] += user_achievement.points_awarded
        
        return Response({
            'categories': list(categories.values()),
            'total_categories': len(categories)
        })
    
    @action(detail=False, methods=['get'])
    def progress_summary(self, request):
        """
        Get summary of user's achievement progress
        """
        from .models import Achievement
        from .achievement_service import AchievementService
        
        # Get user's unlocked achievements
        unlocked_count = self.get_queryset().count()
        total_achievements = Achievement.objects.filter(is_active=True).count()
        
        # Get total points from achievements
        total_points = sum(ua.points_awarded for ua in self.get_queryset())
        
        # Get achievements by rarity
        rarity_breakdown = {}
        for ua in self.get_queryset().select_related('achievement'):
            rarity = ua.achievement.rarity
            if rarity not in rarity_breakdown:
                rarity_breakdown[rarity] = 0
            rarity_breakdown[rarity] += 1
        
        # Get recent progress (achievements in last 30 days)
        from django.utils import timezone
        month_ago = timezone.now() - timezone.timedelta(days=30)
        recent_unlocks = self.get_queryset().filter(earned_at__gte=month_ago).count()
        
        return Response({
            'progress_summary': {
                'unlocked_count': unlocked_count,
                'total_achievements': total_achievements,
                'completion_percentage': round(
                    (unlocked_count / total_achievements * 100) if total_achievements > 0 else 0, 2
                ),
                'total_points_from_achievements': total_points,
                'recent_unlocks_30_days': recent_unlocks
            },
            'rarity_breakdown': rarity_breakdown,
            'next_achievements': AchievementService.get_user_achievements(
                request.user, 
                include_progress=True
            ).get('progress_towards_achievements', [])[:5]  # Next 5 achievements with progress
        })