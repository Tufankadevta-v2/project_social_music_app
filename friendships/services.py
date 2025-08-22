"""
Contact syncing services with privacy protection for friend discovery.
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import ContactHash, Friendship
import re
from typing import List, Dict, Tuple

User = get_user_model()


class ContactSyncService:
    """
    Service for handling contact synchronization with privacy protection.
    Implements mutual contact discovery without storing raw phone numbers.
    """
    
    @staticmethod
    def normalize_phone_number(phone_number: str) -> str:
        """
        Normalize phone number to a consistent format.
        
        Args:
            phone_number (str): Raw phone number
            
        Returns:
            str: Normalized phone number with country code
        """
        if not phone_number:
            return ""
        
        # Remove all non-digit characters except +
        cleaned = re.sub(r'[^\d+]', '', phone_number.strip())
        
        # Handle different formats
        if cleaned.startswith('+'):
            return cleaned
        elif len(cleaned) == 10:
            # Assume US number
            return f"+1{cleaned}"
        elif len(cleaned) == 11 and cleaned.startswith('1'):
            # US number with country code but no +
            return f"+{cleaned}"
        else:
            # Return as-is with + prefix
            return f"+{cleaned}"
    
    @staticmethod
    def validate_phone_numbers(phone_numbers: List[str]) -> List[str]:
        """
        Validate and normalize a list of phone numbers.
        
        Args:
            phone_numbers (List[str]): List of raw phone numbers
            
        Returns:
            List[str]: List of valid, normalized phone numbers
        """
        valid_numbers = []
        
        for phone in phone_numbers:
            try:
                normalized = ContactSyncService.normalize_phone_number(phone)
                
                # Basic validation - must have at least 10 digits after country code
                digits_only = re.sub(r'[^\d]', '', normalized)
                if len(digits_only) >= 10:
                    valid_numbers.append(normalized)
                    
            except Exception:
                # Skip invalid numbers
                continue
        
        return valid_numbers
    
    @staticmethod
    def sync_contacts(user: User, phone_numbers: List[str]) -> Dict:
        """
        Sync user's contacts and find mutual connections.
        
        Args:
            user: User instance
            phone_numbers: List of phone numbers from user's contacts
            
        Returns:
            Dict: Results containing mutual contacts and sync statistics
        """
        if not phone_numbers:
            return {
                'mutual_contacts': [],
                'contacts_synced': 0,
                'mutual_count': 0,
                'errors': []
            }
        
        # Validate and normalize phone numbers
        valid_numbers = ContactSyncService.validate_phone_numbers(phone_numbers)
        
        if not valid_numbers:
            return {
                'mutual_contacts': [],
                'contacts_synced': 0,
                'mutual_count': 0,
                'errors': ['No valid phone numbers provided']
            }
        
        try:
            with transaction.atomic():
                # Create contact hashes for all valid numbers
                contact_hashes_created = 0
                for phone_number in valid_numbers:
                    # Skip user's own number
                    if phone_number == user.phone_number:
                        continue
                    
                    contact_hash = ContactHash.create_contact_hash(user, phone_number)
                    if contact_hash:
                        contact_hashes_created += 1
                
                # Find mutual contacts
                mutual_contacts = ContactHash.find_mutual_contacts(user, valid_numbers)
                
                # Convert to list with user info
                mutual_contacts_data = []
                for contact_user in mutual_contacts:
                    mutual_contacts_data.append({
                        'id': contact_user.id,
                        'phone_number': contact_user.phone_number,
                        'username': contact_user.username,
                        'display_name': getattr(contact_user.profile, 'display_name', '') if hasattr(contact_user, 'profile') else '',
                        'is_friend': Friendship.are_friends(user, contact_user),
                        'friendship_status': ContactSyncService._get_friendship_status(user, contact_user)
                    })
                
                return {
                    'mutual_contacts': mutual_contacts_data,
                    'contacts_synced': contact_hashes_created,
                    'mutual_count': len(mutual_contacts_data),
                    'errors': []
                }
                
        except Exception as e:
            return {
                'mutual_contacts': [],
                'contacts_synced': 0,
                'mutual_count': 0,
                'errors': [str(e)]
            }
    
    @staticmethod
    def _get_friendship_status(user1: User, user2: User) -> str:
        """
        Get the friendship status between two users.
        
        Args:
            user1: First user
            user2: Second user
            
        Returns:
            str: Friendship status ('none', 'pending_sent', 'pending_received', 'friends', 'blocked')
        """
        friendship = Friendship.get_friendship(user1, user2)
        
        if not friendship:
            return 'none'
        
        if friendship.status == 'accepted':
            return 'friends'
        elif friendship.status == 'blocked':
            return 'blocked'
        elif friendship.status == 'pending':
            if friendship.requester == user1:
                return 'pending_sent'
            else:
                return 'pending_received'
        elif friendship.status == 'declined':
            return 'declined'
        
        return 'none'
    
    @staticmethod
    def get_mutual_contacts_for_user(user: User) -> List[Dict]:
        """
        Get all mutual contacts for a user (users who have each other's numbers).
        
        Args:
            user: User instance
            
        Returns:
            List[Dict]: List of mutual contacts with their information
        """
        # Get all users who have uploaded the current user's phone number
        user_phone_hash = ContactHash.hash_phone_number(user.phone_number)
        users_with_my_number = ContactHash.objects.filter(
            phone_hash=user_phone_hash
        ).values_list('user_id', flat=True)
        
        # Get all contact hashes uploaded by the current user
        my_contact_hashes = ContactHash.objects.filter(
            user=user
        ).values_list('phone_hash', flat=True)
        
        # Find users whose phone hashes match my uploaded contacts
        # and who also have my phone number
        users_in_my_contacts = User.objects.filter(
            id__in=users_with_my_number
        )
        
        mutual_users = []
        for contact_user in users_in_my_contacts:
            # Check if I have this user's phone number in my contacts
            contact_user_hash = ContactHash.hash_phone_number(contact_user.phone_number)
            if contact_user_hash in my_contact_hashes:
                mutual_users.append(contact_user)
        
        # Convert to list with user info
        mutual_contacts_data = []
        for contact_user in mutual_users:
            if contact_user.id != user.id:  # Exclude self
                mutual_contacts_data.append({
                    'id': contact_user.id,
                    'phone_number': contact_user.phone_number,
                    'username': contact_user.username,
                    'display_name': getattr(contact_user.profile, 'display_name', '') if hasattr(contact_user, 'profile') else '',
                    'is_friend': Friendship.are_friends(user, contact_user),
                    'friendship_status': ContactSyncService._get_friendship_status(user, contact_user)
                })
        
        return mutual_contacts_data
    
    @staticmethod
    def clear_user_contacts(user: User) -> int:
        """
        Clear all contact hashes for a user.
        
        Args:
            user: User instance
            
        Returns:
            int: Number of contact hashes deleted
        """
        deleted_count, _ = ContactHash.objects.filter(user=user).delete()
        return deleted_count


class FriendshipService:
    """
    Service for managing friendship relationships.
    """
    
    @staticmethod
    def send_friend_request(requester: User, addressee_id: int) -> Tuple[bool, str, Dict]:
        """
        Send a friend request to another user.
        
        Args:
            requester: User sending the request
            addressee_id: ID of user receiving the request
            
        Returns:
            Tuple[bool, str, Dict]: (success, message, friendship_data)
        """
        try:
            addressee = User.objects.get(id=addressee_id)
        except User.DoesNotExist:
            return False, "User not found", {}
        
        # Check if users are mutual contacts
        mutual_contacts = ContactSyncService.get_mutual_contacts_for_user(requester)
        mutual_contact_ids = [contact['id'] for contact in mutual_contacts]
        
        if addressee.id not in mutual_contact_ids:
            return False, "Can only send friend requests to mutual contacts", {}
        
        try:
            friendship, created = Friendship.send_friend_request(requester, addressee)
            
            if created:
                return True, "Friend request sent successfully", {
                    'id': friendship.id,
                    'requester_id': friendship.requester.id,
                    'addressee_id': friendship.addressee.id,
                    'status': friendship.status,
                    'created_at': friendship.created_at.isoformat()
                }
            else:
                return False, "Friend request already exists", {}
                
        except ValidationError as e:
            return False, str(e), {}
    
    @staticmethod
    def respond_to_friend_request(user: User, friendship_id: int, action: str) -> Tuple[bool, str, Dict]:
        """
        Respond to a friend request (accept/decline).
        
        Args:
            user: User responding to the request
            friendship_id: ID of the friendship
            action: 'accept' or 'decline'
            
        Returns:
            Tuple[bool, str, Dict]: (success, message, friendship_data)
        """
        try:
            friendship = Friendship.objects.get(id=friendship_id, addressee=user)
        except Friendship.DoesNotExist:
            return False, "Friend request not found", {}
        
        try:
            if action == 'accept':
                friendship.accept()
                message = "Friend request accepted"
            elif action == 'decline':
                friendship.decline()
                message = "Friend request declined"
            else:
                return False, "Invalid action. Use 'accept' or 'decline'", {}
            
            return True, message, {
                'id': friendship.id,
                'requester_id': friendship.requester.id,
                'addressee_id': friendship.addressee.id,
                'status': friendship.status,
                'updated_at': friendship.updated_at.isoformat()
            }
            
        except ValidationError as e:
            return False, str(e), {}
    
    @staticmethod
    def block_user(user: User, target_user_id: int) -> Tuple[bool, str]:
        """
        Block another user.
        
        Args:
            user: User doing the blocking
            target_user_id: ID of user to block
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            target_user = User.objects.get(id=target_user_id)
        except User.DoesNotExist:
            return False, "User not found"
        
        # Get or create friendship to block
        friendship = Friendship.get_friendship(user, target_user)
        
        if friendship:
            friendship.block()
        else:
            # Create new blocked relationship
            Friendship.objects.create(
                requester=user,
                addressee=target_user,
                status='blocked'
            )
        
        return True, "User blocked successfully"
    
    @staticmethod
    def unblock_user(user: User, target_user_id: int) -> Tuple[bool, str]:
        """
        Unblock another user.
        
        Args:
            user: User doing the unblocking
            target_user_id: ID of user to unblock
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            target_user = User.objects.get(id=target_user_id)
        except User.DoesNotExist:
            return False, "User not found"
        
        friendship = Friendship.get_friendship(user, target_user)
        
        if not friendship or friendship.status != 'blocked':
            return False, "User is not blocked"
        
        try:
            friendship.unblock()
            return True, "User unblocked successfully"
        except ValidationError as e:
            return False, str(e)
    
    @staticmethod
    def get_friends_list(user: User) -> List[Dict]:
        """
        Get list of user's friends.
        
        Args:
            user: User instance
            
        Returns:
            List[Dict]: List of friends with their information
        """
        friends = Friendship.get_friends(user)
        
        friends_data = []
        for friend in friends:
            friends_data.append({
                'id': friend.id,
                'phone_number': friend.phone_number,
                'username': friend.username,
                'display_name': getattr(friend.profile, 'display_name', '') if hasattr(friend, 'profile') else '',
                'total_points': getattr(friend.profile, 'total_points', 0) if hasattr(friend, 'profile') else 0,
            })
        
        return friends_data
    
    @staticmethod
    def get_pending_requests(user: User) -> List[Dict]:
        """
        Get list of pending friend requests for a user.
        
        Args:
            user: User instance
            
        Returns:
            List[Dict]: List of pending requests
        """
        pending_requests = Friendship.get_pending_requests(user)
        
        requests_data = []
        for request in pending_requests:
            requests_data.append({
                'id': request.id,
                'requester': {
                    'id': request.requester.id,
                    'phone_number': request.requester.phone_number,
                    'username': request.requester.username,
                    'display_name': getattr(request.requester.profile, 'display_name', '') if hasattr(request.requester, 'profile') else '',
                },
                'created_at': request.created_at.isoformat()
            })
        
        return requests_data