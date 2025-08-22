from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid
import os

User = get_user_model()


def activity_photo_upload_path(instance, filename):
    """Generate upload path for activity photos"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('activity_photos', str(instance.activity.user.id), filename)


class UserLocation(models.Model):
    """
    Model for storing user location data for nearby friend recommendations
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='location',
        help_text="User this location belongs to"
    )
    
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="User's latitude coordinate"
    )
    
    longitude = models.DecimalField(
        max_digits=11,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="User's longitude coordinate"
    )
    
    city = models.CharField(
        max_length=100,
        blank=True,
        help_text="User's city"
    )
    
    country = models.CharField(
        max_length=100,
        blank=True,
        help_text="User's country"
    )
    
    is_location_enabled = models.BooleanField(
        default=False,
        help_text="Whether user has enabled location sharing"
    )
    
    location_precision = models.CharField(
        max_length=20,
        choices=[
            ('exact', 'Exact Location'),
            ('city', 'City Level'),
            ('country', 'Country Level'),
            ('disabled', 'Disabled'),
        ],
        default='city',
        help_text="Level of location precision to share"
    )
    
    last_updated = models.DateTimeField(
        auto_now=True,
        help_text="When location was last updated"
    )
    
    class Meta:
        db_table = 'social_feed_user_location'
        verbose_name = 'User Location'
        verbose_name_plural = 'User Locations'
        indexes = [
            models.Index(fields=['latitude', 'longitude']),
            models.Index(fields=['city', 'country']),
            models.Index(fields=['is_location_enabled']),
        ]
    
    def __str__(self):
        return f"Location for {self.user.phone_number}"
    
    def calculate_distance_to(self, other_location):
        """Calculate distance to another location in kilometers using Haversine formula"""
        if not all([self.latitude, self.longitude, other_location.latitude, other_location.longitude]):
            return None
        
        import math
        
        # Convert to radians
        lat1, lon1 = math.radians(float(self.latitude)), math.radians(float(self.longitude))
        lat2, lon2 = math.radians(float(other_location.latitude)), math.radians(float(other_location.longitude))
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # Earth's radius in kilometers
        r = 6371
        
        return c * r
    
    @classmethod
    def find_nearby_users(cls, user, radius_km=50, max_results=20):
        """Find users within specified radius"""
        if not hasattr(user, 'location') or not user.location.is_location_enabled:
            return User.objects.none()
        
        user_location = user.location
        if not all([user_location.latitude, user_location.longitude]):
            return User.objects.none()
        
        # Get all users with location enabled
        nearby_locations = cls.objects.filter(
            is_location_enabled=True,
            latitude__isnull=False,
            longitude__isnull=False
        ).exclude(user=user).select_related('user')
        
        nearby_users = []
        for location in nearby_locations:
            distance = user_location.calculate_distance_to(location)
            if distance and distance <= radius_km:
                nearby_users.append((location.user, distance))
        
        # Sort by distance and limit results
        nearby_users.sort(key=lambda x: x[1])
        return [user_data[0] for user_data in nearby_users[:max_results]]


