from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from .privacy_models import PrivacySettings, FriendPrivacySettings, PrivateTask
from .privacy_utils import PrivacyChecker, filter_tasks_by_privacy
from task_management.models import Task
from friendships.models import Friendship

User = get_user_model()


class PrivacySettingsModelTest(TestCase):
    """Test privacy settings model functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            phone_number='+1234567890',
            username='testuser'
        )
    
    def test_privacy_settings_creation(self):
        """Test creating privacy settings with default values"""
        settings = PrivacySettings.get_or_create_for_user(self.user)
        
        self.assertEqual(settings.user, self.user)
        self.assertEqual(settings.profile_visibility, 'friends')
        self.assertEqual(settings.task_visibility, 'friends')
        self.assertTrue(settings.allow_friend_requests)
        self.assertTrue(settings.show_in_leaderboards)
    
    def test_can_view_profile_permissions(self):
        """Test profile visibility permissions"""
        other_user = User.objects.create_user(
            phone_number='+1234567891',
            username='otheruser'
        )
        
        settings = PrivacySettings.get_or_create_for_user(self.user)
        
        # Test public visibility
        settings.profile_visibility = 'public'
        settings.save()
        self.assertTrue(settings.can_view_profile(other_user))
        
        # Test private visibility
        settings.profile_visibility = 'private'
        settings.save()
        self.assertFalse(settings.can_view_profile(other_user))
        
        # Test friends visibility without friendship
        settings.profile_visibility = 'friends'
        settings.save()
        self.assertFalse(settings.can_view_profile(other_user))
    
    def test_activity_feed_visibility_settings(self):
        """Test activity feed visibility settings"""
        settings = PrivacySettings.get_or_create_for_user(self.user)
        
        # Test all activities
        settings.activity_feed_visibility = 'all'
        settings.save()
        self.assertTrue(settings.should_show_in_activity_feed('task_completed'))
        self.assertTrue(settings.should_show_in_activity_feed('achievement_earned'))
        
        # Test achievements only
        settings.activity_feed_visibility = 'achievements_only'
        settings.save()
        self.assertFalse(settings.should_show_in_activity_feed('task_completed'))
        self.assertTrue(settings.should_show_in_activity_feed('achievement_earned'))
        
        # Test none
        settings.activity_feed_visibility = 'none'
        settings.save()
        self.assertFalse(settings.should_show_in_activity_feed('task_completed'))
        self.assertFalse(settings.should_show_in_activity_feed('achievement_earned'))


class FriendPrivacySettingsModelTest(TestCase):
    """Test friend-specific privacy settings"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            phone_number='+1234567890',
            username='testuser'
        )
        self.friend = User.objects.create_user(
            phone_number='+1234567891',
            username='friend'
        )
    
    def test_friend_privacy_settings_creation(self):
        """Test creating friend privacy settings"""
        settings = FriendPrivacySettings.get_or_create_for_friendship(self.user, self.friend)
        
        self.assertEqual(settings.user, self.user)
        self.assertEqual(settings.friend, self.friend)
        self.assertEqual(settings.visibility_level, 'full')
        self.assertTrue(settings.can_see_tasks)
        self.assertTrue(settings.can_see_achievements)
    
    def test_visibility_level_application(self):
        """Test applying visibility level presets"""
        settings = FriendPrivacySettings.get_or_create_for_friendship(self.user, self.friend)
        
        # Test limited visibility
        settings.visibility_level = 'limited'
        settings.apply_visibility_level()
        
        self.assertFalse(settings.can_see_tasks)
        self.assertTrue(settings.can_see_achievements)
        self.assertTrue(settings.can_see_activity_feed)
        
        # Test minimal visibility
        settings.visibility_level = 'minimal'
        settings.apply_visibility_level()
        
        self.assertFalse(settings.can_see_tasks)
        self.assertFalse(settings.can_see_task_completions)
        self.assertTrue(settings.can_see_achievements)
        self.assertFalse(settings.can_see_activity_feed)
        
        # Test blocked
        settings.visibility_level = 'blocked'
        settings.apply_visibility_level()
        
        self.assertFalse(settings.can_see_tasks)
        self.assertFalse(settings.can_see_achievements)
        self.assertFalse(settings.can_see_activity_feed)
    
    def test_self_privacy_validation(self):
        """Test that users cannot set privacy settings for themselves"""
        with self.assertRaises(Exception):
            FriendPrivacySettings.objects.create(
                user=self.user,
                friend=self.user,
                visibility_level='blocked'
            )


