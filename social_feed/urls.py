from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ActivityFeedViewSet, SocialFeedPostViewSet, UserLocationViewSet,
    ActivityFeedSettingsViewSet, SocialFeedStatsView, ActivityFeedStoryViewSet,
    SocialChallengeViewSet, UserEngagementViewSet, MilestoneAchievementViewSet,
    SocialInteractionViewSet
)

app_name = 'social_feed'

router = DefaultRouter()
router.register(r'activities', ActivityFeedViewSet, basename='activity-feed')
router.register(r'posts', SocialFeedPostViewSet, basename='social-posts')
router.register(r'stories', ActivityFeedStoryViewSet, basename='feed-stories')
router.register(r'challenges', SocialChallengeViewSet, basename='social-challenges')
router.register(r'location', UserLocationViewSet, basename='user-location')
router.register(r'settings', ActivityFeedSettingsViewSet, basename='feed-settings')
router.register(r'engagement', UserEngagementViewSet, basename='user-engagement')
router.register(r'stats', SocialFeedStatsView, basename='feed-stats')
router.register(r'milestones', MilestoneAchievementViewSet, basename='milestones')
router.register(r'interactions', SocialInteractionViewSet, basename='social-interactions')

urlpatterns = [
    path('', include(router.urls)),
]