class ActivityPhoto(models.Model):
    """
    Model for storing photos attached to activity feed entries
    """
    activity = models.ForeignKey(
        'ActivityFeed',
        on_delete=models.CASCADE,
        related_name='photos',
        help_text="Activity this photo belongs to"
    )
    
    image = models.ImageField(
        upload_to=activity_photo_upload_path,
        help_text="Photo image file"
    )
    
    caption = models.CharField(
        max_length=200,
        blank=True,
        help_text="Photo caption"
    )
    
    order = models.PositiveIntegerField(
        default=0,
        help_text="Display order for multiple photos"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'social_feed_activity_photo'
        verbose_name = 'Activity Photo'
        verbose_name_plural = 'Activity Photos'
        ordering = ['order', 'created_at']
        indexes = [
            models.Index(fields=['activity', 'order']),
        ]
    
    def __str__(self):
        return f"Photo for {self.activity.title}"
    
    @property
    def image_url(self):
        """Get the URL for this image"""
        if self.image:
            return self.image.url
        return None


class ActivityFeed(models.Model):
    """
    Model for storing user activities that appear in the social feed
    """
    ACTIVITY_TYPES = [
        ('task_completed', 'Task Completed'),
        ('achievement_earned', 'Achievement Earned'),
        ('shared_task_completed', 'Shared Task Completed'),
        ('milestone_reached', 'Milestone Reached'),
        ('shared_task_created', 'Shared Task Created'),
        ('friend_joined', 'Friend Joined'),
        ('streak_achieved', 'Streak Achieved'),
        ('leaderboard_position', 'Leaderboard Position'),
        ('photo_shared', 'Photo Shared'),
        ('celebration', 'Celebration'),
        ('workout_completed', 'Workout Completed'),
        ('goal_achieved', 'Goal Achieved'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='activities',
        help_text="User who performed the activity"
    )
    
    activity_type = models.CharField(
        max_length=30,
        choices=ACTIVITY_TYPES,
        help_text="Type of activity performed"
    )
    
    title = models.CharField(
        max_length=200,
        help_text="Activity title for display"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Detailed description of the activity"
    )
    
    content = models.JSONField(
        default=dict,
        help_text="Flexible content storage for activity-specific data"
    )
    
    is_public = models.BooleanField(
        default=True,
        help_text="Whether this activity is visible to friends"
    )
    
    points_earned = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Points earned from this activity"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the activity was created"
    )
    
    # Related object references (optional, for linking back to source objects)
    related_task_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="ID of related task if applicable"
    )
    
    related_shared_task_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="ID of related shared task if applicable"
    )
    
    related_achievement_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="ID of related achievement if applicable"
    )
    
    class Meta:
        db_table = 'social_feed_activity_feed'
        verbose_name = 'Activity Feed Entry'
        verbose_name_plural = 'Activity Feed Entries'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['activity_type', 'created_at']),
            models.Index(fields=['is_public', 'created_at']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.phone_number} - {self.get_activity_type_display()}: {self.title}"
    
    @property
    def age_in_hours(self):
        """Get the age of this activity in hours"""
        return (timezone.now() - self.created_at).total_seconds() / 3600
    
    @property
    def is_recent(self):
        """Check if this activity is recent (within 24 hours)"""
        return self.age_in_hours <= 24
    
    def get_visible_to_user(self, requesting_user):
        """
        Check if this activity should be visible to the requesting user
        """
        # Activity is visible if:
        # 1. It's public AND
        # 2. The requesting user is friends with the activity user OR it's their own activity
        if not self.is_public:
            return self.user == requesting_user
        
        if self.user == requesting_user:
            return True
        
        # Check if users are friends
        from friendships.models import Friendship
        return Friendship.are_friends(requesting_user, self.user)


