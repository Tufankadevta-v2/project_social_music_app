"""
Utility functions for social feed functionality
"""
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import ActivityFeed, ActivityFeedCache, UserLocation
from .signals import (
    handle_task_completion, handle_shared_task_completion, handle_achievement_earned,
    handle_milestone_reached, handle_shared_task_created, handle_friend_joined,
    handle_streak_achieved, handle_leaderboard_position
)

User = get_user_model()


class ActivityFeedManager:
    """Manager class for activity feed operations"""
    
    @staticmethod
    def create_task_completion_activity(task, points_earned):
        """Create activity for task completion"""
        return handle_task_completion(task, points_earned)
    
    @staticmethod
    def create_shared_task_completion_activity(participation):
        """Create activity for shared task completion"""
        return handle_shared_task_completion(participation)
    
    @staticmethod
    def create_achievement_activity(user, achievement_name, achievement_description, points_earned=0):
        """Create activity for achievement earned"""
        return handle_achievement_earned(user, achievement_name, achievement_description, points_earned)
    
    @staticmethod
    def create_milestone_activity(user, milestone_type, milestone_value, points_earned=0):
        """Create activity for milestone reached"""
        return handle_milestone_reached(user, milestone_type, milestone_value, points_earned)
    
    @staticmethod
    def create_shared_task_created_activity(shared_task):
        """Create activity for shared task creation"""
        return handle_shared_task_created(shared_task)
    
    @staticmethod
    def create_friend_joined_activity(user):
        """Create activity for new friend joining"""
        return handle_friend_joined(user)
    
    @staticmethod
    def create_streak_activity(user, streak_length, streak_type='task_completion'):
        """Create activity for streak achievement"""
        return handle_streak_achieved(user, streak_length, streak_type)
    
    @staticmethod
    def create_leaderboard_activity(user, position, leaderboard_type='global', time_period='weekly'):
        """Create activity for leaderboard position"""
        return handle_leaderboard_position(user, position, leaderboard_type, time_period)
    
    @staticmethod
    def get_user_feed(user, page_size=20, page=1):
        """Get paginated activity feed for user"""
        from friendships.models import Friendship
        
        # Check cache first
        cache_key = f"feed_page_{page}_{page_size}"
        cached_data = ActivityFeedCache.get_cached_data(user, cache_key)
        if cached_data:
            return cached_data
        
        # Get friends list
        friends = Friendship.get_friends(user)
        friend_ids = list(friends.values_list('id', flat=True))
        friend_ids.append(user.id)  # Include user's own activities
        
        # Get activities with privacy filtering
        activities = ActivityFeed.objects.filter(
            user_id__in=friend_ids,
            is_public=True
        ).select_related('user').prefetch_related('photos', 'interactions')
        
        # Apply pagination
        start = (page - 1) * page_size
        end = start + page_size
        page_activities = activities[start:end]
        
        # Serialize data
        from .serializers import ActivityFeedSerializer
        serializer = ActivityFeedSerializer(page_activities, many=True, context={'request': None})
        
        # Cache the result
        ActivityFeedCache.set_cached_data(user, cache_key, serializer.data, expires_in_minutes=15)
        
        return serializer.data


class LocationManager:
    """Manager class for location-based operations"""
    
    @staticmethod
    def update_user_location(user, latitude=None, longitude=None, city=None, country=None, 
                           is_enabled=None, precision=None):
        """Update user location"""
        location, created = UserLocation.objects.get_or_create(user=user)
        
        if latitude is not None:
            location.latitude = latitude
        if longitude is not None:
            location.longitude = longitude
        if city is not None:
            location.city = city
        if country is not None:
            location.country = country
        if is_enabled is not None:
            location.is_location_enabled = is_enabled
        if precision is not None:
            location.location_precision = precision
        
        location.save()
        return location
    
    @staticmethod
    def find_nearby_users(user, radius_km=50, max_results=20):
        """Find nearby users"""
        return UserLocation.find_nearby_users(user, radius_km, max_results)
    
    @staticmethod
    def calculate_distance(user1, user2):
        """Calculate distance between two users"""
        if not all([
            hasattr(user1, 'location'), hasattr(user2, 'location'),
            user1.location.is_location_enabled, user2.location.is_location_enabled
        ]):
            return None
        
        return user1.location.calculate_distance_to(user2.location)


