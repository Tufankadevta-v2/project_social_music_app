"""
API views for contact syncing and friendship management.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .services import ContactSyncService, FriendshipService
from .serializers import (
    ContactSyncSerializer, 
    FriendRequestSerializer, 
    FriendshipResponseSerializer,
    BlockUserSerializer
)
from user_accounts.privacy_utils import PrivacyChecker
from user_accounts.privacy_models import PrivacySettings

User = get_user_model()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync_contacts(request):
    """
    Sync user's contacts to find mutual connections.
    
    POST /api/friendships/sync-contacts/
    {
        "phone_numbers": ["+1234567890", "+0987654321", ...]
    }
    """
    serializer = ContactSyncSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {'error': 'Invalid data', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    phone_numbers = serializer.validated_data['phone_numbers']
    
    # Sync contacts and find mutual connections
    result = ContactSyncService.sync_contacts(request.user, phone_numbers)
    
    return Response({
        'success': True,
        'data': result
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_mutual_contacts(request):
    """
    Get all mutual contacts for the authenticated user.
    
    GET /api/friendships/mutual-contacts/
    """
    mutual_contacts = ContactSyncService.get_mutual_contacts_for_user(request.user)
    
    return Response({
        'success': True,
        'data': {
            'mutual_contacts': mutual_contacts,
            'count': len(mutual_contacts)
        }
    }, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def clear_contacts(request):
    """
    Clear all synced contacts for the authenticated user.
    
    DELETE /api/friendships/clear-contacts/
    """
    deleted_count = ContactSyncService.clear_user_contacts(request.user)
    
    return Response({
        'success': True,
        'message': f'Cleared {deleted_count} contact hashes',
        'deleted_count': deleted_count
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_friend_request(request):
    """
    Send a friend request to another user.
    
    POST /api/friendships/send-request/
    {
        "addressee_id": 123
    }
    """
    serializer = FriendRequestSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {'error': 'Invalid data', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    addressee_id = serializer.validated_data['addressee_id']
    
    # Check if target user allows friend requests
    try:
        target_user = User.objects.get(id=addressee_id)
        privacy_settings = PrivacySettings.get_or_create_for_user(target_user)
        
        if not privacy_settings.allow_friend_requests:
            return Response({
                'success': False,
                'error': 'This user is not accepting friend requests'
            }, status=status.HTTP_403_FORBIDDEN)
    except User.DoesNotExist:
        return Response({
            'success': False,
            'error': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    success, message, friendship_data = FriendshipService.send_friend_request(
        request.user, addressee_id
    )
    
    if success:
        return Response({
            'success': True,
            'message': message,
            'data': friendship_data
        }, status=status.HTTP_201_CREATED)
    else:
        return Response({
            'success': False,
            'error': message
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def respond_to_friend_request(request, friendship_id):
    """
    Respond to a friend request (accept/decline).
    
    POST /api/friendships/respond/{friendship_id}/
    {
        "action": "accept"  // or "decline"
    }
    """
    serializer = FriendshipResponseSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {'error': 'Invalid data', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    action = serializer.validated_data['action']
    
    success, message, friendship_data = FriendshipService.respond_to_friend_request(
        request.user, friendship_id, action
    )
    
    if success:
        return Response({
            'success': True,
            'message': message,
            'data': friendship_data
        }, status=status.HTTP_200_OK)
    else:
        return Response({
            'success': False,
            'error': message
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_friends(request):
    """
    Get list of user's friends.
    
    GET /api/friendships/friends/
    """
    friends = FriendshipService.get_friends_list(request.user)
    
    return Response({
        'success': True,
        'data': {
            'friends': friends,
            'count': len(friends)
        }
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_pending_requests(request):
    """
    Get list of pending friend requests.
    
    GET /api/friendships/pending-requests/
    """
    pending_requests = FriendshipService.get_pending_requests(request.user)
    
    return Response({
        'success': True,
        'data': {
            'pending_requests': pending_requests,
            'count': len(pending_requests)
        }
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def block_user(request):
    """
    Block another user.
    
    POST /api/friendships/block/
    {
        "user_id": 123
    }
    """
    serializer = BlockUserSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {'error': 'Invalid data', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    user_id = serializer.validated_data['user_id']
    
    success, message = FriendshipService.block_user(request.user, user_id)
    
    if success:
        return Response({
            'success': True,
            'message': message
        }, status=status.HTTP_200_OK)
    else:
        return Response({
            'success': False,
            'error': message
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def unblock_user(request):
    """
    Unblock another user.
    
    POST /api/friendships/unblock/
    {
        "user_id": 123
    }
    """
    serializer = BlockUserSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {'error': 'Invalid data', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    user_id = serializer.validated_data['user_id']
    
    success, message = FriendshipService.unblock_user(request.user, user_id)
    
    if success:
        return Response({
            'success': True,
            'message': message
        }, status=status.HTTP_200_OK)
    else:
        return Response({
            'success': False,
            'error': message
        }, status=status.HTTP_400_BAD_REQUEST)