from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    ActivityFeed, ActivityInteraction, ActivityFeedSettings, ActivityPhoto,
    UserLocation, NearbyFriendRecommendation, SocialFeedPost, SocialPostPhoto,
    SocialPostInteraction, ActivityFeedStory, StoryView, SocialChallenge,
    ChallengeParticipation, UserEngagementMetrics
)
from user_accounts.serializers import UserSerializer

User = get_user_model()


class ActivityPhotoSerializer(serializers.ModelSerializer):
    """Serializer for activity photos"""
    image_url = serializers.ReadOnlyField()
    
    class Meta:
        model = ActivityPhoto
        fields = ['id', 'image', 'image_url', 'caption', 'order', 'created_at']
        read_only_fields = ['id', 'created_at']


class ActivityInteractionSerializer(serializers.ModelSerializer):
    """Serializer for activity interactions"""
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = ActivityInteraction
        fields = ['id', 'user', 'interaction_type', 'comment_text', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def validate(self, data):
        """Validate interaction data"""
        interaction_type = data.get('interaction_type')
        comment_text = data.get('comment_text', '').strip()
        
        if interaction_type == 'comment' and not comment_text:
            raise serializers.ValidationError("Comment interactions must include comment text")
        
        if interaction_type != 'comment' and comment_text:
            raise serializers.ValidationError("Only comment interactions can include comment text")
        
        return data


class ActivityFeedSerializer(serializers.ModelSerializer):
    """Serializer for activity feed entries"""
    user = UserSerializer(read_only=True)
    photos = ActivityPhotoSerializer(many=True, read_only=True)
    interactions = ActivityInteractionSerializer(many=True, read_only=True)
    age_in_hours = serializers.ReadOnlyField()
    is_recent = serializers.ReadOnlyField()
    
    # Interaction counts
    likes_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    cheers_count = serializers.SerializerMethodField()
    
    # User's interaction status
    user_liked = serializers.SerializerMethodField()
    user_cheered = serializers.SerializerMethodField()
    
    class Meta:
        model = ActivityFeed
        fields = [
            'id', 'user', 'activity_type', 'title', 'description', 'content',
            'is_public', 'points_earned', 'created_at', 'photos', 'interactions',
            'age_in_hours', 'is_recent', 'likes_count', 'comments_count', 'cheers_count',
            'user_liked', 'user_cheered', 'related_task_id', 'related_shared_task_id',
            'related_achievement_id'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_likes_count(self, obj):
        """Get number of likes"""
        return obj.interactions.filter(interaction_type='like').count()
    
    def get_comments_count(self, obj):
        """Get number of comments"""
        return obj.interactions.filter(interaction_type='comment').count()
    
    def get_cheers_count(self, obj):
        """Get number of cheers"""
        return obj.interactions.filter(interaction_type='cheer').count()
    
    def get_user_liked(self, obj):
        """Check if current user liked this activity"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.interactions.filter(
                user=request.user,
                interaction_type='like'
            ).exists()
        return False
    
    def get_user_cheered(self, obj):
        """Check if current user cheered this activity"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.interactions.filter(
                user=request.user,
                interaction_type='cheer'
            ).exists()
        return False


class ActivityFeedCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating activity feed entries"""
    photos = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False,
        allow_empty=True,
        max_length=5  # Maximum 5 photos per activity
    )
    
    class Meta:
        model = ActivityFeed
        fields = [
            'activity_type', 'title', 'description', 'content', 'is_public',
            'points_earned', 'related_task_id', 'related_shared_task_id',
            'related_achievement_id', 'photos'
        ]
    
    def create(self, validated_data):
        """Create activity with photos"""
        photos_data = validated_data.pop('photos', [])
        validated_data['user'] = self.context['request'].user
        
        activity = ActivityFeed.objects.create(**validated_data)
        
        # Create photos
        for i, photo_data in enumerate(photos_data):
            ActivityPhoto.objects.create(
                activity=activity,
                image=photo_data,
                order=i
            )
        
        return activity


class UserLocationSerializer(serializers.ModelSerializer):
    """Serializer for user location"""
    
    class Meta:
        model = UserLocation
        fields = [
            'latitude', 'longitude', 'city', 'country', 'is_location_enabled',
            'location_precision', 'last_updated'
        ]
        read_only_fields = ['last_updated']
    
    def validate(self, data):
        """Validate location data"""
        is_enabled = data.get('is_location_enabled', False)
        precision = data.get('location_precision', 'disabled')
        
        if is_enabled and precision == 'disabled':
            raise serializers.ValidationError(
                "Location precision cannot be 'disabled' when location is enabled"
            )
        
        if precision == 'exact' and not all([data.get('latitude'), data.get('longitude')]):
            raise serializers.ValidationError(
                "Exact location requires latitude and longitude coordinates"
            )
        
        return data


class NearbyFriendRecommendationSerializer(serializers.ModelSerializer):
    """Serializer for nearby friend recommendations"""
    recommended_user = UserSerializer(read_only=True)
    
    class Meta:
        model = NearbyFriendRecommendation
        fields = [
            'id', 'recommended_user', 'distance_km', 'recommendation_score',
            'is_dismissed', 'is_contacted', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'recommendation_score']


class SocialPostPhotoSerializer(serializers.ModelSerializer):
    """Serializer for social post photos"""
    image_url = serializers.ReadOnlyField()
    
    class Meta:
        model = SocialPostPhoto
        fields = ['id', 'image', 'image_url', 'caption', 'order', 'created_at']
        read_only_fields = ['id', 'created_at']


class SocialPostInteractionSerializer(serializers.ModelSerializer):
    """Serializer for social post interactions"""
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = SocialPostInteraction
        fields = ['id', 'user', 'interaction_type', 'comment_text', 'created_at']
        read_only_fields = ['id', 'created_at']


class SocialFeedPostSerializer(serializers.ModelSerializer):
    """Serializer for social feed posts"""
    user = UserSerializer(read_only=True)
    photos = SocialPostPhotoSerializer(many=True, read_only=True)
    interactions = SocialPostInteractionSerializer(many=True, read_only=True)
    
    # Interaction counts (already stored in model)
    reactions_breakdown = serializers.SerializerMethodField()
    user_reaction = serializers.SerializerMethodField()
    
    class Meta:
        model = SocialFeedPost
        fields = [
            'id', 'user', 'post_type', 'title', 'content', 'location_name',
            'latitude', 'longitude', 'is_public', 'friends_only', 'likes_count',
            'comments_count', 'shares_count', 'related_task_id', 'related_achievement_id',
            'created_at', 'updated_at', 'photos', 'interactions', 'reactions_breakdown',
            'user_reaction'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'likes_count', 'comments_count', 'shares_count']
    
    def get_reactions_breakdown(self, obj):
        """Get breakdown of different reaction types"""
        reactions = obj.interactions.exclude(interaction_type='comment').values_list('interaction_type', flat=True)
        breakdown = {}
        for reaction in reactions:
            breakdown[reaction] = breakdown.get(reaction, 0) + 1
        return breakdown
    
    def get_user_reaction(self, obj):
        """Get current user's reaction to this post"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            reaction = obj.interactions.filter(
                user=request.user
            ).exclude(interaction_type='comment').first()
            return reaction.interaction_type if reaction else None
        return None


class SocialFeedPostCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating social feed posts"""
    photos = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False,
        allow_empty=True,
        max_length=10  # Maximum 10 photos per post
    )
    
    photo_captions = serializers.ListField(
        child=serializers.CharField(max_length=200, allow_blank=True),
        write_only=True,
        required=False,
        allow_empty=True
    )
    
    class Meta:
        model = SocialFeedPost
        fields = [
            'post_type', 'title', 'content', 'location_name', 'latitude', 'longitude',
            'is_public', 'friends_only', 'related_task_id', 'related_achievement_id',
            'photos', 'photo_captions'
        ]
    
    def validate(self, data):
        """Validate post data"""
        photos = data.get('photos', [])
        captions = data.get('photo_captions', [])
        
        if len(captions) > len(photos):
            raise serializers.ValidationError("Cannot have more captions than photos")
        
        # Ensure we have content or photos
        if not any([data.get('title'), data.get('content'), photos]):
            raise serializers.ValidationError("Post must have title, content, or photos")
        
        return data
    
    def create(self, validated_data):
        """Create social post with photos"""
        photos_data = validated_data.pop('photos', [])
        photo_captions = validated_data.pop('photo_captions', [])
        validated_data['user'] = self.context['request'].user
        
        post = SocialFeedPost.objects.create(**validated_data)
        
        # Create photos with captions
        for i, photo_data in enumerate(photos_data):
            caption = photo_captions[i] if i < len(photo_captions) else ''
            SocialPostPhoto.objects.create(
                post=post,
                image=photo_data,
                caption=caption,
                order=i
            )
        
        return post


class ActivityFeedSettingsSerializer(serializers.ModelSerializer):
    """Serializer for activity feed settings"""
    
    class Meta:
        model = ActivityFeedSettings
        fields = [
            'show_task_completions', 'show_achievements', 'show_milestones',
            'show_shared_task_activities', 'show_leaderboard_positions',
            'friends_only', 'notify_on_interactions', 'notify_on_friend_activities'
        ]
    
    def update(self, instance, validated_data):
        """Update settings and clear cache"""
        updated_instance = super().update(instance, validated_data)
        
        # Clear user's activity feed cache when settings change
        from .models import ActivityFeedCache
        ActivityFeedCache.clear_user_cache(instance.user)
        
        return updated_instance


class FeedInteractionSerializer(serializers.Serializer):
    """Serializer for feed interactions (like, comment, etc.)"""
    interaction_type = serializers.ChoiceField(
        choices=ActivityInteraction.INTERACTION_TYPES
    )
    comment_text = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True
    )
    
    def validate(self, data):
        """Validate interaction data"""
        interaction_type = data.get('interaction_type')
        comment_text = data.get('comment_text', '').strip()
        
        if interaction_type == 'comment' and not comment_text:
            raise serializers.ValidationError("Comment interactions must include comment text")
        
        if interaction_type != 'comment' and comment_text:
            raise serializers.ValidationError("Only comment interactions can include comment text")
        
        return data


class SocialPostInteractionCreateSerializer(serializers.Serializer):
    """Serializer for creating social post interactions"""
    interaction_type = serializers.ChoiceField(
        choices=SocialPostInteraction.INTERACTION_TYPES
    )
    comment_text = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True
    )
    
    def validate(self, data):
        """Validate interaction data"""
        interaction_type = data.get('interaction_type')
        comment_text = data.get('comment_text', '').strip()
        
        if interaction_type == 'comment' and not comment_text:
            raise serializers.ValidationError("Comment interactions must include comment text")
        
        if interaction_type != 'comment' and comment_text:
            data['comment_text'] = ''  # Clear comment text for non-comment interactions
        
        return data


class ActivityFeedStorySerializer(serializers.ModelSerializer):
    """Serializer for activity feed stories"""
    user = UserSerializer(read_only=True)
    time_remaining = serializers.ReadOnlyField()
    is_expired = serializers.ReadOnlyField()
    
    class Meta:
        model = ActivityFeedStory
        fields = [
            'id', 'user', 'story_type', 'content', 'media_file', 'background_color',
            'location_name', 'latitude', 'longitude', 'views_count', 'related_task_id',
            'related_achievement_id', 'created_at', 'expires_at', 'time_remaining', 'is_expired'
        ]
        read_only_fields = ['id', 'created_at', 'expires_at', 'views_count']


class ActivityFeedStoryCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating activity feed stories"""
    
    class Meta:
        model = ActivityFeedStory
        fields = [
            'story_type', 'content', 'media_file', 'background_color',
            'location_name', 'latitude', 'longitude', 'related_task_id', 'related_achievement_id'
        ]
    
    def create(self, validated_data):
        """Create story with current user"""
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class StoryViewSerializer(serializers.ModelSerializer):
    """Serializer for story views"""
    viewer = UserSerializer(read_only=True)
    
    class Meta:
        model = StoryView
        fields = ['id', 'viewer', 'viewed_at']
        read_only_fields = ['id', 'viewed_at']


