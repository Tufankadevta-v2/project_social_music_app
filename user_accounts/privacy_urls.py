from django.urls import path
from . import privacy_views

app_name = 'privacy'

urlpatterns = [
    # Main privacy settings
    path('settings/', privacy_views.PrivacySettingsView.as_view(), name='privacy-settings'),
    path('summary/', privacy_views.privacy_summary_view, name='privacy-summary'),
    path('reset/', privacy_views.reset_privacy_settings_view, name='privacy-reset'),
    path('recommendations/', privacy_views.privacy_recommendations_view, name='privacy-recommendations'),
    
    # Friend-specific privacy settings
    path('friends/', privacy_views.FriendPrivacySettingsListView.as_view(), name='friend-privacy-list'),
    path('friends/<int:pk>/', privacy_views.FriendPrivacySettingsDetailView.as_view(), name='friend-privacy-detail'),
    
    # Private task settings
    path('tasks/', privacy_views.PrivateTaskListView.as_view(), name='private-tasks-list'),
    path('tasks/<int:pk>/', privacy_views.PrivateTaskDetailView.as_view(), name='private-tasks-detail'),
    
    # Bulk operations
    path('bulk-update/', privacy_views.BulkPrivacyUpdateView.as_view(), name='bulk-privacy-update'),
    
    # Privacy checking
    path('check/', privacy_views.PrivacyCheckView.as_view(), name='privacy-check'),
]