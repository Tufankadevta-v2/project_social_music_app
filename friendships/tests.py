from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from .models import ContactHash, Friendship
from .services import ContactSyncService, FriendshipService

User = get_user_model()


class ContactHashModelTest(TestCase):
    """Test cases for ContactHash model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            phone_number='+1234567890',
            username='testuser',
            is_phone_verified=True
        )
    
    def test_hash_phone_number(self):
        """Test phone number hashing functionality."""
        phone = '+1234567890'
        hash1 = ContactHash.hash_phone_number(phone)
        hash2 = ContactHash.hash_phone_number(phone)
        
        # Same phone number should produce same hash
        self.assertEqual(hash1, hash2)
        
        # Hash should be 64 characters (SHA256)
        self.assertEqual(len(hash1), 64)
        
        # Different phone numbers should produce different hashes
        different_hash = ContactHash.hash_phone_number('+0987654321')
        self.assertNotEqual(hash1, different_hash)
    
    def test_normalize_phone_numbers(self):
        """Test phone number normalization."""
        from .services import ContactSyncService
        
        test_cases = [
            ('1234567890', '+11234567890'),
            ('11234567890', '+11234567890'),
            ('+11234567890', '+11234567890'),
            ('123-456-7890', '+11234567890'),
            ('(123) 456-7890', '+11234567890'),
        ]
        
        for input_phone, expected in test_cases:
            normalized = ContactSyncService.normalize_phone_number(input_phone)
            self.assertEqual(normalized, expected)
    
    def test_create_contact_hash(self):
        """Test creating contact hashes."""
        phone = '+0987654321'
        contact_hash = ContactHash.create_contact_hash(self.user, phone)
        
        self.assertIsInstance(contact_hash, ContactHash)
        self.assertEqual(contact_hash.user, self.user)
        self.assertEqual(contact_hash.phone_hash, ContactHash.hash_phone_number(phone))
        
        # Creating same hash again should return existing one
        contact_hash2 = ContactHash.create_contact_hash(self.user, phone)
        self.assertEqual(contact_hash.id, contact_hash2.id)
    
    def test_find_mutual_contacts(self):
        """Test mutual contact discovery."""
        # Create users
        user1 = User.objects.create_user(phone_number='+1111111111', username='user1', is_phone_verified=True)
        user2 = User.objects.create_user(phone_number='+2222222222', username='user2', is_phone_verified=True)
        user3 = User.objects.create_user(phone_number='+3333333333', username='user3', is_phone_verified=True)
        
        # User1 has User2's number
        ContactHash.create_contact_hash(user1, user2.phone_number)
        
        # User2 has User1's number (mutual)
        ContactHash.create_contact_hash(user2, user1.phone_number)
        
        # User1 has User3's number but User3 doesn't have User1's (not mutual)
        ContactHash.create_contact_hash(user1, user3.phone_number)
        
        # Find mutual contacts for User1
        mutual_contacts = ContactHash.find_mutual_contacts(
            user1, [user2.phone_number, user3.phone_number]
        )
        
        # Should only find User2 as mutual contact
        self.assertEqual(mutual_contacts.count(), 1)
        self.assertEqual(mutual_contacts.first(), user2)


class FriendshipModelTest(TestCase):
    """Test cases for Friendship model."""
    
    def setUp(self):
        self.user1 = User.objects.create_user(
            phone_number='+1111111111',
            username='user1',
            is_phone_verified=True
        )
        self.user2 = User.objects.create_user(
            phone_number='+2222222222',
            username='user2',
            is_phone_verified=True
        )
    
    def test_send_friend_request(self):
        """Test sending friend requests."""
        friendship, created = Friendship.send_friend_request(self.user1, self.user2)
        
        self.assertTrue(created)
        self.assertEqual(friendship.requester, self.user1)
        self.assertEqual(friendship.addressee, self.user2)
        self.assertEqual(friendship.status, 'pending')
    
    def test_cannot_send_duplicate_request(self):
        """Test that duplicate friend requests are not allowed."""
        Friendship.send_friend_request(self.user1, self.user2)
        
        with self.assertRaises(Exception):
            Friendship.send_friend_request(self.user1, self.user2)
    
    def test_accept_friend_request(self):
        """Test accepting friend requests."""
        friendship, _ = Friendship.send_friend_request(self.user1, self.user2)
        friendship.accept()
        
        self.assertEqual(friendship.status, 'accepted')
        self.assertTrue(Friendship.are_friends(self.user1, self.user2))
    
    def test_decline_friend_request(self):
        """Test declining friend requests."""
        friendship, _ = Friendship.send_friend_request(self.user1, self.user2)
        friendship.decline()
        
        self.assertEqual(friendship.status, 'declined')
        self.assertFalse(Friendship.are_friends(self.user1, self.user2))
    
    def test_block_user(self):
        """Test blocking functionality."""
        friendship, _ = Friendship.send_friend_request(self.user1, self.user2)
        friendship.block()
        
        self.assertEqual(friendship.status, 'blocked')
    
    def test_get_friends(self):
        """Test getting friends list."""
        user3 = User.objects.create_user(phone_number='+3333333333', username='user3', is_phone_verified=True)
        
        # Create accepted friendships
        friendship1, _ = Friendship.send_friend_request(self.user1, self.user2)
        friendship1.accept()
        
        friendship2, _ = Friendship.send_friend_request(self.user1, user3)
        friendship2.accept()
        
        friends = Friendship.get_friends(self.user1)
        self.assertEqual(friends.count(), 2)
        self.assertIn(self.user2, friends)
        self.assertIn(user3, friends)


class ContactSyncServiceTest(TestCase):
    """Test cases for ContactSyncService."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            phone_number='+1234567890',
            username='testuser',
            is_phone_verified=True
        )
    
    def test_normalize_phone_number(self):
        """Test phone number normalization."""
        test_cases = [
            ('1234567890', '+11234567890'),
            ('11234567890', '+11234567890'),
            ('+11234567890', '+11234567890'),
            ('123-456-7890', '+11234567890'),
            ('(123) 456-7890', '+11234567890'),
            ('', ''),
        ]
        
        for input_phone, expected in test_cases:
            result = ContactSyncService.normalize_phone_number(input_phone)
            self.assertEqual(result, expected)
    
    def test_validate_phone_numbers(self):
        """Test phone number validation."""
        valid_numbers = [
            '+1234567890',
            '1234567890',
            '123-456-7890',
            '(123) 456-7890'
        ]
        
        invalid_numbers = [
            '123',  # Too short
            '',     # Empty
            'abc',  # Non-numeric
        ]
        
        all_numbers = valid_numbers + invalid_numbers
        result = ContactSyncService.validate_phone_numbers(all_numbers)
        
        # Should return 4 valid numbers (all normalized to +1 format)
        self.assertEqual(len(result), 4)
        for number in result:
            self.assertTrue(number.startswith('+1'))
    
    def test_sync_contacts(self):
        """Test contact syncing functionality."""
        # Create another user
        user2 = User.objects.create_user(
            phone_number='+0987654321',
            username='user2',
            is_phone_verified=True
        )
        
        # User2 uploads User1's contact
        ContactHash.create_contact_hash(user2, self.user.phone_number)
        
        # User1 syncs contacts including User2's number
        phone_numbers = ['+0987654321', '+1111111111']  # User2's number + random number
        
        result = ContactSyncService.sync_contacts(self.user, phone_numbers)
        
        self.assertTrue(result['contacts_synced'] > 0)
        self.assertEqual(result['mutual_count'], 1)
        self.assertEqual(len(result['mutual_contacts']), 1)
        self.assertEqual(result['mutual_contacts'][0]['id'], user2.id)