class ActivityInteraction(models.Model):
    """
    Model for storing interactions with activity feed entries (likes, comments, cheers)
    """
    INTERACTION_TYPES = [
        ('like', 'Like'),
        ('comment', 'Comment'),
        ('cheer', 'Cheer'),
        ('celebrate', 'Celebrate'),
        ('fire', 'Fire'),
    ]
    
    activity = models.ForeignKey(
        ActivityFeed,
        on_delete=models.CASCADE,
        related_name='interactions',
        help_text="Activity being interacted with"
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='activity_interactions',
        help_text="User performing the interaction"
    )
    
    interaction_type = models.CharField(
        max_length=20,
        choices=INTERACTION_TYPES,
        help_text="Type of interaction"
    )
    
    comment_text = models.TextField(
        blank=True,
        max_length=500,
        help_text="Comment text (for comment interactions)"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the interaction was created"
    )
    
    class Meta:
        db_table = 'social_feed_activity_interaction'
        verbose_name = 'Activity Interaction'
        verbose_name_plural = 'Activity Interactions'
        unique_together = ('activity', 'user', 'interaction_type')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['activity', 'interaction_type']),
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        if self.interaction_type == 'comment':
            return f"{self.user.phone_number} commented on {self.activity.title}"
        else:
            return f"{self.user.phone_number} {self.interaction_type}d {self.activity.title}"
    
    def clean(self):
        """Validate interaction data"""
        from django.core.exceptions import ValidationError
        
        # Comment interactions must have comment text
        if self.interaction_type == 'comment' and not self.comment_text.strip():
            raise ValidationError("Comment interactions must include comment text")
        
        # Non-comment interactions should not have comment text
        if self.interaction_type != 'comment' and self.comment_text.strip():
            raise ValidationError("Only comment interactions can include comment text")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class ActivityFeedSettings(models.Model):
    """
    Model for storing user preferences for activity feed visibility and notifications
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='activity_feed_settings',
        help_text="User these settings belong to"
    )
    
    # Visibility settings
    show_task_completions = models.BooleanField(
        default=True,
        help_text="Show when user completes tasks"
    )
    
    show_achievements = models.BooleanField(
        default=True,
        help_text="Show when user earns achievements"
    )
    
    show_milestones = models.BooleanField(
        default=True,
        help_text="Show when user reaches point milestones"
    )
    
    show_shared_task_activities = models.BooleanField(
        default=True,
        help_text="Show shared task related activities"
    )
    
    show_leaderboard_positions = models.BooleanField(
        default=True,
        help_text="Show when user achieves high leaderboard positions"
    )
    
    # Privacy settings
    friends_only = models.BooleanField(
        default=True,
        help_text="Only show activities to friends"
    )
    
    # Notification settings
    notify_on_interactions = models.BooleanField(
        default=True,
        help_text="Send notifications when friends interact with activities"
    )
    
    notify_on_friend_activities = models.BooleanField(
        default=True,
        help_text="Send notifications for friend activities"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'social_feed_activity_feed_settings'
        verbose_name = 'Activity Feed Settings'
        verbose_name_plural = 'Activity Feed Settings'
    
    def __str__(self):
        return f"Activity Feed Settings for {self.user.phone_number}"
    
    @classmethod
    def get_or_create_for_user(cls, user):
        """Get or create activity feed settings for a user"""
        settings, created = cls.objects.get_or_create(
            user=user,
            defaults={
                'show_task_completions': True,
                'show_achievements': True,
                'show_milestones': True,
                'show_shared_task_activities': True,
                'show_leaderboard_positions': True,
                'friends_only': True,
                'notify_on_interactions': True,
                'notify_on_friend_activities': True,
            }
        )
        return settings


class ActivityFeedCache(models.Model):
    """
    Model for caching computed activity feed data to improve performance
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='activity_feed_cache',
        help_text="User this cache belongs to"
    )
    
    cache_key = models.CharField(
        max_length=100,
        help_text="Cache key identifier"
    )
    
    cache_data = models.JSONField(
        help_text="Cached activity feed data"
    )
    
    expires_at = models.DateTimeField(
        help_text="When this cache entry expires"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'social_feed_activity_feed_cache'
        verbose_name = 'Activity Feed Cache'
        verbose_name_plural = 'Activity Feed Cache'
        unique_together = ('user', 'cache_key')
        indexes = [
            models.Index(fields=['user', 'cache_key']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Cache for {self.user.phone_number}: {self.cache_key}"
    
    @property
    def is_expired(self):
        """Check if this cache entry has expired"""
        return timezone.now() > self.expires_at
    
    @classmethod
    def get_cached_data(cls, user, cache_key):
        """Get cached data if it exists and hasn't expired"""
        try:
            cache_entry = cls.objects.get(user=user, cache_key=cache_key)
            if not cache_entry.is_expired:
                return cache_entry.cache_data
            else:
                # Delete expired cache
                cache_entry.delete()
                return None
        except cls.DoesNotExist:
            return None
    
    @classmethod
    def set_cached_data(cls, user, cache_key, data, expires_in_minutes=30):
        """Set cached data with expiration"""
        expires_at = timezone.now() + timezone.timedelta(minutes=expires_in_minutes)
        
        cache_entry, created = cls.objects.update_or_create(
            user=user,
            cache_key=cache_key,
            defaults={
                'cache_data': data,
                'expires_at': expires_at
            }
        )
        return cache_entry
    
    @classmethod
    def clear_user_cache(cls, user):
        """Clear all cache entries for a user"""
        cls.objects.filter(user=user).delete()
    
    @classmethod
    def cleanup_expired_cache(cls):
        """Remove all expired cache entries"""
        expired_count = cls.objects.filter(expires_at__lt=timezone.now()).count()
        cls.objects.filter(expires_at__lt=timezone.now()).delete()
        return expired_count


class NearbyFriendRecommendation(models.Model):
    """
    Model for storing nearby friend recommendations based on location
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='nearby_recommendations',
        help_text="User receiving the recommendation"
    )
    
    recommended_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='recommended_to',
        help_text="User being recommended"
    )
    
    distance_km = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="Distance between users in kilometers"
    )
    
    recommendation_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.0,
        help_text="Recommendation score based on various factors"
    )
    
    is_dismissed = models.BooleanField(
        default=False,
        help_text="Whether user has dismissed this recommendation"
    )
    
    is_contacted = models.BooleanField(
        default=False,
        help_text="Whether user has sent friend request to recommended user"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'social_feed_nearby_friend_recommendation'
        verbose_name = 'Nearby Friend Recommendation'
        verbose_name_plural = 'Nearby Friend Recommendations'
        unique_together = ('user', 'recommended_user')
        ordering = ['-recommendation_score', 'distance_km']
        indexes = [
            models.Index(fields=['user', 'is_dismissed']),
            models.Index(fields=['recommendation_score']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Recommend {self.recommended_user.phone_number} to {self.user.phone_number}"
    
    def calculate_recommendation_score(self):
        """Calculate recommendation score based on various factors"""
        score = 100.0  # Base score
        
        # Distance factor (closer = higher score)
        if self.distance_km <= 1:
            score += 50
        elif self.distance_km <= 5:
            score += 30
        elif self.distance_km <= 10:
            score += 20
        elif self.distance_km <= 25:
            score += 10
        
        # Common friends factor
        from friendships.models import Friendship
        user_friends = set(Friendship.get_friends(self.user).values_list('id', flat=True))
        recommended_friends = set(Friendship.get_friends(self.recommended_user).values_list('id', flat=True))
        common_friends = len(user_friends & recommended_friends)
        score += common_friends * 15
        
        # Activity level factor (more active users get higher scores)
        recent_activities = ActivityFeed.objects.filter(
            user=self.recommended_user,
            created_at__gte=timezone.now() - timezone.timedelta(days=7)
        ).count()
        score += min(recent_activities * 2, 20)
        
        # Similar interests factor (based on task categories, achievements, etc.)
        # This could be expanded based on user preferences and task types
        
        self.recommendation_score = min(score, 200.0)  # Cap at 200
        return self.recommendation_score
    
    @classmethod
    def generate_recommendations_for_user(cls, user, force_refresh=False):
        """Generate nearby friend recommendations for a user"""
        if not force_refresh:
            # Check if we have recent recommendations
            recent_recommendations = cls.objects.filter(
                user=user,
                created_at__gte=timezone.now() - timezone.timedelta(hours=6)
            ).exists()
            if recent_recommendations:
                return cls.objects.filter(user=user, is_dismissed=False)
        
        # Clear old recommendations
        cls.objects.filter(user=user).delete()
        
        # Find nearby users
        nearby_users = UserLocation.find_nearby_users(user, radius_km=50, max_results=50)
        
        # Filter out existing friends and blocked users
        from friendships.models import Friendship
        existing_friends = set(Friendship.get_friends(user).values_list('id', flat=True))
        blocked_users = set(Friendship.objects.filter(
            models.Q(requester=user, status='blocked') |
            models.Q(addressee=user, status='blocked')
        ).values_list(
            models.Case(
                models.When(requester=user, then='addressee'),
                default='requester'
            ),
            flat=True
        ))
        
        recommendations = []
        for nearby_user in nearby_users:
            if nearby_user.id not in existing_friends and nearby_user.id not in blocked_users:
                distance = user.location.calculate_distance_to(nearby_user.location)
                if distance:
                    recommendation = cls(
                        user=user,
                        recommended_user=nearby_user,
                        distance_km=distance
                    )
                    recommendation.calculate_recommendation_score()
                    recommendations.append(recommendation)
        
        # Sort by score and create top recommendations
        recommendations.sort(key=lambda x: x.recommendation_score, reverse=True)
        top_recommendations = recommendations[:20]  # Limit to top 20
        
        # Bulk create recommendations
        cls.objects.bulk_create(top_recommendations)
        
        return cls.objects.filter(user=user, is_dismissed=False)


class SocialFeedPost(models.Model):
    """
    Model for user-created social posts (photos, celebrations, achievements)
    """
    POST_TYPES = [
        ('photo', 'Photo Post'),
        ('achievement', 'Achievement Post'),
        ('celebration', 'Celebration Post'),
        ('milestone', 'Milestone Post'),
        ('workout', 'Workout Post'),
        ('goal', 'Goal Post'),
        ('text', 'Text Post'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='social_posts',
        help_text="User who created the post"
    )
    
    post_type = models.CharField(
        max_length=20,
        choices=POST_TYPES,
        default='text',
        help_text="Type of social post"
    )
    
    title = models.CharField(
        max_length=200,
        blank=True,
        help_text="Post title"
    )
    
    content = models.TextField(
        max_length=1000,
        blank=True,
        help_text="Post content/description"
    )
    
    # Location data for posts
    location_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Location name (e.g., 'Central Park, NYC')"
    )
    
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="Post location latitude"
    )
    
    longitude = models.DecimalField(
        max_digits=11,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="Post location longitude"
    )
    
    # Privacy settings
    is_public = models.BooleanField(
        default=True,
        help_text="Whether post is visible to all friends"
    )
    
    friends_only = models.BooleanField(
        default=True,
        help_text="Whether post is visible only to friends"
    )
    
    # Engagement metrics
    likes_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of likes"
    )
    
    comments_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of comments"
    )
    
    shares_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of shares"
    )
    
    # Related objects
    related_task_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="Related task ID if applicable"
    )
    
    related_achievement_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="Related achievement ID if applicable"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'social_feed_social_post'
        verbose_name = 'Social Feed Post'
        verbose_name_plural = 'Social Feed Posts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['post_type', 'created_at']),
            models.Index(fields=['is_public', 'created_at']),
            models.Index(fields=['latitude', 'longitude']),
        ]
    
    def __str__(self):
        return f"{self.user.phone_number} - {self.get_post_type_display()}: {self.title or self.content[:50]}"
    
    def get_visible_to_user(self, requesting_user):
        """Check if this post should be visible to the requesting user"""
        if self.user == requesting_user:
            return True
        
        if not self.is_public:
            return False
        
        if self.friends_only:
            from friendships.models import Friendship
            return Friendship.are_friends(requesting_user, self.user)
        
        return True
    
    def increment_likes(self):
        """Increment likes count"""
        self.likes_count = models.F('likes_count') + 1
        self.save(update_fields=['likes_count'])
    
    def decrement_likes(self):
        """Decrement likes count"""
        self.likes_count = models.F('likes_count') - 1
        self.save(update_fields=['likes_count'])
    
    def increment_comments(self):
        """Increment comments count"""
        self.comments_count = models.F('comments_count') + 1
        self.save(update_fields=['comments_count'])
    
    def decrement_comments(self):
        """Decrement comments count"""
        self.comments_count = models.F('comments_count') - 1
        self.save(update_fields=['comments_count'])


def social_post_photo_upload_path(instance, filename):
    """Generate upload path for social post photos"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('social_posts', str(instance.post.user.id), filename)


class SocialPostPhoto(models.Model):
    """
    Model for photos attached to social posts
    """
    post = models.ForeignKey(
        SocialFeedPost,
        on_delete=models.CASCADE,
        related_name='photos',
        help_text="Post this photo belongs to"
    )
    
    image = models.ImageField(
        upload_to=social_post_photo_upload_path,
        help_text="Photo image file"
    )
    
    caption = models.CharField(
        max_length=200,
        blank=True,
        help_text="Photo caption"
    )
    
    order = models.PositiveIntegerField(
        default=0,
        help_text="Display order for multiple photos"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'social_feed_social_post_photo'
        verbose_name = 'Social Post Photo'
        verbose_name_plural = 'Social Post Photos'
        ordering = ['order', 'created_at']
        indexes = [
            models.Index(fields=['post', 'order']),
        ]
    
    def __str__(self):
        return f"Photo for {self.post.title or 'Post'}"
    
    @property
    def image_url(self):
        """Get the URL for this image"""
        if self.image:
            return self.image.url
        return None


class SocialPostInteraction(models.Model):
    """
    Model for interactions with social posts (likes, comments, shares)
    """
    INTERACTION_TYPES = [
        ('like', 'Like'),
        ('love', 'Love'),
        ('laugh', 'Laugh'),
        ('wow', 'Wow'),
        ('sad', 'Sad'),
        ('angry', 'Angry'),
        ('fire', 'Fire'),
        ('celebrate', 'Celebrate'),
        ('comment', 'Comment'),
        ('share', 'Share'),
    ]
    
    post = models.ForeignKey(
        SocialFeedPost,
        on_delete=models.CASCADE,
        related_name='interactions',
        help_text="Post being interacted with"
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='social_post_interactions',
        help_text="User performing the interaction"
    )
    
    interaction_type = models.CharField(
        max_length=20,
        choices=INTERACTION_TYPES,
        help_text="Type of interaction"
    )
    
    comment_text = models.TextField(
        blank=True,
        max_length=500,
        help_text="Comment text (for comment interactions)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'social_feed_social_post_interaction'
        verbose_name = 'Social Post Interaction'
        verbose_name_plural = 'Social Post Interactions'
        unique_together = ('post', 'user', 'interaction_type')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['post', 'interaction_type']),
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        if self.interaction_type == 'comment':
            return f"{self.user.phone_number} commented on post"
        else:
            return f"{self.user.phone_number} {self.interaction_type}d post"
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Update post interaction counts
        if is_new:
            if self.interaction_type in ['like', 'love', 'laugh', 'wow', 'sad', 'angry', 'fire', 'celebrate']:
                self.post.increment_likes()
            elif self.interaction_type == 'comment':
                self.post.increment_comments()
    
    def delete(self, *args, **kwargs):
        # Update post interaction counts
        if self.interaction_type in ['like', 'love', 'laugh', 'wow', 'sad', 'angry', 'fire', 'celebrate']:
            self.post.decrement_likes()
        elif self.interaction_type == 'comment':
            self.post.decrement_comments()
        
        super().delete(*args, **kwargs)


class ActivityFeedStory(models.Model):
    """
    Model for temporary story-like posts that disappear after 24 hours
    """
    STORY_TYPES = [
        ('photo', 'Photo Story'),
        ('video', 'Video Story'),
        ('text', 'Text Story'),
        ('achievement', 'Achievement Story'),
        ('workout', 'Workout Story'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='stories',
        help_text="User who created the story"
    )
    
    story_type = models.CharField(
        max_length=20,
        choices=STORY_TYPES,
        default='photo',
        help_text="Type of story"
    )
    
    content = models.TextField(
        max_length=500,
        blank=True,
        help_text="Story text content"
    )
    
    media_file = models.FileField(
        upload_to='stories/',
        null=True,
        blank=True,
        help_text="Photo or video file for story"
    )
    
    background_color = models.CharField(
        max_length=7,
        default='#000000',
        help_text="Background color for text stories (hex code)"
    )
    
    # Location data
    location_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Location name for story"
    )
    
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="Story location latitude"
    )
    
    longitude = models.DecimalField(
        max_digits=11,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="Story location longitude"
    )
    
    # Engagement metrics
    views_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of views"
    )
    
    # Related objects
    related_task_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="Related task ID if applicable"
    )
    
    related_achievement_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="Related achievement ID if applicable"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        help_text="When the story expires (24 hours from creation)"
    )
    
    class Meta:
        db_table = 'social_feed_activity_feed_story'
        verbose_name = 'Activity Feed Story'
        verbose_name_plural = 'Activity Feed Stories'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'expires_at']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.phone_number} - {self.get_story_type_display()}"
    
    def save(self, *args, **kwargs):
        # Set expiration time to 24 hours from creation
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(hours=24)
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        """Check if story has expired"""
        return timezone.now() > self.expires_at
    
    @property
    def time_remaining(self):
        """Get time remaining until expiration in seconds"""
        if self.is_expired:
            return 0
        return (self.expires_at - timezone.now()).total_seconds()
    
    def get_visible_to_user(self, requesting_user):
        """Check if story should be visible to requesting user"""
        if self.is_expired:
            return False
        
        if self.user == requesting_user:
            return True
        
        # Check if users are friends
        from friendships.models import Friendship
        return Friendship.are_friends(requesting_user, self.user)
    
    @classmethod
    def cleanup_expired_stories(cls):
        """Remove expired stories"""
        expired_count = cls.objects.filter(expires_at__lt=timezone.now()).count()
        cls.objects.filter(expires_at__lt=timezone.now()).delete()
        return expired_count