class PrivateTaskModelTest(TestCase):
    """Test private task settings"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            phone_number='+1234567890',
            username='testuser'
        )
        self.friend = User.objects.create_user(
            phone_number='+1234567891',
            username='friend'
        )
        self.task = Task.objects.create(
            user=self.user,
            title='Test Task',
            description='Test Description'
        )
    
    def test_private_task_creation(self):
        """Test creating private task settings"""
        private_task = PrivateTask.objects.create(
            task=self.task,
            is_completely_private=True
        )
        
        self.assertEqual(private_task.task, self.task)
        self.assertTrue(private_task.is_completely_private)
        self.assertTrue(private_task.hide_from_activity_feed)
    
    def test_private_task_visibility(self):
        """Test private task visibility permissions"""
        private_task = PrivateTask.objects.create(
            task=self.task,
            is_completely_private=True
        )
        
        # Owner can always see their task
        self.assertTrue(private_task.can_view_task(self.user))
        
        # Others cannot see completely private task
        self.assertFalse(private_task.can_view_task(self.friend))
        
        # Add friend to visible list
        private_task.visible_to_friends.add(self.friend)
        private_task.is_completely_private = False
        private_task.save()
        
        self.assertTrue(private_task.can_view_task(self.friend))


class PrivacyCheckerTest(TestCase):
    """Test privacy checker utility class"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            phone_number='+1234567890',
            username='testuser'
        )
        self.friend = User.objects.create_user(
            phone_number='+1234567891',
            username='friend'
        )
        self.stranger = User.objects.create_user(
            phone_number='+1234567892',
            username='stranger'
        )
        
        # Create friendship
        Friendship.objects.create(
            requester=self.user,
            addressee=self.friend,
            status='accepted'
        )
    
    def test_privacy_checker_profile_access(self):
        """Test privacy checker for profile access"""
        checker = PrivacyChecker(self.friend)
        
        # Test with default settings (friends only)
        self.assertTrue(checker.can_view_user_profile(self.user))
        
        # Test stranger access
        stranger_checker = PrivacyChecker(self.stranger)
        self.assertFalse(stranger_checker.can_view_user_profile(self.user))
        
        # Test with public settings
        privacy_settings = PrivacySettings.get_or_create_for_user(self.user)
        privacy_settings.profile_visibility = 'public'
        privacy_settings.save()
        
        self.assertTrue(stranger_checker.can_view_user_profile(self.user))
    
    def test_privacy_checker_task_access(self):
        """Test privacy checker for task access"""
        checker = PrivacyChecker(self.friend)
        
        # Test with default settings
        self.assertTrue(checker.can_view_user_tasks(self.user))
        
        # Test with friend-specific restrictions
        friend_settings = FriendPrivacySettings.get_or_create_for_friendship(self.user, self.friend)
        friend_settings.can_see_tasks = False
        friend_settings.save()
        
        self.assertFalse(checker.can_view_user_tasks(self.user))
    
    def test_privacy_checker_specific_task(self):
        """Test privacy checker for specific task access"""
        task = Task.objects.create(
            user=self.user,
            title='Test Task'
        )
        
        checker = PrivacyChecker(self.friend)
        
        # Test normal task access
        self.assertTrue(checker.can_view_specific_task(task))
        
        # Test private task
        PrivateTask.objects.create(
            task=task,
            is_completely_private=True
        )
        
        self.assertFalse(checker.can_view_specific_task(task))


