from django.contrib import admin
from .models import (
    ActivityFeed, ActivityInteraction, ActivityFeedSettings, ActivityPhoto,
    UserLocation, NearbyFriendRecommendation, SocialFeedPost, SocialPostPhoto,
    SocialPostInteraction, ActivityFeedCache
)


class ActivityPhotoInline(admin.TabularInline):
    model = ActivityPhoto
    extra = 0
    readonly_fields = ['image_url']


class ActivityInteractionInline(admin.TabularInline):
    model = ActivityInteraction
    extra = 0
    readonly_fields = ['created_at']


@admin.register(ActivityFeed)
class ActivityFeedAdmin(admin.ModelAdmin):
    list_display = ['user', 'activity_type', 'title', 'points_earned', 'is_public', 'created_at']
    list_filter = ['activity_type', 'is_public', 'created_at']
    search_fields = ['user__phone_number', 'title', 'description']
    readonly_fields = ['created_at', 'age_in_hours', 'is_recent']
    inlines = [ActivityPhotoInline, ActivityInteractionInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'activity_type', 'title', 'description')
        }),
        ('Content', {
            'fields': ('content', 'points_earned')
        }),
        ('Privacy', {
            'fields': ('is_public',)
        }),
        ('Related Objects', {
            'fields': ('related_task_id', 'related_shared_task_id', 'related_achievement_id'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'age_in_hours', 'is_recent'),
            'classes': ('collapse',)
        })
    )


@admin.register(ActivityInteraction)
class ActivityInteractionAdmin(admin.ModelAdmin):
    list_display = ['user', 'activity', 'interaction_type', 'created_at']
    list_filter = ['interaction_type', 'created_at']
    search_fields = ['user__phone_number', 'activity__title', 'comment_text']
    readonly_fields = ['created_at']


@admin.register(UserLocation)
class UserLocationAdmin(admin.ModelAdmin):
    list_display = ['user', 'city', 'country', 'is_location_enabled', 'location_precision', 'last_updated']
    list_filter = ['is_location_enabled', 'location_precision', 'country']
    search_fields = ['user__phone_number', 'city', 'country']
    readonly_fields = ['last_updated']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Location Data', {
            'fields': ('latitude', 'longitude', 'city', 'country')
        }),
        ('Privacy Settings', {
            'fields': ('is_location_enabled', 'location_precision')
        }),
        ('Timestamps', {
            'fields': ('last_updated',)
        })
    )


@admin.register(NearbyFriendRecommendation)
class NearbyFriendRecommendationAdmin(admin.ModelAdmin):
    list_display = ['user', 'recommended_user', 'distance_km', 'recommendation_score', 'is_dismissed', 'created_at']
    list_filter = ['is_dismissed', 'is_contacted', 'created_at']
    search_fields = ['user__phone_number', 'recommended_user__phone_number']
    readonly_fields = ['created_at', 'updated_at', 'recommendation_score']
    
    actions = ['recalculate_scores']
    
    def recalculate_scores(self, request, queryset):
        """Recalculate recommendation scores for selected recommendations"""
        for recommendation in queryset:
            recommendation.calculate_recommendation_score()
            recommendation.save(update_fields=['recommendation_score'])
        
        self.message_user(request, f"Recalculated scores for {queryset.count()} recommendations")
    
    recalculate_scores.short_description = "Recalculate recommendation scores"


class SocialPostPhotoInline(admin.TabularInline):
    model = SocialPostPhoto
    extra = 0
    readonly_fields = ['image_url']


class SocialPostInteractionInline(admin.TabularInline):
    model = SocialPostInteraction
    extra = 0
    readonly_fields = ['created_at']


@admin.register(SocialFeedPost)
class SocialFeedPostAdmin(admin.ModelAdmin):
    list_display = ['user', 'post_type', 'title', 'likes_count', 'comments_count', 'is_public', 'created_at']
    list_filter = ['post_type', 'is_public', 'friends_only', 'created_at']
    search_fields = ['user__phone_number', 'title', 'content', 'location_name']
    readonly_fields = ['created_at', 'updated_at', 'likes_count', 'comments_count', 'shares_count']
    inlines = [SocialPostPhotoInline, SocialPostInteractionInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'post_type', 'title', 'content')
        }),
        ('Location', {
            'fields': ('location_name', 'latitude', 'longitude'),
            'classes': ('collapse',)
        }),
        ('Privacy', {
            'fields': ('is_public', 'friends_only')
        }),
        ('Related Objects', {
            'fields': ('related_task_id', 'related_achievement_id'),
            'classes': ('collapse',)
        }),
        ('Engagement', {
            'fields': ('likes_count', 'comments_count', 'shares_count'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(SocialPostInteraction)
class SocialPostInteractionAdmin(admin.ModelAdmin):
    list_display = ['user', 'post', 'interaction_type', 'created_at']
    list_filter = ['interaction_type', 'created_at']
    search_fields = ['user__phone_number', 'post__title', 'comment_text']
    readonly_fields = ['created_at']


@admin.register(ActivityFeedSettings)
class ActivityFeedSettingsAdmin(admin.ModelAdmin):
    list_display = ['user', 'friends_only', 'notify_on_interactions', 'created_at']
    list_filter = ['friends_only', 'notify_on_interactions', 'notify_on_friend_activities']
    search_fields = ['user__phone_number']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Visibility Settings', {
            'fields': (
                'show_task_completions', 'show_achievements', 'show_milestones',
                'show_shared_task_activities', 'show_leaderboard_positions'
            )
        }),
        ('Privacy Settings', {
            'fields': ('friends_only',)
        }),
        ('Notification Settings', {
            'fields': ('notify_on_interactions', 'notify_on_friend_activities')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(ActivityFeedCache)
class ActivityFeedCacheAdmin(admin.ModelAdmin):
    list_display = ['user', 'cache_key', 'expires_at', 'is_expired', 'created_at']
    list_filter = ['expires_at', 'created_at']
    search_fields = ['user__phone_number', 'cache_key']
    readonly_fields = ['created_at', 'is_expired']
    
    actions = ['clear_expired_cache']
    
    def clear_expired_cache(self, request, queryset):
        """Clear expired cache entries"""
        expired_count = ActivityFeedCache.cleanup_expired_cache()
        self.message_user(request, f"Cleared {expired_count} expired cache entries")
    
    clear_expired_cache.short_description = "Clear expired cache entries"


# Register photo models separately for easier management
@admin.register(ActivityPhoto)
class ActivityPhotoAdmin(admin.ModelAdmin):
    list_display = ['activity', 'caption', 'order', 'created_at']
    list_filter = ['created_at']
    search_fields = ['activity__title', 'caption']
    readonly_fields = ['created_at', 'image_url']


@admin.register(SocialPostPhoto)
class SocialPostPhotoAdmin(admin.ModelAdmin):
    list_display = ['post', 'caption', 'order', 'created_at']
    list_filter = ['created_at']
    search_fields = ['post__title', 'caption']
    readonly_fields = ['created_at', 'image_url']