class FriendshipAPITest(APITestCase):
    """Test cases for Friendship API endpoints."""
    
    def setUp(self):
        self.user1 = User.objects.create_user(
            phone_number='+1111111111',
            username='user1',
            is_phone_verified=True
        )
        self.user2 = User.objects.create_user(
            phone_number='+2222222222',
            username='user2',
            is_phone_verified=True
        )
        
        # Set up mutual contacts
        ContactHash.create_contact_hash(self.user1, self.user2.phone_number)
        ContactHash.create_contact_hash(self.user2, self.user1.phone_number)
        
        # Authenticate user1
        refresh = RefreshToken.for_user(self.user1)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    
    def test_sync_contacts_api(self):
        """Test contact sync API endpoint."""
        url = reverse('friendships:sync_contacts')
        data = {
            'phone_numbers': ['+2222222222', '+3333333333']
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('data', response.data)
    
    def test_get_mutual_contacts_api(self):
        """Test get mutual contacts API endpoint."""
        url = reverse('friendships:mutual_contacts')
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('mutual_contacts', response.data['data'])
    
    def test_send_friend_request_api(self):
        """Test send friend request API endpoint."""
        url = reverse('friendships:send_friend_request')
        data = {'addressee_id': self.user2.id}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.assertIn('data', response.data)
    
    def test_respond_to_friend_request_api(self):
        """Test respond to friend request API endpoint."""
        # Create a friend request
        friendship, _ = Friendship.send_friend_request(self.user2, self.user1)
        
        url = reverse('friendships:respond_to_friend_request', kwargs={'friendship_id': friendship.id})
        data = {'action': 'accept'}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Verify friendship was accepted
        friendship.refresh_from_db()
        self.assertEqual(friendship.status, 'accepted')
    
    def test_get_friends_api(self):
        """Test get friends list API endpoint."""
        # Create and accept a friendship
        friendship, _ = Friendship.send_friend_request(self.user1, self.user2)
        friendship.accept()
        
        url = reverse('friendships:get_friends')
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['count'], 1)
    
    def test_get_pending_requests_api(self):
        """Test get pending requests API endpoint."""
        # Create a pending request to user1
        Friendship.send_friend_request(self.user2, self.user1)
        
        url = reverse('friendships:pending_requests')
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['count'], 1)
    
    def test_block_user_api(self):
        """Test block user API endpoint."""
        url = reverse('friendships:block_user')
        data = {'user_id': self.user2.id}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
    
    def test_unblock_user_api(self):
        """Test unblock user API endpoint."""
        # First block the user
        FriendshipService.block_user(self.user1, self.user2.id)
        
        url = reverse('friendships:unblock_user')
        data = {'user_id': self.user2.id}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
    
    def test_cannot_send_request_to_non_mutual_contact(self):
        """Test that friend requests can only be sent to mutual contacts."""
        # Create user3 without mutual contact relationship
        user3 = User.objects.create_user(
            phone_number='+3333333333',
            username='user3',
            is_phone_verified=True
        )
        
        url = reverse('friendships:send_friend_request')
        data = {'addressee_id': user3.id}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('mutual contacts', response.data['error'])