class StoryView(models.Model):
    """
    Model for tracking story views
    """
    story = models.ForeignKey(
        ActivityFeedStory,
        on_delete=models.CASCADE,
        related_name='story_views',
        help_text="Story that was viewed"
    )
    
    viewer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='story_views',
        help_text="User who viewed the story"
    )
    
    viewed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'social_feed_story_view'
        verbose_name = 'Story View'
        verbose_name_plural = 'Story Views'
        unique_together = ('story', 'viewer')
        ordering = ['-viewed_at']
        indexes = [
            models.Index(fields=['story', 'viewed_at']),
            models.Index(fields=['viewer', 'viewed_at']),
        ]
    
    def __str__(self):
        return f"{self.viewer.phone_number} viewed {self.story.user.phone_number}'s story"
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Update story views count
        if is_new:
            self.story.views_count = models.F('views_count') + 1
            self.story.save(update_fields=['views_count'])


class SocialChallenge(models.Model):
    """
    Model for social challenges that friends can participate in
    """
    CHALLENGE_TYPES = [
        ('step_count', 'Step Count Challenge'),
        ('workout_streak', 'Workout Streak Challenge'),
        ('task_completion', 'Task Completion Challenge'),
        ('points_race', 'Points Race Challenge'),
        ('custom', 'Custom Challenge'),
    ]
    
    STATUS_CHOICES = [
        ('upcoming', 'Upcoming'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    creator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_challenges',
        help_text="User who created the challenge"
    )
    
    title = models.CharField(
        max_length=200,
        help_text="Challenge title"
    )
    
    description = models.TextField(
        max_length=1000,
        help_text="Challenge description"
    )
    
    challenge_type = models.CharField(
        max_length=20,
        choices=CHALLENGE_TYPES,
        help_text="Type of challenge"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='upcoming',
        help_text="Challenge status"
    )
    
    # Challenge parameters
    target_value = models.PositiveIntegerField(
        help_text="Target value for the challenge (steps, points, etc.)"
    )
    
    duration_days = models.PositiveIntegerField(
        default=7,
        help_text="Challenge duration in days"
    )
    
    max_participants = models.PositiveIntegerField(
        default=20,
        help_text="Maximum number of participants"
    )
    
    # Timing
    start_date = models.DateTimeField(
        help_text="When the challenge starts"
    )
    
    end_date = models.DateTimeField(
        help_text="When the challenge ends"
    )
    
    # Rewards
    winner_points = models.PositiveIntegerField(
        default=100,
        help_text="Points awarded to winner"
    )
    
    participation_points = models.PositiveIntegerField(
        default=25,
        help_text="Points awarded for participation"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'social_feed_social_challenge'
        verbose_name = 'Social Challenge'
        verbose_name_plural = 'Social Challenges'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'start_date']),
            models.Index(fields=['challenge_type', 'status']),
            models.Index(fields=['creator', 'status']),
        ]
    
    def __str__(self):
        return f"{self.title} by {self.creator.phone_number}"
    
    def get_participant_count(self):
        """Get number of participants"""
        return self.participants.count()
    
    def can_join(self):
        """Check if challenge can be joined"""
        return (
            self.status in ['upcoming', 'active'] and
            self.get_participant_count() < self.max_participants
        )
    
    def is_active(self):
        """Check if challenge is currently active"""
        now = timezone.now()
        return (
            self.status == 'active' and
            self.start_date <= now <= self.end_date
        )
    
    def get_leaderboard(self):
        """Get challenge leaderboard"""
        return self.participants.filter(
            status='active'
        ).order_by('-current_progress', 'joined_at')


