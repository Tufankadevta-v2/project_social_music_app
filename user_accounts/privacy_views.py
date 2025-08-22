from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.db import transaction, models
from rest_framework import serializers

from .privacy_models import PrivacySettings, FriendPrivacySettings, PrivateTask
from .privacy_serializers import (
    PrivacySettingsSerializer,
    FriendPrivacySettingsSerializer,
    PrivateTaskSerializer,
    PrivacySettingsUpdateSerializer,
    PrivacyCheckSerializer
)
# from .permissions import IsOwnerOrReadOnly  # Not needed for now

User = get_user_model()


class PrivacySettingsView(generics.RetrieveUpdateAPIView):
    """
    View for retrieving and updating user privacy settings
    """
    serializer_class = PrivacySettingsSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        """Get or create privacy settings for the authenticated user"""
        return PrivacySettings.get_or_create_for_user(self.request.user)
    
    def perform_update(self, serializer):
        """Update privacy settings and handle side effects"""
        instance = serializer.save()
        
        # If user disabled friend requests, cancel all pending requests
        if not instance.allow_friend_requests:
            from friendships.models import Friendship
            Friendship.objects.filter(
                addressee=self.request.user,
                status='pending'
            ).update(status='declined')
        
        # If user disabled shared task invites, decline pending invites
        if not instance.allow_shared_task_invites:
            from task_management.models import TaskParticipation
            TaskParticipation.objects.filter(
                user=self.request.user,
                status='pending'
            ).delete()


class FriendPrivacySettingsListView(generics.ListCreateAPIView):
    """
    View for listing and creating friend-specific privacy settings
    """
    serializer_class = FriendPrivacySettingsSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Get friend privacy settings for the authenticated user"""
        return FriendPrivacySettings.objects.filter(
            user=self.request.user
        ).select_related('friend', 'friend__profile')
    
    def perform_create(self, serializer):
        """Create friend privacy settings for the authenticated user"""
        serializer.save(user=self.request.user)


class FriendPrivacySettingsDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    View for retrieving, updating, and deleting specific friend privacy settings
    """
    serializer_class = FriendPrivacySettingsSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Get friend privacy settings for the authenticated user"""
        return FriendPrivacySettings.objects.filter(user=self.request.user)
    
    def perform_destroy(self, instance):
        """Reset to default privacy settings when deleting custom settings"""
        # Instead of deleting, reset to default values
        instance.visibility_level = 'full'
        instance.apply_visibility_level()
        instance.save()


class PrivateTaskListView(generics.ListCreateAPIView):
    """
    View for listing and creating private task settings
    """
    serializer_class = PrivateTaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Get private task settings for the authenticated user's tasks"""
        return PrivateTask.objects.filter(
            task__user=self.request.user
        ).select_related('task')
    
    def perform_create(self, serializer):
        """Create private task settings"""
        # Validate that the task belongs to the user
        task = serializer.validated_data['task']
        if task.user != self.request.user:
            raise serializers.ValidationError("You can only set privacy for your own tasks")
        
        serializer.save()


class PrivateTaskDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    View for retrieving, updating, and deleting private task settings
    """
    serializer_class = PrivateTaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Get private task settings for the authenticated user's tasks"""
        return PrivateTask.objects.filter(task__user=self.request.user)


