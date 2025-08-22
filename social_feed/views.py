from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Q, Count, Prefetch
from django.db import transaction

from .models import (
    ActivityFeed, ActivityInteraction, ActivityFeedSettings, UserLocation,
    NearbyFriendRecommendation, SocialFeedPost, SocialPostInteraction,
    ActivityFeedCache, ActivityFeedStory, StoryView, SocialChallenge,
    ChallengeParticipation, UserEngagementMetrics
)
from .serializers import (
    ActivityFeedSerializer, ActivityFeedCreateSerializer, ActivityInteractionSerializer,
    UserLocationSerializer, NearbyFriendRecommendationSerializer,
    SocialFeedPostSerializer, SocialFeedPostCreateSerializer, SocialPostInteractionSerializer,
    ActivityFeedSettingsSerializer, FeedInteractionSerializer, SocialPostInteractionCreateSerializer,
    ActivityFeedStorySerializer, ActivityFeedStoryCreateSerializer, StoryViewSerializer,
    SocialChallengeSerializer, SocialChallengeCreateSerializer, ChallengeParticipationSerializer,
    UserEngagementMetricsSerializer
)
from friendships.models import Friendship
from user_accounts.privacy_utils import (
    PrivacyChecker, 
    filter_activity_feed_by_privacy,
    should_notify_user
)


