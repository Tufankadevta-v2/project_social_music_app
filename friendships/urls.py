from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'friendships'

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
    
    # Contact syncing endpoints
    path('sync-contacts/', views.sync_contacts, name='sync_contacts'),
    path('mutual-contacts/', views.get_mutual_contacts, name='mutual_contacts'),
    path('clear-contacts/', views.clear_contacts, name='clear_contacts'),
    
    # Friendship management endpoints
    path('send-request/', views.send_friend_request, name='send_friend_request'),
    path('respond/<int:friendship_id>/', views.respond_to_friend_request, name='respond_to_friend_request'),
    path('friends/', views.get_friends, name='get_friends'),
    path('pending-requests/', views.get_pending_requests, name='pending_requests'),
    
    # Blocking endpoints
    path('block/', views.block_user, name='block_user'),
    path('unblock/', views.unblock_user, name='unblock_user'),
]