class SocialChallengeSerializer(serializers.ModelSerializer):
    """Serializer for social challenges"""
    creator = UserSerializer(read_only=True)
    participant_count = serializers.SerializerMethodField()
    can_join = serializers.ReadOnlyField()
    is_active = serializers.ReadOnlyField()
    user_participation = serializers.SerializerMethodField()
    
    class Meta:
        model = SocialChallenge
        fields = [
            'id', 'creator', 'title', 'description', 'challenge_type', 'status',
            'target_value', 'duration_days', 'max_participants', 'start_date', 'end_date',
            'winner_points', 'participation_points', 'created_at', 'updated_at',
            'participant_count', 'can_join', 'is_active', 'user_participation'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_participant_count(self, obj):
        return obj.get_participant_count()
    
    def get_user_participation(self, obj):
        """Get current user's participation in this challenge"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            try:
                participation = ChallengeParticipation.objects.get(
                    challenge=obj,
                    user=request.user
                )
                return ChallengeParticipationSerializer(participation).data
            except ChallengeParticipation.DoesNotExist:
                return None
        return None


class SocialChallengeCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating social challenges"""
    
    class Meta:
        model = SocialChallenge
        fields = [
            'title', 'description', 'challenge_type', 'target_value', 'duration_days',
            'max_participants', 'start_date', 'end_date', 'winner_points', 'participation_points'
        ]
    
    def validate(self, data):
        """Validate challenge data"""
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if start_date and end_date and start_date >= end_date:
            raise serializers.ValidationError("End date must be after start date")
        
        if start_date and start_date <= timezone.now():
            raise serializers.ValidationError("Start date must be in the future")
        
        return data
    
    def create(self, validated_data):
        """Create challenge with current user as creator"""
        validated_data['creator'] = self.context['request'].user
        return super().create(validated_data)


class ChallengeParticipationSerializer(serializers.ModelSerializer):
    """Serializer for challenge participation"""
    user = UserSerializer(read_only=True)
    challenge = SocialChallengeSerializer(read_only=True)
    completion_percentage = serializers.ReadOnlyField()
    rank = serializers.ReadOnlyField()
    
    class Meta:
        model = ChallengeParticipation
        fields = [
            'id', 'user', 'challenge', 'status', 'current_progress', 'completed_at',
            'points_earned', 'joined_at', 'completion_percentage', 'rank'
        ]
        read_only_fields = ['id', 'joined_at', 'completed_at', 'points_earned']


class UserEngagementMetricsSerializer(serializers.ModelSerializer):
    """Serializer for user engagement metrics"""
    
    class Meta:
        model = UserEngagementMetrics
        fields = [
            'total_activities_created', 'total_posts_created', 'total_stories_created',
            'total_likes_given', 'total_likes_received', 'total_comments_given',
            'total_comments_received', 'activity_score', 'social_score',
            'last_activity_date', 'current_streak_days', 'longest_streak_days',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class EngagementStatsSerializer(serializers.Serializer):
    """Serializer for engagement statistics"""
    daily_stats = serializers.DictField()
    weekly_stats = serializers.DictField()
    monthly_stats = serializers.DictField()
    top_friends = serializers.ListField()
    recent_interactions = serializers.ListField()