class ChallengeParticipation(models.Model):
    """
    Model for tracking challenge participation
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('dropped_out', 'Dropped Out'),
    ]
    
    challenge = models.ForeignKey(
        SocialChallenge,
        on_delete=models.CASCADE,
        related_name='participants',
        help_text="Challenge being participated in"
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='challenge_participations',
        help_text="Participating user"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        help_text="Participation status"
    )
    
    current_progress = models.PositiveIntegerField(
        default=0,
        help_text="Current progress towards target"
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When user completed the challenge"
    )
    
    points_earned = models.PositiveIntegerField(
        default=0,
        help_text="Points earned from this challenge"
    )
    
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'social_feed_challenge_participation'
        verbose_name = 'Challenge Participation'
        verbose_name_plural = 'Challenge Participations'
        unique_together = ('challenge', 'user')
        ordering = ['-current_progress', 'joined_at']
        indexes = [
            models.Index(fields=['challenge', 'status']),
            models.Index(fields=['user', 'status']),
        ]
    
    def __str__(self):
        return f"{self.user.phone_number} in {self.challenge.title}"
    
    @property
    def completion_percentage(self):
        """Get completion percentage"""
        if self.challenge.target_value == 0:
            return 0
        return min((self.current_progress / self.challenge.target_value) * 100, 100)
    
    @property
    def rank(self):
        """Get current rank in challenge"""
        better_participants = ChallengeParticipation.objects.filter(
            challenge=self.challenge,
            status='active',
            current_progress__gt=self.current_progress
        ).count()
        return better_participants + 1
    
    def update_progress(self, new_progress):
        """Update progress and check for completion"""
        self.current_progress = new_progress
        
        # Check if challenge is completed
        if new_progress >= self.challenge.target_value and self.status == 'active':
            self.status = 'completed'
            self.completed_at = timezone.now()
            
            # Award points based on completion order
            completed_before = ChallengeParticipation.objects.filter(
                challenge=self.challenge,
                status='completed',
                completed_at__lt=self.completed_at
            ).count()
            
            if completed_before == 0:  # First to complete
                self.points_earned = self.challenge.winner_points
            else:
                self.points_earned = self.challenge.participation_points
        
        self.save()
        return self.status == 'completed'


class UserEngagementMetrics(models.Model):
    """
    Model for tracking user engagement metrics
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='engagement_metrics',
        help_text="User these metrics belong to"
    )
    
    # Activity metrics
    total_activities_created = models.PositiveIntegerField(
        default=0,
        help_text="Total activities created by user"
    )
    
    total_posts_created = models.PositiveIntegerField(
        default=0,
        help_text="Total social posts created by user"
    )
    
    total_stories_created = models.PositiveIntegerField(
        default=0,
        help_text="Total stories created by user"
    )
    
    # Interaction metrics
    total_likes_given = models.PositiveIntegerField(
        default=0,
        help_text="Total likes given by user"
    )
    
    total_likes_received = models.PositiveIntegerField(
        default=0,
        help_text="Total likes received by user"
    )
    
    total_comments_given = models.PositiveIntegerField(
        default=0,
        help_text="Total comments given by user"
    )
    
    total_comments_received = models.PositiveIntegerField(
        default=0,
        help_text="Total comments received by user"
    )
    
    # Engagement scores
    activity_score = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0.0,
        help_text="Overall activity engagement score"
    )
    
    social_score = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0.0,
        help_text="Social interaction engagement score"
    )
    
    # Time-based metrics
    last_activity_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date of last activity"
    )
    
    current_streak_days = models.PositiveIntegerField(
        default=0,
        help_text="Current daily activity streak"
    )
    
    longest_streak_days = models.PositiveIntegerField(
        default=0,
        help_text="Longest daily activity streak"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'social_feed_user_engagement_metrics'
        verbose_name = 'User Engagement Metrics'
        verbose_name_plural = 'User Engagement Metrics'
    
    def __str__(self):
        return f"Engagement metrics for {self.user.phone_number}"
    
    def calculate_activity_score(self):
        """Calculate overall activity engagement score"""
        # Base score from activities and posts
        content_score = (self.total_activities_created * 2) + (self.total_posts_created * 3)
        
        # Interaction score
        interaction_score = (
            (self.total_likes_given * 0.5) + 
            (self.total_comments_given * 1.5) +
            (self.total_likes_received * 1) +
            (self.total_comments_received * 2)
        )
        
        # Streak bonus
        streak_bonus = min(self.current_streak_days * 5, 100)
        
        self.activity_score = content_score + interaction_score + streak_bonus
        return self.activity_score
    
    def calculate_social_score(self):
        """Calculate social interaction engagement score"""
        # Ratio of interactions given vs received
        given_interactions = self.total_likes_given + self.total_comments_given
        received_interactions = self.total_likes_received + self.total_comments_received
        
        if given_interactions == 0:
            interaction_ratio = 0
        else:
            interaction_ratio = min(received_interactions / given_interactions, 2.0)
        
        # Base social score
        base_score = (given_interactions * 0.8) + (received_interactions * 1.2)
        
        # Apply interaction ratio multiplier
        self.social_score = base_score * (1 + interaction_ratio * 0.5)
        return self.social_score
    
    def update_streak(self):
        """Update activity streak based on recent activity"""
        today = timezone.now().date()
        
        # Check if user had activity today
        has_activity_today = (
            ActivityFeed.objects.filter(
                user=self.user,
                created_at__date=today
            ).exists() or
            SocialFeedPost.objects.filter(
                user=self.user,
                created_at__date=today
            ).exists()
        )
        
        if has_activity_today:
            if self.last_activity_date and self.last_activity_date.date() == today - timezone.timedelta(days=1):
                # Continue streak
                self.current_streak_days += 1
            elif not self.last_activity_date or self.last_activity_date.date() < today - timezone.timedelta(days=1):
                # Start new streak
                self.current_streak_days = 1
            
            # Update longest streak
            if self.current_streak_days > self.longest_streak_days:
                self.longest_streak_days = self.current_streak_days
            
            self.last_activity_date = timezone.now()
        else:
            # Check if streak should be broken
            if self.last_activity_date and self.last_activity_date.date() < today - timezone.timedelta(days=1):
                self.current_streak_days = 0
        
        self.save()
    
    @classmethod
    def get_or_create_for_user(cls, user):
        """Get or create engagement metrics for user"""
        metrics, created = cls.objects.get_or_create(
            user=user,
            defaults={
                'total_activities_created': 0,
                'total_posts_created': 0,
                'total_stories_created': 0,
                'total_likes_given': 0,
                'total_likes_received': 0,
                'total_comments_given': 0,
                'total_comments_received': 0,
                'activity_score': 0.0,
                'social_score': 0.0,
                'current_streak_days': 0,
                'longest_streak_days': 0,
            }
        )
        return metrics