class PrivacyAPITest(APITestCase):
    """Test privacy API endpoints"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            phone_number='+1234567890',
            username='testuser'
        )
        self.user.is_phone_verified = True
        self.user.save()
        
        self.friend = User.objects.create_user(
            phone_number='+1234567891',
            username='friend'
        )
        self.friend.is_phone_verified = True
        self.friend.save()
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_get_privacy_settings(self):
        """Test retrieving privacy settings"""
        url = reverse('user_accounts:privacy:privacy-settings')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['profile_visibility'], 'friends')
        self.assertEqual(response.data['task_visibility'], 'friends')
    
    def test_update_privacy_settings(self):
        """Test updating privacy settings"""
        url = reverse('user_accounts:privacy:privacy-settings')
        data = {
            'profile_visibility': 'private',
            'task_visibility': 'private',
            'show_in_leaderboards': False
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['profile_visibility'], 'private')
        self.assertEqual(response.data['task_visibility'], 'private')
        self.assertFalse(response.data['show_in_leaderboards'])
    
    def test_privacy_summary(self):
        """Test privacy summary endpoint"""
        url = reverse('user_accounts:privacy:privacy-summary')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('privacy_settings', response.data)
        self.assertIn('privacy_score', response.data)
        self.assertIn('friend_settings_count', response.data)
    
    def test_privacy_check(self):
        """Test privacy check endpoint"""
        url = reverse('user_accounts:privacy:privacy-check')
        data = {
            'target_user_id': self.friend.id,
            'permission_type': 'profile'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('has_permission', response.data)
        self.assertEqual(response.data['target_user_id'], self.friend.id)
    
    def test_friend_privacy_settings_crud(self):
        """Test CRUD operations for friend privacy settings"""
        # Create friendship first
        Friendship.objects.create(
            requester=self.user,
            addressee=self.friend,
            status='accepted'
        )
        
        # Get the automatically created friend privacy settings
        from user_accounts.privacy_models import FriendPrivacySettings
        friend_settings = FriendPrivacySettings.objects.get(
            user=self.user,
            friend=self.friend
        )
        
        # Update the existing settings instead of creating new ones
        detail_url = reverse('user_accounts:privacy:friend-privacy-detail', kwargs={'pk': friend_settings.id})
        data = {
            'visibility_level': 'limited',
            'can_see_tasks': False
        }
        
        response = self.client.patch(detail_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Retrieve settings to verify update
        response = self.client.get(detail_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['visibility_level'], 'limited')
        self.assertFalse(response.data['can_see_tasks'])
    
    def test_private_task_settings(self):
        """Test private task settings endpoints"""
        task = Task.objects.create(
            user=self.user,
            title='Private Task'
        )
        
        # Create private task settings
        url = reverse('user_accounts:privacy:private-tasks-list')
        data = {
            'task': task.id,
            'is_completely_private': True,
            'hide_from_activity_feed': True
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify settings were created
        private_task = PrivateTask.objects.get(task=task)
        self.assertTrue(private_task.is_completely_private)
        self.assertTrue(private_task.hide_from_activity_feed)
    
    def test_privacy_recommendations(self):
        """Test privacy recommendations endpoint"""
        url = reverse('user_accounts:privacy:privacy-recommendations')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('recommendations', response.data)
        self.assertIn('privacy_score', response.data)
    
    def test_reset_privacy_settings(self):
        """Test resetting privacy settings to defaults"""
        # First, change some settings
        privacy_settings = PrivacySettings.get_or_create_for_user(self.user)
        privacy_settings.profile_visibility = 'private'
        privacy_settings.show_in_leaderboards = False
        privacy_settings.save()
        
        # Reset settings
        url = reverse('user_accounts:privacy:privacy-reset')
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify settings were reset
        privacy_settings.refresh_from_db()
        self.assertEqual(privacy_settings.profile_visibility, 'friends')
        self.assertTrue(privacy_settings.show_in_leaderboards)
    
    def test_unauthorized_access(self):
        """Test that unauthenticated users cannot access privacy endpoints"""
        self.client.force_authenticate(user=None)  # Remove authentication
        
        url = reverse('user_accounts:privacy:privacy-settings')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivacyUtilsTest(TestCase):
    """Test privacy utility functions"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            phone_number='+1234567890',
            username='testuser'
        )
        self.friend = User.objects.create_user(
            phone_number='+1234567891',
            username='friend'
        )
        self.stranger = User.objects.create_user(
            phone_number='+1234567892',
            username='stranger'
        )
        
        # Create friendship
        Friendship.objects.create(
            requester=self.user,
            addressee=self.friend,
            status='accepted'
        )
        
        # Create tasks
        self.user_task = Task.objects.create(
            user=self.user,
            title='User Task'
        )
        self.friend_task = Task.objects.create(
            user=self.friend,
            title='Friend Task'
        )
        self.stranger_task = Task.objects.create(
            user=self.stranger,
            title='Stranger Task'
        )
    
    def test_filter_tasks_by_privacy(self):
        """Test filtering tasks based on privacy settings"""
        all_tasks = Task.objects.all()
        
        # User should see their own tasks and friend's tasks
        visible_tasks = filter_tasks_by_privacy(all_tasks, self.user)
        task_ids = list(visible_tasks.values_list('id', flat=True))
        
        self.assertIn(self.user_task.id, task_ids)
        self.assertIn(self.friend_task.id, task_ids)
        self.assertNotIn(self.stranger_task.id, task_ids)
        
        # Test with private task
        PrivateTask.objects.create(
            task=self.friend_task,
            is_completely_private=True
        )
        
        visible_tasks = filter_tasks_by_privacy(all_tasks, self.user)
        task_ids = list(visible_tasks.values_list('id', flat=True))
        
        self.assertIn(self.user_task.id, task_ids)
        self.assertNotIn(self.friend_task.id, task_ids)  # Now private
    
    def test_unauthenticated_user_filtering(self):
        """Test that unauthenticated users see no tasks"""
        from django.contrib.auth.models import AnonymousUser
        
        all_tasks = Task.objects.all()
        visible_tasks = filter_tasks_by_privacy(all_tasks, AnonymousUser())
        
        self.assertEqual(visible_tasks.count(), 0)