class PrivacyProtectionTest(TestCase):
    """Test cases for privacy protection features."""
    
    def test_phone_numbers_are_hashed(self):
        """Test that phone numbers are stored as hashes, not plain text."""
        user = User.objects.create_user(
            phone_number='+1234567890',
            username='testuser',
            is_phone_verified=True
        )
        
        phone_to_hash = '+0987654321'
        contact_hash = ContactHash.create_contact_hash(user, phone_to_hash)
        
        # Verify that the stored hash is not the original phone number
        self.assertNotEqual(contact_hash.phone_hash, phone_to_hash)
        
        # Verify that the hash is consistent
        expected_hash = ContactHash.hash_phone_number(phone_to_hash)
        self.assertEqual(contact_hash.phone_hash, expected_hash)
    
    def test_mutual_contact_requirement(self):
        """Test that users can only discover each other if both have uploaded contacts."""
        user1 = User.objects.create_user(phone_number='+1111111111', username='user1', is_phone_verified=True)
        user2 = User.objects.create_user(phone_number='+2222222222', username='user2', is_phone_verified=True)
        user3 = User.objects.create_user(phone_number='+3333333333', username='user3', is_phone_verified=True)
        
        # Only user1 has user2's number (not mutual)
        ContactHash.create_contact_hash(user1, user2.phone_number)
        
        # Both user1 and user3 have each other's numbers (mutual)
        ContactHash.create_contact_hash(user1, user3.phone_number)
        ContactHash.create_contact_hash(user3, user1.phone_number)
        
        # User1 should only see user3 as mutual contact, not user2
        mutual_contacts = ContactHash.find_mutual_contacts(
            user1, [user2.phone_number, user3.phone_number]
        )
        
        self.assertEqual(mutual_contacts.count(), 1)
        self.assertEqual(mutual_contacts.first(), user3)