class SocialFeedAnalytics:
    """Analytics class for social feed metrics"""
    
    @staticmethod
    def get_user_engagement_stats(user, days=30):
        """Get user engagement statistics"""
        since_date = timezone.now() - timezone.timedelta(days=days)
        
        # User's activities
        user_activities = ActivityFeed.objects.filter(
            user=user,
            created_at__gte=since_date
        )
        
        # Interactions on user's activities
        from .models import ActivityInteraction
        interactions_received = ActivityInteraction.objects.filter(
            activity__user=user,
            created_at__gte=since_date
        )
        
        # Interactions by user
        interactions_given = ActivityInteraction.objects.filter(
            user=user,
            created_at__gte=since_date
        )
        
        return {
            'activities_count': user_activities.count(),
            'total_points_earned': sum(activity.points_earned for activity in user_activities),
            'interactions_received': interactions_received.count(),
            'interactions_given': interactions_given.count(),
            'likes_received': interactions_received.filter(interaction_type='like').count(),
            'comments_received': interactions_received.filter(interaction_type='comment').count(),
            'cheers_received': interactions_received.filter(interaction_type='cheer').count(),
            'engagement_rate': (
                interactions_received.count() / user_activities.count() 
                if user_activities.count() > 0 else 0
            )
        }
    
    @staticmethod
    def get_trending_activities(user, hours=24, limit=10):
        """Get trending activities among user's friends"""
        from friendships.models import Friendship
        from django.db.models import Count
        
        since_time = timezone.now() - timezone.timedelta(hours=hours)
        
        # Get friends list
        friends = Friendship.get_friends(user)
        friend_ids = list(friends.values_list('id', flat=True))
        friend_ids.append(user.id)
        
        # Get activities with most interactions
        trending = ActivityFeed.objects.filter(
            user_id__in=friend_ids,
            is_public=True,
            created_at__gte=since_time
        ).annotate(
            interaction_count=Count('interactions')
        ).filter(
            interaction_count__gt=0
        ).order_by('-interaction_count', '-created_at')[:limit]
        
        return trending
    
    @staticmethod
    def get_friend_activity_summary(user, days=7):
        """Get summary of friend activities"""
        from friendships.models import Friendship
        
        since_date = timezone.now() - timezone.timedelta(days=days)
        
        # Get friends list
        friends = Friendship.get_friends(user)
        friend_ids = list(friends.values_list('id', flat=True))
        
        # Get friend activities
        friend_activities = ActivityFeed.objects.filter(
            user_id__in=friend_ids,
            is_public=True,
            created_at__gte=since_date
        )
        
        # Group by activity type
        activity_summary = {}
        for activity in friend_activities:
            activity_type = activity.get_activity_type_display()
            if activity_type not in activity_summary:
                activity_summary[activity_type] = {
                    'count': 0,
                    'total_points': 0,
                    'users': set()
                }
            
            activity_summary[activity_type]['count'] += 1
            activity_summary[activity_type]['total_points'] += activity.points_earned
            activity_summary[activity_type]['users'].add(activity.user.id)
        
        # Convert sets to counts
        for activity_type in activity_summary:
            activity_summary[activity_type]['unique_users'] = len(activity_summary[activity_type]['users'])
            del activity_summary[activity_type]['users']
        
        return {
            'total_activities': friend_activities.count(),
            'active_friends': friend_activities.values('user').distinct().count(),
            'activity_breakdown': activity_summary
        }


class PhotoManager:
    """Manager class for photo operations"""
    
    @staticmethod
    def process_activity_photos(activity, photo_files):
        """Process and attach photos to activity"""
        from .models import ActivityPhoto
        
        photos = []
        for i, photo_file in enumerate(photo_files):
            photo = ActivityPhoto.objects.create(
                activity=activity,
                image=photo_file,
                order=i
            )
            photos.append(photo)
        
        return photos
    
    @staticmethod
    def process_social_post_photos(post, photo_files, captions=None):
        """Process and attach photos to social post"""
        from .models import SocialPostPhoto
        
        captions = captions or []
        photos = []
        
        for i, photo_file in enumerate(photo_files):
            caption = captions[i] if i < len(captions) else ''
            photo = SocialPostPhoto.objects.create(
                post=post,
                image=photo_file,
                caption=caption,
                order=i
            )
            photos.append(photo)
        
        return photos


def cleanup_old_activities(days_to_keep=90):
    """Clean up old activity feed entries"""
    cutoff_date = timezone.now() - timezone.timedelta(days=days_to_keep)
    
    # Delete old activities
    deleted_count = ActivityFeed.objects.filter(
        created_at__lt=cutoff_date
    ).delete()[0]
    
    # Clean up expired cache
    cache_deleted = ActivityFeedCache.cleanup_expired_cache()
    
    return {
        'activities_deleted': deleted_count,
        'cache_entries_deleted': cache_deleted
    }


def generate_activity_summary_email(user, days=7):
    """Generate email summary of friend activities"""
    analytics = SocialFeedAnalytics()
    friend_summary = analytics.get_friend_activity_summary(user, days)
    user_stats = analytics.get_user_engagement_stats(user, days)
    
    return {
        'user': user,
        'period_days': days,
        'friend_summary': friend_summary,
        'user_stats': user_stats,
        'generated_at': timezone.now()
    }