class ActivityFeedPagination(PageNumberPagination):
    """Custom pagination for activity feed"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 50


class ActivityFeedViewSet(viewsets.ModelViewSet):
    """
    ViewSet for activity feed management
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ActivityFeedSerializer
    pagination_class = ActivityFeedPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'points_earned']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Get privacy-filtered activity feed for current user"""
        user = self.request.user
        
        # Get base queryset with all activities
        base_queryset = ActivityFeed.objects.select_related('user').prefetch_related(
            'photos',
            Prefetch('interactions', queryset=ActivityInteraction.objects.select_related('user'))
        )
        
        # Apply privacy filtering
        queryset = filter_activity_feed_by_privacy(base_queryset, user)
        
        # Apply user's activity feed settings
        settings = ActivityFeedSettings.get_or_create_for_user(user)
        
        # Filter by activity types based on user preferences
        activity_type_filters = []
        if settings.show_task_completions:
            activity_type_filters.extend(['task_completed', 'workout_completed'])
        if settings.show_achievements:
            activity_type_filters.extend(['achievement_earned', 'goal_achieved'])
        if settings.show_milestones:
            activity_type_filters.extend(['milestone_reached', 'streak_achieved'])
        if settings.show_shared_task_activities:
            activity_type_filters.extend(['shared_task_completed', 'shared_task_created'])
        if settings.show_leaderboard_positions:
            activity_type_filters.append('leaderboard_position')
        
        # Always include photo shares and celebrations
        activity_type_filters.extend(['photo_shared', 'celebration', 'friend_joined'])
        
        if activity_type_filters:
            queryset = queryset.filter(activity_type__in=activity_type_filters)
        
        return queryset
    
    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == 'create':
            return ActivityFeedCreateSerializer
        return ActivityFeedSerializer
    
    def perform_create(self, serializer):
        """Create activity feed entry"""
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def my_activities(self, request):
        """Get current user's own activities"""
        activities = ActivityFeed.objects.filter(
            user=request.user
        ).select_related('user').prefetch_related('photos', 'interactions')
        
        page = self.paginate_queryset(activities)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(activities, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def interact(self, request, pk=None):
        """Add interaction to activity feed entry"""
        activity = self.get_object()
        serializer = FeedInteractionSerializer(data=request.data)
        
        if serializer.is_valid():
            interaction_type = serializer.validated_data['interaction_type']
            comment_text = serializer.validated_data.get('comment_text', '')
            
            # Check if user can interact with this activity
            if not activity.get_visible_to_user(request.user):
                return Response(
                    {'error': 'You do not have permission to interact with this activity'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # For non-comment interactions, remove existing interaction of same type
            if interaction_type != 'comment':
                ActivityInteraction.objects.filter(
                    activity=activity,
                    user=request.user,
                    interaction_type=interaction_type
                ).delete()
            
            # Create new interaction
            interaction, created = ActivityInteraction.objects.get_or_create(
                activity=activity,
                user=request.user,
                interaction_type=interaction_type,
                defaults={'comment_text': comment_text}
            )
            
            if not created and interaction_type == 'comment':
                # For comments, always create new ones
                interaction = ActivityInteraction.objects.create(
                    activity=activity,
                    user=request.user,
                    interaction_type=interaction_type,
                    comment_text=comment_text
                )
            
            interaction_serializer = ActivityInteractionSerializer(
                interaction, 
                context={'request': request}
            )
            
            return Response({
                'message': f'Successfully {interaction_type}d activity',
                'interaction': interaction_serializer.data
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['delete'])
    def remove_interaction(self, request, pk=None):
        """Remove interaction from activity feed entry"""
        activity = self.get_object()
        interaction_type = request.query_params.get('type')
        
        if not interaction_type:
            return Response(
                {'error': 'Interaction type is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            interaction = ActivityInteraction.objects.get(
                activity=activity,
                user=request.user,
                interaction_type=interaction_type
            )
            interaction.delete()
            
            return Response({'message': f'Successfully removed {interaction_type}'})
        
        except ActivityInteraction.DoesNotExist:
            return Response(
                {'error': 'Interaction not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def trending(self, request):
        """Get trending activities (most interactions in last 24 hours)"""
        yesterday = timezone.now() - timezone.timedelta(hours=24)
        
        # Get friends list
        friends = Friendship.get_friends(request.user)
        friend_ids = list(friends.values_list('id', flat=True))
        friend_ids.append(request.user.id)
        
        trending_activities = ActivityFeed.objects.filter(
            user_id__in=friend_ids,
            is_public=True,
            created_at__gte=yesterday
        ).annotate(
            interaction_count=Count('interactions')
        ).filter(
            interaction_count__gt=0
        ).order_by('-interaction_count', '-created_at')[:10]
        
        serializer = self.get_serializer(trending_activities, many=True)
        return Response(serializer.data)


class SocialFeedPostViewSet(viewsets.ModelViewSet):
    """
    ViewSet for social feed posts (user-created content)
    """
    permission_classes = [IsAuthenticated]
    serializer_class = SocialFeedPostSerializer
    pagination_class = ActivityFeedPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'content', 'location_name']
    filterset_fields = ['post_type', 'is_public']
    ordering_fields = ['created_at', 'likes_count', 'comments_count']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Get social posts visible to current user"""
        user = self.request.user
        
        # Get friends list
        friends = Friendship.get_friends(user)
        friend_ids = list(friends.values_list('id', flat=True))
        friend_ids.append(user.id)  # Include user's own posts
        
        # Base queryset with privacy filtering
        queryset = SocialFeedPost.objects.filter(
            user_id__in=friend_ids,
            is_public=True
        ).select_related('user').prefetch_related(
            'photos',
            Prefetch('interactions', queryset=SocialPostInteraction.objects.select_related('user'))
        )
        
        return queryset
    
    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == 'create':
            return SocialFeedPostCreateSerializer
        return SocialFeedPostSerializer
    
    def perform_create(self, serializer):
        """Create social post"""
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def my_posts(self, request):
        """Get current user's own posts"""
        posts = SocialFeedPost.objects.filter(
            user=request.user
        ).select_related('user').prefetch_related('photos', 'interactions')
        
        page = self.paginate_queryset(posts)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(posts, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def react(self, request, pk=None):
        """Add reaction to social post"""
        post = self.get_object()
        serializer = SocialPostInteractionCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            interaction_type = serializer.validated_data['interaction_type']
            comment_text = serializer.validated_data.get('comment_text', '')
            
            # Check if user can interact with this post
            if not post.get_visible_to_user(request.user):
                return Response(
                    {'error': 'You do not have permission to interact with this post'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            with transaction.atomic():
                # For non-comment interactions, remove existing reactions
                if interaction_type != 'comment':
                    SocialPostInteraction.objects.filter(
                        post=post,
                        user=request.user
                    ).exclude(interaction_type='comment').delete()
                
                # Create new interaction
                interaction = SocialPostInteraction.objects.create(
                    post=post,
                    user=request.user,
                    interaction_type=interaction_type,
                    comment_text=comment_text
                )
            
            interaction_serializer = SocialPostInteractionSerializer(
                interaction, 
                context={'request': request}
            )
            
            return Response({
                'message': f'Successfully {interaction_type}d post',
                'interaction': interaction_serializer.data
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['delete'])
    def remove_reaction(self, request, pk=None):
        """Remove reaction from social post"""
        post = self.get_object()
        
        # Remove all non-comment reactions from this user
        deleted_count = SocialPostInteraction.objects.filter(
            post=post,
            user=request.user
        ).exclude(interaction_type='comment').delete()[0]
        
        if deleted_count > 0:
            return Response({'message': 'Successfully removed reaction'})
        else:
            return Response(
                {'error': 'No reaction found to remove'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def nearby_posts(self, request):
        """Get posts from nearby users"""
        if not hasattr(request.user, 'location') or not request.user.location.is_location_enabled:
            return Response(
                {'error': 'Location sharing must be enabled to see nearby posts'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get nearby users
        nearby_users = UserLocation.find_nearby_users(request.user, radius_km=25, max_results=100)
        nearby_user_ids = [user.id for user in nearby_users]
        
        # Get posts from nearby users
        nearby_posts = SocialFeedPost.objects.filter(
            user_id__in=nearby_user_ids,
            is_public=True,
            latitude__isnull=False,
            longitude__isnull=False
        ).select_related('user').prefetch_related('photos', 'interactions')
        
        page = self.paginate_queryset(nearby_posts)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(nearby_posts, many=True)
        return Response(serializer.data)


class UserLocationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for user location management
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserLocationSerializer
    
    def get_queryset(self):
        """Get current user's location only"""
        return UserLocation.objects.filter(user=self.request.user)
    
    def get_object(self):
        """Get or create user location"""
        location, created = UserLocation.objects.get_or_create(
            user=self.request.user
        )
        return location
    
    def perform_create(self, serializer):
        """Create user location"""
        serializer.save(user=self.request.user)
    
    def perform_update(self, serializer):
        """Update user location"""
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def nearby_friends(self, request):
        """Get nearby friend recommendations"""
        # Generate fresh recommendations
        recommendations = NearbyFriendRecommendation.generate_recommendations_for_user(
            request.user,
            force_refresh=request.query_params.get('refresh') == 'true'
        )
        
        serializer = NearbyFriendRecommendationSerializer(
            recommendations, 
            many=True, 
            context={'request': request}
        )
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def dismiss_recommendation(self, request):
        """Dismiss a nearby friend recommendation"""
        recommendation_id = request.data.get('recommendation_id')
        
        if not recommendation_id:
            return Response(
                {'error': 'recommendation_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            recommendation = NearbyFriendRecommendation.objects.get(
                id=recommendation_id,
                user=request.user
            )
            recommendation.is_dismissed = True
            recommendation.save(update_fields=['is_dismissed'])
            
            return Response({'message': 'Recommendation dismissed'})
        
        except NearbyFriendRecommendation.DoesNotExist:
            return Response(
                {'error': 'Recommendation not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def location_stats(self, request):
        """Get location-based statistics"""
        if not hasattr(request.user, 'location') or not request.user.location.is_location_enabled:
            return Response({
                'location_enabled': False,
                'nearby_users_count': 0,
                'nearby_friends_count': 0,
                'location_precision': 'disabled'
            })
        
        user_location = request.user.location
        nearby_users = UserLocation.find_nearby_users(request.user, radius_km=50)
        
        # Count nearby friends
        friends = Friendship.get_friends(request.user)
        nearby_friends = [user for user in nearby_users if user in friends]
        
        return Response({
            'location_enabled': True,
            'nearby_users_count': len(nearby_users),
            'nearby_friends_count': len(nearby_friends),
            'location_precision': user_location.location_precision,
            'city': user_location.city,
            'country': user_location.country,
            'last_updated': user_location.last_updated
        })


class ActivityFeedSettingsViewSet(viewsets.ModelViewSet):
    """
    ViewSet for activity feed settings
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ActivityFeedSettingsSerializer
    
    def get_queryset(self):
        """Get current user's settings only"""
        return ActivityFeedSettings.objects.filter(user=self.request.user)
    
    def get_object(self):
        """Get or create user settings"""
        return ActivityFeedSettings.get_or_create_for_user(self.request.user)
    
    def perform_create(self, serializer):
        """Create settings"""
        serializer.save(user=self.request.user)
    
    def perform_update(self, serializer):
        """Update settings"""
        serializer.save(user=self.request.user)


class SocialFeedStatsView(viewsets.ViewSet):
    """
    ViewSet for social feed statistics and analytics
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Get social feed dashboard statistics"""
        user = request.user
        
        # Get time ranges
        today = timezone.now().date()
        week_ago = timezone.now() - timezone.timedelta(days=7)
        month_ago = timezone.now() - timezone.timedelta(days=30)
        
        # User's activity stats
        user_activities = ActivityFeed.objects.filter(user=user)
        user_posts = SocialFeedPost.objects.filter(user=user)
        
        # Friend activity stats
        friends = Friendship.get_friends(user)
        friend_ids = list(friends.values_list('id', flat=True))
        
        friend_activities = ActivityFeed.objects.filter(
            user_id__in=friend_ids,
            is_public=True
        )
        
        # Interaction stats
        user_interactions = ActivityInteraction.objects.filter(user=user)
        received_interactions = ActivityInteraction.objects.filter(
            activity__user=user
        )
        
        stats = {
            'user_stats': {
                'total_activities': user_activities.count(),
                'activities_this_week': user_activities.filter(created_at__gte=week_ago).count(),
                'activities_this_month': user_activities.filter(created_at__gte=month_ago).count(),
                'total_posts': user_posts.count(),
                'posts_this_week': user_posts.filter(created_at__gte=week_ago).count(),
                'total_points_earned': sum(activity.points_earned for activity in user_activities),
            },
            'social_stats': {
                'friends_count': friends.count(),
                'interactions_given': user_interactions.count(),
                'interactions_received': received_interactions.count(),
                'likes_received': received_interactions.filter(interaction_type='like').count(),
                'comments_received': received_interactions.filter(interaction_type='comment').count(),
                'cheers_received': received_interactions.filter(interaction_type='cheer').count(),
            },
            'feed_stats': {
                'friend_activities_this_week': friend_activities.filter(created_at__gte=week_ago).count(),
                'trending_activities_count': friend_activities.filter(
                    created_at__gte=timezone.now() - timezone.timedelta(hours=24)
                ).annotate(
                    interaction_count=Count('interactions')
                ).filter(interaction_count__gt=2).count(),
            }
        }
        
        # Location stats if enabled
        if hasattr(user, 'location') and user.location.is_location_enabled:
            nearby_users = UserLocation.find_nearby_users(user, radius_km=25)
            stats['location_stats'] = {
                'nearby_users_count': len(nearby_users),
                'location_enabled': True
            }
        else:
            stats['location_stats'] = {
                'nearby_users_count': 0,
                'location_enabled': False
            }
        
        return Response(stats)


class ActivityFeedStoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for activity feed stories (24-hour temporary posts)
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ActivityFeedStorySerializer
    pagination_class = ActivityFeedPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['story_type']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Get non-expired stories from friends"""
        user = self.request.user
        
        # Get friends list
        friends = Friendship.get_friends(user)
        friend_ids = list(friends.values_list('id', flat=True))
        friend_ids.append(user.id)  # Include user's own stories
        
        # Get non-expired stories
        return ActivityFeedStory.objects.filter(
            user_id__in=friend_ids,
            expires_at__gt=timezone.now()
        ).select_related('user')
    
    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == 'create':
            return ActivityFeedStoryCreateSerializer
        return ActivityFeedStorySerializer
    
    @action(detail=True, methods=['post'])
    def view_story(self, request, pk=None):
        """Mark story as viewed by current user"""
        story = self.get_object()
        
        # Check if story is visible to user
        if not story.get_visible_to_user(request.user):
            return Response(
                {'error': 'Story not found or expired'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Create or get story view
        story_view, created = StoryView.objects.get_or_create(
            story=story,
            viewer=request.user
        )
        
        return Response({
            'message': 'Story viewed',
            'view_created': created
        })
    
    @action(detail=True, methods=['get'])
    def viewers(self, request, pk=None):
        """Get list of users who viewed this story"""
        story = self.get_object()
        
        # Only story owner can see viewers
        if story.user != request.user:
            return Response(
                {'error': 'You can only see viewers of your own stories'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        viewers = StoryView.objects.filter(story=story).select_related('viewer')
        serializer = StoryViewSerializer(viewers, many=True, context={'request': request})
        
        return Response({
            'story_id': story.id,
            'total_views': story.views_count,
            'viewers': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def my_stories(self, request):
        """Get current user's stories"""
        stories = ActivityFeedStory.objects.filter(
            user=request.user,
            expires_at__gt=timezone.now()
        )
        
        serializer = self.get_serializer(stories, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def cleanup_expired(self, request):
        """Clean up expired stories (admin only)"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Admin access required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        deleted_count = ActivityFeedStory.cleanup_expired_stories()
        return Response({
            'message': f'Cleaned up {deleted_count} expired stories'
        })


class MilestoneViewSet(viewsets.ViewSet):
    """
    ViewSet for milestone celebrations and achievement posts
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def celebrate_milestone(self, request):
        """Create a milestone celebration post"""
        milestone_type = request.data.get('milestone_type')
        milestone_value = request.data.get('milestone_value')
        points_earned = request.data.get('points_earned', 0)
        custom_message = request.data.get('custom_message', '')
        
        if not milestone_type or not milestone_value:
            return Response(
                {'error': 'milestone_type and milestone_value are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create milestone activity
        from .utils import ActivityFeedManager
        activity = ActivityFeedManager.create_milestone_activity(
            user=request.user,
            milestone_type=milestone_type,
            milestone_value=milestone_value,
            points_earned=points_earned
        )
        
        # Create celebration post if custom message provided
        celebration_post = None
        if custom_message:
            celebration_post = SocialFeedPost.objects.create(
                user=request.user,
                post_type='milestone',
                title=f"🎉 {milestone_value} {milestone_type} milestone!",
                content=custom_message,
                is_public=True,
                friends_only=True
            )
        
        response_data = {
            'message': 'Milestone celebration created successfully',
            'activity_id': activity.id if activity else None,
            'celebration_post_id': celebration_post.id if celebration_post else None
        }
        
        return Response(response_data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['post'])
    def celebrate_achievement(self, request):
        """Create an achievement celebration post"""
        achievement_name = request.data.get('achievement_name')
        achievement_description = request.data.get('achievement_description', '')
        points_earned = request.data.get('points_earned', 0)
        custom_message = request.data.get('custom_message', '')
        
        if not achievement_name:
            return Response(
                {'error': 'achievement_name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create achievement activity
        from .utils import ActivityFeedManager
        activity = ActivityFeedManager.create_achievement_activity(
            user=request.user,
            achievement_name=achievement_name,
            achievement_description=achievement_description,
            points_earned=points_earned
        )
        
        # Create celebration post if custom message provided
        celebration_post = None
        if custom_message:
            celebration_post = SocialFeedPost.objects.create(
                user=request.user,
                post_type='achievement',
                title=f"🏆 {achievement_name}",
                content=custom_message,
                is_public=True,
                friends_only=True
            )
        
        response_data = {
            'message': 'Achievement celebration created successfully',
            'activity_id': activity.id if activity else None,
            'celebration_post_id': celebration_post.id if celebration_post else None
        }
        
        return Response(response_data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def recent_milestones(self, request):
        """Get recent milestones and achievements from friends"""
        from friendships.models import Friendship
        
        # Get friends list
        friends = Friendship.get_friends(request.user)
        friend_ids = list(friends.values_list('id', flat=True))
        fnd_ids.append(request.user.id)
        
        # Get recent milestone and achievement activities
        recent_milestones = ActivityFeed.objects.filter(
            user_id__in=friend_ids,
            activity_type__in=['milestone_reached', 'achievement_earned'],
            is_public=True,
            created_at__gte=timezone.now() - timezone.timedelta(days=7)
        ).select_related('user').prefetch_related('interactions')[:20]
        
        serializer = ActivityFeedSerializer(
            recent_milestones, 
            many=True, 
            context={'request': request}
        )
        
        return Response({
            'milestones': serializer.data,
            'count': len(serializer.data)
        })
    
    @action(detail=False, methods=['get'])
    def celebration_posts(self, request):
        """Get celebration posts from friends"""
        from friendships.models import Friendship
        
        # Get friends list
        friends = Friendship.get_friends(request.user)
        friend_ids = list(friends.values_list('id', flat=True))
        friend_ids.append(request.user.id)
        
        # Get celebration posts
        celebration_posts = SocialFeedPost.objects.filter(
            user_id__in=friend_ids,
            post_type__in=['milestone', 'achievement', 'celebration'],
            is_public=True
        ).select_related('user').prefetch_related('photos', 'interactions')[:20]
        
        serializer = SocialFeedPostSerializer(
            celebration_posts, 
            many=True, 
            context={'request': request}
        )
        
        return Response({
            'posts': serializer.data,
            'count': len(serializer.data)
        })


class SocialChallengeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for social challenges
    """
    permission_classes = [IsAuthenticated]
    serializer_class = SocialChallengeSerializer
    pagination_class = ActivityFeedPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description']
    filterset_fields = ['challenge_type', 'status']
    ordering_fields = ['created_at', 'start_date', 'end_date']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Get challenges visible to current user"""
        user = self.request.user
        
        # Get friends list
        friends = Friendship.get_friends(user)
        friend_ids = list(friends.values_list('id', flat=True))
        friend_ids.append(user.id)  # Include user's own challenges
        
        return SocialChallenge.objects.filter(
            creator_id__in=friend_ids
        ).select_related('creator').prefetch_related('participants')
    
    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == 'create':
            return SocialChallengeCreateSerializer
        return SocialChallengeSerializer
    
    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        """Join a challenge"""
        challenge = self.get_object()
        
        # Check if user can join
        if not challenge.can_join():
            return Response(
                {'error': 'Challenge is full or not available for joining'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user is already participating
        if ChallengeParticipation.objects.filter(challenge=challenge, user=request.user).exists():
            return Response(
                {'error': 'You are already participating in this challenge'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create participation
        participation = ChallengeParticipation.objects.create(
            challenge=challenge,
            user=request.user
        )
        
        serializer = ChallengeParticipationSerializer(participation, context={'request': request})
        return Response({
            'message': 'Successfully joined challenge',
            'participation': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def leave(self, request, pk=None):
        """Leave a challenge"""
        challenge = self.get_object()
        
        try:
            participation = ChallengeParticipation.objects.get(
                challenge=challenge,
                user=request.user
            )
            
            # Can't leave if already completed
            if participation.status == 'completed':
                return Response(
                    {'error': 'Cannot leave a completed challenge'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            participation.status = 'dropped_out'
            participation.save()
            
            return Response({'message': 'Successfully left challenge'})
        
        except ChallengeParticipation.DoesNotExist:
            return Response(
                {'error': 'You are not participating in this challenge'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'])
    def update_progress(self, request, pk=None):
        """Update progress in a challenge"""
        challenge = self.get_object()
        progress = request.data.get('progress')
        
        if progress is None:
            return Response(
                {'error': 'Progress value is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            participation = ChallengeParticipation.objects.get(
                challenge=challenge,
                user=request.user,
                status='active'
            )
            
            completed = participation.update_progress(progress)
            
            serializer = ChallengeParticipationSerializer(participation, context={'request': request})
            
            response_data = {
                'message': 'Progress updated',
                'participation': serializer.data
            }
            
            if completed:
                response_data['message'] = 'Challenge completed! Congratulations!'
                response_data['points_earned'] = participation.points_earned
            
            return Response(response_data)
        
        except ChallengeParticipation.DoesNotExist:
            return Response(
                {'error': 'You are not actively participating in this challenge'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['get'])
    def leaderboard(self, request, pk=None):
        """Get challenge leaderboard"""
        challenge = self.get_object()
        
        participants = challenge.get_leaderboard()
        serializer = ChallengeParticipationSerializer(participants, many=True, context={'request': request})
        
        return Response({
            'challenge_id': challenge.id,
            'challenge_title': challenge.title,
            'leaderboard': serializer.data,
            'total_participants': challenge.get_participant_count()
        })
    
    @action(detail=False, methods=['get'])
    def my_challenges(self, request):
        """Get user's challenge participations"""
        participations = ChallengeParticipation.objects.filter(
            user=request.user
        ).select_related('challenge__creator')
        
        active_challenges = []
        completed_challenges = []
        
        for participation in participations:
            challenge_data = SocialChallengeSerializer(
                participation.challenge,
                context={'request': request}
            ).data
            challenge_data['my_participation'] = ChallengeParticipationSerializer(
                participation,
                context={'request': request}
            ).data
            
            if participation.status == 'completed':
                completed_challenges.append(challenge_data)
            else:
                active_challenges.append(challenge_data)
        
        return Response({
            'active_challenges': active_challenges,
            'completed_challenges': completed_challenges,
            'total_active': len(active_challenges),
            'total_completed': len(completed_challenges)
        })


class UserEngagementViewSet(viewsets.ViewSet):
    """
    ViewSet for user engagement metrics and analytics
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def metrics(self, request):
        """Get user's engagement metrics"""
        metrics = UserEngagementMetrics.get_or_create_for_user(request.user)
        
        # Update metrics
        metrics.update_streak()
        metrics.calculate_activity_score()
        metrics.calculate_social_score()
        metrics.save()
        
        serializer = UserEngagementMetricsSerializer(metrics)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def leaderboard(self, request):
        """Get engagement leaderboard among friends"""
        friends = Friendship.get_friends(request.user)
        friend_ids = list(friends.values_list('id', flat=True))
        friend_ids.append(request.user.id)
        
        # Get metrics for friends
        metrics = UserEngagementMetrics.objects.filter(
            user_id__in=friend_ids
        ).select_related('user').order_by('-activity_score')
        
        leaderboard_data = []
        for i, metric in enumerate(metrics, 1):
            leaderboard_data.append({
                'rank': i,
                'user': UserSerializer(metric.user, context={'request': request}).data,
                'activity_score': metric.activity_score,
                'social_score': metric.social_score,
                'current_streak': metric.current_streak_days,
                'longest_streak': metric.longest_streak_days
            })
        
        return Response({
            'leaderboard': leaderboard_data,
            'total_participants': len(leaderboard_data)
        })
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get detailed engagement statistics"""
        user = request.user
        
        # Time ranges
        today = timezone.now().date()
        week_ago = timezone.now() - timezone.timedelta(days=7)
        month_ago = timezone.now() - timezone.timedelta(days=30)
        
        # Daily stats
        daily_activities = ActivityFeed.objects.filter(
            user=user,
            created_at__date=today
        ).count()
        
        daily_posts = SocialFeedPost.objects.filter(
            user=user,
            created_at__date=today
        ).count()
        
        # Weekly stats
        weekly_activities = ActivityFeed.objects.filter(
            user=user,
            created_at__gte=week_ago
        ).count()
        
        weekly_interactions = ActivityInteraction.objects.filter(
            user=user,
            created_at__gte=week_ago
        ).count()
        
        # Monthly stats
        monthly_activities = ActivityFeed.objects.filter(
            user=user,
            created_at__gte=month_ago
        ).count()
        
        monthly_posts = SocialFeedPost.objects.filter(
            user=user,
            created_at__gte=month_ago
        ).count()
        
        # Top interacting friends
        top_friends = ActivityInteraction.objects.filter(
            activity__user=user,
            created_at__gte=month_ago
        ).values('user__id', 'user__phone_number').annotate(
            interaction_count=Count('id')
        ).order_by('-interaction_count')[:5]
        
        # Recent interactions
        recent_interactions = ActivityInteraction.objects.filter(
            activity__user=user,
            created_at__gte=week_ago
        ).select_related('user', 'activity').order_by('-created_at')[:10]
        
        recent_interactions_data = []
        for interaction in recent_interactions:
            recent_interactions_data.append({
                'user': UserSerializer(interaction.user, context={'request': request}).data,
                'interaction_type': interaction.interaction_type,
                'activity_title': interaction.activity.title,
                'created_at': interaction.created_at
            })
        
        stats = {
            'daily_stats': {
                'activities': daily_activities,
                'posts': daily_posts
            },
            'weekly_stats': {
                'activities': weekly_activities,
                'interactions_given': weekly_interactions
            },
            'monthly_stats': {
                'activities': monthly_activities,
                'posts': monthly_posts
            },
            'top_friends': list(top_friends),
            'recent_interactions': recent_interactions_data
        }
        
        return Response(stats)


class MilestoneAchievementViewSet(viewsets.ViewSet):
    """
    ViewSet for creating milestone celebrations and achievement posts
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def create_milestone_celebration(self, request):
        """Create a milestone celebration post"""
        milestone_type = request.data.get('milestone_type')
        milestone_value = request.data.get('milestone_value')
        custom_message = request.data.get('custom_message', '')
        photos = request.FILES.getlist('photos', [])
        
        if not milestone_type or not milestone_value:
            return Response(
                {'error': 'milestone_type and milestone_value are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create milestone activity
        from .utils import ActivityFeedManager
        activity = ActivityFeedManager.create_milestone_activity(
            user=request.user,
            milestone_type=milestone_type,
            milestone_value=milestone_value,
            points_earned=50  # Bonus points for sharing milestone
        )
        
        # Create celebration post
        celebration_post = SocialFeedPost.objects.create(
            user=request.user,
            post_type='milestone',
            title=f"🎉 {milestone_value} {milestone_type} milestone reached!",
            content=custom_message or f"Just hit {milestone_value} {milestone_type}! Feeling accomplished! 💪",
            related_achievement_id=activity.id if activity else None
        )
        
        # Add photos if provided
        if photos:
            from .utils import PhotoManager
            PhotoManager.process_social_post_photos(celebration_post, photos)
        
        serializer = SocialFeedPostSerializer(celebration_post, context={'request': request})
        return Response({
            'message': 'Milestone celebration created successfully',
            'post': serializer.data
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['post'])
    def create_achievement_celebration(self, request):
        """Create an achievement celebration post"""
        achievement_name = request.data.get('achievement_name')
        achievement_description = request.data.get('achievement_description', '')
        custom_message = request.data.get('custom_message', '')
        photos = request.FILES.getlist('photos', [])
        
        if not achievement_name:
            return Response(
                {'error': 'achievement_name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create achievement activity
        from .utils import ActivityFeedManager
        activity = ActivityFeedManager.create_achievement_activity(
            user=request.user,
            achievement_name=achievement_name,
            achievement_description=achievement_description,
            points_earned=100  # Bonus points for sharing achievement
        )
        
        # Create celebration post
        celebration_post = SocialFeedPost.objects.create(
            user=request.user,
            post_type='achievement',
            title=f"🏆 Achievement Unlocked: {achievement_name}",
            content=custom_message or f"Just earned the '{achievement_name}' achievement! {achievement_description} 🎯",
            related_achievement_id=activity.id if activity else None
        )
        
        # Add photos if provided
        if photos:
            from .utils import PhotoManager
            PhotoManager.process_social_post_photos(celebration_post, photos)
        
        serializer = SocialFeedPostSerializer(celebration_post, context={'request': request})
        return Response({
            'message': 'Achievement celebration created successfully',
            'post': serializer.data
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['post'])
    def create_celebration_post(self, request):
        """Create a general celebration post"""
        title = request.data.get('title')
        content = request.data.get('content')
        celebration_type = request.data.get('celebration_type', 'general')  # general, workout, goal, etc.
        photos = request.FILES.getlist('photos', [])
        
        if not title and not content:
            return Response(
                {'error': 'Either title or content is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create celebration post
        celebration_post = SocialFeedPost.objects.create(
            user=request.user,
            post_type='celebration',
            title=title or f"🎉 Celebrating {celebration_type}!",
            content=content or "Feeling great about this accomplishment!"
        )
        
        # Add photos if provided
        if photos:
            from .utils import PhotoManager
            PhotoManager.process_social_post_photos(celebration_post, photos)
        
        # Also create activity feed entry
        ActivityFeed.objects.create(
            user=request.user,
            activity_type='celebration',
            title=celebration_post.title,
            description=celebration_post.content[:200],
            content={
                'celebration_type': celebration_type,
                'post_id': celebration_post.id
            }
        )
        
        serializer = SocialFeedPostSerializer(celebration_post, context={'request': request})
        return Response({
            'message': 'Celebration post created successfully',
            'post': serializer.data
        }, status=status.HTTP_201_CREATED)


class SocialInteractionViewSet(viewsets.ViewSet):
    """
    ViewSet for managing social interactions across activities and posts
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def bulk_interact(self, request):
        """Perform bulk interactions (like multiple posts at once)"""
        interactions = request.data.get('interactions', [])
        
        if not interactions:
            return Response(
                {'error': 'interactions list is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        results = []
        
        with transaction.atomic():
            for interaction_data in interactions:
                content_type = interaction_data.get('content_type')  # 'activity' or 'post'
                content_id = interaction_data.get('content_id')
                interaction_type = interaction_data.get('interaction_type')
                comment_text = interaction_data.get('comment_text', '')
                
                try:
                    if content_type == 'activity':
                        activity = ActivityFeed.objects.get(id=content_id)
                        if activity.get_visible_to_user(request.user):
                            # Remove existing non-comment interactions
                            if interaction_type != 'comment':
                                ActivityInteraction.objects.filter(
                                    activity=activity,
                                    user=request.user,
                                    interaction_type=interaction_type
                                ).delete()
                            
                            # Create new interaction
                            interaction = ActivityInteraction.objects.create(
                                activity=activity,
                                user=request.user,
                                interaction_type=interaction_type,
                                comment_text=comment_text
                            )
                            
                            results.append({
                                'content_type': content_type,
                                'content_id': content_id,
                                'interaction_type': interaction_type,
                                'status': 'success'
                            })
                        else:
                            results.append({
                                'content_type': content_type,
                                'content_id': content_id,
                                'status': 'error',
                                'message': 'Permission denied'
                            })
                    
                    elif content_type == 'post':
                        post = SocialFeedPost.objects.get(id=content_id)
                        if post.get_visible_to_user(request.user):
                            # Remove existing non-comment reactions
                            if interaction_type != 'comment':
                                SocialPostInteraction.objects.filter(
                                    post=post,
                                    user=request.user
                                ).exclude(interaction_type='comment').delete()
                            
                            # Create new interaction
                            interaction = SocialPostInteraction.objects.create(
                                post=post,
                                user=request.user,
                                interaction_type=interaction_type,
                                comment_text=comment_text
                            )
                            
                            results.append({
                                'content_type': content_type,
                                'content_id': content_id,
                                'interaction_type': interaction_type,
                                'status': 'success'
                            })
                        else:
                            results.append({
                                'content_type': content_type,
                                'content_id': content_id,
                                'status': 'error',
                                'message': 'Permission denied'
                            })
                    
                except (ActivityFeed.DoesNotExist, SocialFeedPost.DoesNotExist):
                    results.append({
                        'content_type': content_type,
                        'content_id': content_id,
                        'status': 'error',
                        'message': 'Content not found'
                    })
                
                except Exception as e:
                    results.append({
                        'content_type': content_type,
                        'content_id': content_id,
                        'status': 'error',
                        'message': str(e)
                    })
        
        return Response({
            'message': 'Bulk interactions processed',
            'results': results
        })
    
    @action(detail=False, methods=['get'])
    def my_interactions(self, request):
        """Get user's recent interactions"""
        days = int(request.query_params.get('days', 7))
        since_date = timezone.now() - timezone.timedelta(days=days)
        
        # Get activity interactions
        activity_interactions = ActivityInteraction.objects.filter(
            user=request.user,
            created_at__gte=since_date
        ).select_related('activity', 'activity__user')
        
        # Get post interactions
        post_interactions = SocialPostInteraction.objects.filter(
            user=request.user,
            created_at__gte=since_date
        ).select_related('post', 'post__user')
        
        # Serialize data
        activity_data = []
        for interaction in activity_interactions:
            activity_data.append({
                'id': interaction.id,
                'content_type': 'activity',
                'content_id': interaction.activity.id,
                'content_title': interaction.activity.title,
                'content_author': interaction.activity.user.phone_number,
                'interaction_type': interaction.interaction_type,
                'comment_text': interaction.comment_text,
                'created_at': interaction.created_at
            })
        
        post_data = []
        for interaction in post_interactions:
            post_data.append({
                'id': interaction.id,
                'content_type': 'post',
                'content_id': interaction.post.id,
                'content_title': interaction.post.title,
                'content_author': interaction.post.user.phone_number,
                'interaction_type': interaction.interaction_type,
                'comment_text': interaction.comment_text,
                'created_at': interaction.created_at
            })
        
        # Combine and sort by date
        all_interactions = activity_data + post_data
        all_interactions.sort(key=lambda x: x['created_at'], reverse=True)
        
        return Response({
            'interactions': all_interactions,
            'total_count': len(all_interactions),
            'period_days': days
        })
    
    @action(detail=False, methods=['get'])
    def interaction_stats(self, request):
        """Get user's interaction statistics"""
        days = int(request.query_params.get('days', 30))
        since_date = timezone.now() - timezone.timedelta(days=days)
        
        # Interactions given
        activity_interactions_given = ActivityInteraction.objects.filter(
            user=request.user,
            created_at__gte=since_date
        )
        
        post_interactions_given = SocialPostInteraction.objects.filter(
            user=request.user,
            created_at__gte=since_date
        )
        
        # Interactions received
        activity_interactions_received = ActivityInteraction.objects.filter(
            activity__user=request.user,
            created_at__gte=since_date
        )
        
        post_interactions_received = SocialPostInteraction.objects.filter(
            post__user=request.user,
            created_at__gte=since_date
        )
        
        stats = {
            'given': {
                'total': activity_interactions_given.count() + post_interactions_given.count(),
                'likes': (activity_interactions_given.filter(interaction_type='like').count() + 
                         post_interactions_given.filter(interaction_type='like').count()),
                'comments': (activity_interactions_given.filter(interaction_type='comment').count() + 
                           post_interactions_given.filter(interaction_type='comment').count()),
                'cheers': activity_interactions_given.filter(interaction_type='cheer').count(),
                'celebrates': (activity_interactions_given.filter(interaction_type='celebrate').count() + 
                             post_interactions_given.filter(interaction_type='celebrate').count()),
            },
            'received': {
                'total': activity_interactions_received.count() + post_interactions_received.count(),
                'likes': (activity_interactions_received.filter(interaction_type='like').count() + 
                         post_interactions_received.filter(interaction_type='like').count()),
                'comments': (activity_interactions_received.filter(interaction_type='comment').count() + 
                           post_interactions_received.filter(interaction_type='comment').count()),
                'cheers': activity_interactions_received.filter(interaction_type='cheer').count(),
                'celebrates': (activity_interactions_received.filter(interaction_type='celebrate').count() + 
                             post_interactions_received.filter(interaction_type='celebrate').count()),
            },
            'period_days': days
        }
        
        return Response(stats)