class BulkPrivacyUpdateView(APIView):
    """
    View for updating all privacy settings in a single request
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def put(self, request):
        """Update all privacy settings"""
        serializer = PrivacySettingsUpdateSerializer(
            instance=request.user,
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response(
                {'message': 'Privacy settings updated successfully'},
                status=status.HTTP_200_OK
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PrivacyCheckView(APIView):
    """
    View for checking privacy permissions between users
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Check if user has permission to view target user's content"""
        serializer = PrivacyCheckSerializer(data=request.data)
        
        if serializer.is_valid():
            target_user_id = serializer.validated_data['target_user_id']
            permission_type = serializer.validated_data['permission_type']
            
            target_user = get_object_or_404(User, id=target_user_id)
            privacy_settings = PrivacySettings.get_or_create_for_user(target_user)
            
            # Check permission based on type
            has_permission = False
            
            if permission_type == 'profile':
                has_permission = privacy_settings.can_view_profile(request.user)
            elif permission_type == 'tasks':
                has_permission = privacy_settings.can_view_tasks(request.user)
            elif permission_type == 'task_completions':
                has_permission = privacy_settings.can_view_task_completions(request.user)
            elif permission_type == 'achievements':
                has_permission = privacy_settings.can_view_achievements(request.user)
            elif permission_type == 'activity_feed':
                # Check both general privacy and friend-specific settings
                has_permission = privacy_settings.can_view_task_completions(request.user)
                
                # Check friend-specific settings if they exist
                try:
                    friend_settings = FriendPrivacySettings.objects.get(
                        user=target_user,
                        friend=request.user
                    )
                    has_permission = has_permission and friend_settings.can_see_activity_feed
                except FriendPrivacySettings.DoesNotExist:
                    pass
            
            return Response({
                'has_permission': has_permission,
                'target_user_id': target_user_id,
                'permission_type': permission_type
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def privacy_summary_view(request):
    """
    Get a summary of user's privacy settings
    """
    user = request.user
    privacy_settings = PrivacySettings.get_or_create_for_user(user)
    
    # Count friend-specific settings
    friend_settings_count = FriendPrivacySettings.objects.filter(user=user).count()
    
    # Count private tasks
    private_tasks_count = PrivateTask.objects.filter(task__user=user).count()
    
    # Get friends with custom privacy settings
    custom_friend_settings = FriendPrivacySettings.objects.filter(
        user=user
    ).exclude(visibility_level='full').select_related('friend')
    
    summary = {
        'privacy_settings': PrivacySettingsSerializer(privacy_settings).data,
        'friend_settings_count': friend_settings_count,
        'private_tasks_count': private_tasks_count,
        'custom_friend_settings': [
            {
                'friend_id': setting.friend.id,
                'friend_phone': setting.friend.phone_number,
                'visibility_level': setting.visibility_level
            }
            for setting in custom_friend_settings
        ],
        'privacy_score': calculate_privacy_score(privacy_settings, friend_settings_count, private_tasks_count)
    }
    
    return Response(summary)


def calculate_privacy_score(privacy_settings, friend_settings_count, private_tasks_count):
    """
    Calculate a privacy score from 0-100 based on user's privacy settings
    """
    score = 0
    
    # Base privacy settings (40 points total)
    visibility_scores = {'private': 10, 'friends': 5, 'public': 0}
    
    score += visibility_scores.get(privacy_settings.profile_visibility, 0)
    score += visibility_scores.get(privacy_settings.task_visibility, 0)
    score += visibility_scores.get(privacy_settings.achievement_visibility, 0)
    score += visibility_scores.get(privacy_settings.task_completion_visibility, 0)
    
    # Boolean settings (30 points total)
    boolean_settings = [
        privacy_settings.show_in_leaderboards,
        privacy_settings.allow_friend_requests,
        privacy_settings.allow_shared_task_invites,
        privacy_settings.share_location,
        privacy_settings.show_online_status,
        privacy_settings.show_last_seen,
    ]
    
    # Invert boolean values (False = more private = higher score)
    score += sum(5 for setting in boolean_settings if not setting)
    
    # Friend-specific settings (20 points total)
    if friend_settings_count > 0:
        score += min(20, friend_settings_count * 2)
    
    # Private tasks (10 points total)
    if private_tasks_count > 0:
        score += min(10, private_tasks_count)
    
    return min(100, score)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def reset_privacy_settings_view(request):
    """
    Reset all privacy settings to default values
    """
    user = request.user
    
    with transaction.atomic():
        # Reset main privacy settings
        privacy_settings = PrivacySettings.get_or_create_for_user(user)
        privacy_settings.profile_visibility = 'friends'
        privacy_settings.task_visibility = 'friends'
        privacy_settings.task_completion_visibility = 'friends'
        privacy_settings.achievement_visibility = 'friends'
        privacy_settings.activity_feed_visibility = 'all'
        privacy_settings.show_in_leaderboards = True
        privacy_settings.allow_friend_requests = True
        privacy_settings.allow_shared_task_invites = True
        privacy_settings.share_location = False
        privacy_settings.allow_contact_sync = True
        privacy_settings.show_online_status = True
        privacy_settings.show_last_seen = True
        privacy_settings.save()
        
        # Reset friend-specific settings
        FriendPrivacySettings.objects.filter(user=user).delete()
        
        # Reset private task settings
        PrivateTask.objects.filter(task__user=user).delete()
    
    return Response({
        'message': 'Privacy settings reset to default values',
        'privacy_settings': PrivacySettingsSerializer(privacy_settings).data
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def privacy_recommendations_view(request):
    """
    Get privacy recommendations based on user's current settings and activity
    """
    user = request.user
    privacy_settings = PrivacySettings.get_or_create_for_user(user)
    
    recommendations = []
    
    # Check if user has public settings but few friends
    from friendships.models import Friendship
    friends_count = Friendship.get_friends(user).count()
    
    if friends_count < 5:
        if privacy_settings.profile_visibility == 'public':
            recommendations.append({
                'type': 'security',
                'title': 'Consider making your profile friends-only',
                'description': 'You have few friends but a public profile. Consider restricting visibility.',
                'action': 'Set profile_visibility to "friends"'
            })
    
    # Check for inconsistent settings
    if privacy_settings.profile_visibility == 'private' and privacy_settings.task_visibility == 'public':
        recommendations.append({
            'type': 'consistency',
            'title': 'Inconsistent privacy settings',
            'description': 'Your profile is private but tasks are public. Consider aligning these settings.',
            'action': 'Set task_visibility to "private" or "friends"'
        })
    
    # Check if user shares location but has restrictive other settings
    if privacy_settings.share_location and privacy_settings.profile_visibility == 'private':
        recommendations.append({
            'type': 'privacy',
            'title': 'Location sharing with private profile',
            'description': 'You share location but have a private profile. Consider disabling location sharing.',
            'action': 'Set share_location to false'
        })
    
    # Check for tasks that might need privacy settings
    from task_management.models import Task
    sensitive_keywords = ['personal', 'private', 'secret', 'confidential', 'therapy', 'medical']
    
    potentially_private_tasks = Task.objects.filter(
        user=user,
        status__in=['pending', 'completed']
    ).filter(
        models.Q(title__icontains='personal') |
        models.Q(description__icontains='personal') |
        models.Q(title__icontains='private') |
        models.Q(description__icontains='private')
    ).exclude(
        id__in=PrivateTask.objects.filter(task__user=user).values_list('task_id', flat=True)
    )[:5]
    
    if potentially_private_tasks.exists():
        recommendations.append({
            'type': 'task_privacy',
            'title': 'Consider making some tasks private',
            'description': f'You have {potentially_private_tasks.count()} tasks that might be personal.',
            'action': 'Review and set privacy settings for sensitive tasks',
            'task_ids': list(potentially_private_tasks.values_list('id', flat=True))
        })
    
    return Response({
        'recommendations': recommendations,
        'privacy_score': calculate_privacy_score(
            privacy_settings,
            FriendPrivacySettings.objects.filter(user=user).count(),
            PrivateTask.objects.filter(task__user=user).count()
        )
    })