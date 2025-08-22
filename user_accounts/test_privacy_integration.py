from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from .privacy_models import PrivacySettings, FriendPrivacySettings, PrivateTask
from .privacy_utils import PrivacyChecker, filter_tasks_by_privacy, filter_activity_feed_by_privacy
from task_management.models import Task, SharedTask, TaskParticipation
from social_feed.models import ActivityFeed, ActivityInteraction
from friendships.models import Friendship

User = get_user_model()


class PrivacyIntegrationTest(APITestCase):
    """Test privacy filtering across all features"""
    
    def setUp(self):
        # Create users
        self.user1 = User.objects.create_user(
            phone_number='+1234567890',
            username='user1'
        )
        self.user1.is_phone_verified = True
        self.user1.save()
        
        self.user2 = User.objects.create_user(
            phone_number='+1234567891',
            username='user2'
        )
        self.user2.is_phone_verified = True
        self.user2.save()
        
        self.user3 = User.objects.create_user(
            phone_number='+1234567892',
            username='user3'
        )
        self.user3.is_phone_verified = True
        self.user3.save()
        
        # Create friendship between user1 and user2
        Friendship.objects.create(
            requester=self.user1,
            addressee=self.user2,
            status='accepted'
        )
        
        # Create tasks
        self.user1_task = Task.objects.create(
            user=self.user1,
            title='User1 Public Task',
            description='This is a public task'
        )
        
        self.user1_private_task = Task.objects.create(
            user=self.user1,
            title='User1 Private Task',
            description='This is a private task',
            is_private=True
        )
        
        self.user2_task = Task.objects.create(
            user=self.user2,
            title='User2 Task',
            description='User2 task'
        )
        
        self.user3_task = Task.objects.create(
            user=self.user3,
            title='User3 Task',
            description='User3 task'
        )
        
        # Create activity feed entries
        self.user1_activity = ActivityFeed.objects.create(
            user=self.user1,
            activity_type='task_completed',
            title='Completed a task',
            description='User1 completed a task',
            is_public=True
        )
        
        self.user2_activity = ActivityFeed.objects.create(
            user=self.user2,
            activity_type='achievement_earned',
            title='Earned an achievement',
            description='User2 earned an achievement',
            is_public=True
        )
        
        self.user3_activity = ActivityFeed.objects.create(
            user=self.user3,
            activity_type='task_completed',
            title='Completed a task',
            description='User3 completed a task',
            is_public=True
        )
        
        # Set up API client
        self.client = APIClient()
    
    def test_task_privacy_filtering(self):
        """Test that task privacy filtering works correctly"""
        self.client.force_authenticate(user=self.user1)
        
        # User1 should see their own tasks and friend's tasks
        all_tasks = Task.objects.all()
        visible_tasks = filter_tasks_by_privacy(all_tasks, self.user1)
        task_ids = list(visible_tasks.values_list('id', flat=True))
        
        self.assertIn(self.user1_task.id, task_ids)
        self.assertIn(self.user1_private_task.id, task_ids)  # Own private task
        self.assertIn(self.user2_task.id, task_ids)  # Friend's task
        self.assertNotIn(self.user3_task.id, task_ids)  # Stranger's task
    
    def test_task_privacy_with_restricted_friend(self):
        """Test task privacy when friend has restricted settings"""
        # Set user2's privacy to not allow user1 to see tasks
        privacy_settings = PrivacySettings.get_or_create_for_user(self.user2)
        privacy_settings.task_visibility = 'private'
        privacy_settings.save()
        
        self.client.force_authenticate(user=self.user1)
        
        all_tasks = Task.objects.all()
        visible_tasks = filter_tasks_by_privacy(all_tasks, self.user1)
        task_ids = list(visible_tasks.values_list('id', flat=True))
        
        self.assertIn(self.user1_task.id, task_ids)
        self.assertNotIn(self.user2_task.id, task_ids)  # Friend's task now hidden
        self.assertNotIn(self.user3_task.id, task_ids)
    
    def test_activity_feed_privacy_filtering(self):
        """Test that activity feed privacy filtering works correctly"""
        self.client.force_authenticate(user=self.user1)
        
        all_activities = ActivityFeed.objects.all()
        visible_activities = filter_activity_feed_by_privacy(all_activities, self.user1)
        activity_ids = list(visible_activities.values_list('id', flat=True))
        
        self.assertIn(self.user1_activity.id, activity_ids)  # Own activity
        self.assertIn(self.user2_activity.id, activity_ids)  # Friend's activity
        self.assertNotIn(self.user3_activity.id, activity_ids)  # Stranger's activity
    
    def test_activity_feed_privacy_with_restricted_friend(self):
        """Test activity feed privacy when friend has restricted settings"""
        # Set friend-specific privacy settings
        friend_settings = FriendPrivacySettings.get_or_create_for_friendship(
            self.user2, self.user1
        )
        friend_settings.can_see_activity_feed = False
        friend_settings.save()
        
        self.client.force_authenticate(user=self.user1)
        
        all_activities = ActivityFeed.objects.all()
        visible_activities = filter_activity_feed_by_privacy(all_activities, self.user1)
        activity_ids = list(visible_activities.values_list('id', flat=True))
        
        self.assertIn(self.user1_activity.id, activity_ids)  # Own activity
        self.assertNotIn(self.user2_activity.id, activity_ids)  # Friend's activity now hidden
        self.assertNotIn(self.user3_activity.id, activity_ids)  # Stranger's activity
    
    def test_private_task_visibility(self):
        """Test that private tasks are properly filtered"""
        # Create private task settings
        PrivateTask.objects.create(
            task=self.user1_private_task,
            is_completely_private=True
        )
        
        self.client.force_authenticate(user=self.user2)
        
        all_tasks = Task.objects.all()
        visible_tasks = filter_tasks_by_privacy(all_tasks, self.user2)
        task_ids = list(visible_tasks.values_list('id', flat=True))
        
        self.assertIn(self.user1_task.id, task_ids)  # Friend's public task
        self.assertNotIn(self.user1_private_task.id, task_ids)  # Friend's private task
        self.assertIn(self.user2_task.id, task_ids)  # Own task
    
    def test_private_task_with_specific_visibility(self):
        """Test private task with specific friend visibility"""
        # Create private task settings that allow user2 to see it
        private_task_settings = PrivateTask.objects.create(
            task=self.user1_private_task,
            is_completely_private=False
        )
        private_task_settings.visible_to_friends.add(self.user2)
        
        self.client.force_authenticate(user=self.user2)
        
        all_tasks = Task.objects.all()
        visible_tasks = filter_tasks_by_privacy(all_tasks, self.user2)
        task_ids = list(visible_tasks.values_list('id', flat=True))
        
        self.assertIn(self.user1_private_task.id, task_ids)  # Now visible to user2
    
    def test_friend_request_privacy_check(self):
        """Test that friend requests respect privacy settings"""
        # Disable friend requests for user3
        privacy_settings = PrivacySettings.get_or_create_for_user(self.user3)
        privacy_settings.allow_friend_requests = False
        privacy_settings.save()
        
        self.client.force_authenticate(user=self.user1)
        
        url = reverse('friendships:send_friend_request')
        data = {'addressee_id': self.user3.id}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('not accepting friend requests', response.data['error'])
    
    def test_shared_task_invite_privacy_check(self):
        """Test that shared task invites respect privacy settings"""
        # Create a shared task
        shared_task = SharedTask.objects.create(
            task=self.user1_task,
            creator=self.user1
        )
        
        # Disable shared task invites for user2
        privacy_settings = PrivacySettings.get_or_create_for_user(self.user2)
        privacy_settings.allow_shared_task_invites = False
        privacy_settings.save()
        
        self.client.force_authenticate(user=self.user1)
        
        # Try to invite user2 to shared task
        url = reverse('task_management:shared-tasks-invite', kwargs={'pk': shared_task.id})
        data = {'user_ids': [self.user2.id]}
        response = self.client.post(url, data)
        
        # This should either fail or not create the participation
        if response.status_code == 200:
            # Check that participation was not created
            participation_exists = TaskParticipation.objects.filter(
                shared_task=shared_task,
                user=self.user2
            ).exists()
            self.assertFalse(participation_exists)
    
    def test_leaderboard_privacy_filtering(self):
        """Test that leaderboards respect privacy settings"""
        # Disable leaderboard visibility for user2
        privacy_settings = PrivacySettings.get_or_create_for_user(self.user2)
        privacy_settings.show_in_leaderboards = False
        privacy_settings.save()
        
        self.client.force_authenticate(user=self.user1)
        
        # Get leaderboard data (this would be implemented in task_management views)
        from user_accounts.privacy_utils import get_visible_users_for_leaderboard
        
        all_users = User.objects.all()
        visible_users = get_visible_users_for_leaderboard(self.user1, all_users)
        user_ids = list(visible_users.values_list('id', flat=True))
        
        self.assertIn(self.user1.id, user_ids)  # Own user
        self.assertNotIn(self.user2.id, user_ids)  # Friend with disabled leaderboard
        self.assertNotIn(self.user3.id, user_ids)  # Stranger
    
    def test_profile_visibility_privacy(self):
        """Test profile visibility privacy settings"""
        # Set user2's profile to private
        privacy_settings = PrivacySettings.get_or_create_for_user(self.user2)
        privacy_settings.profile_visibility = 'private'
        privacy_settings.save()
        
        privacy_checker = PrivacyChecker(self.user1)
        
        # User1 should not be able to view user2's profile even though they're friends
        self.assertFalse(privacy_checker.can_view_user_profile(self.user2))
        
        # But user2 can view their own profile
        privacy_checker_self = PrivacyChecker(self.user2)
        self.assertTrue(privacy_checker_self.can_view_user_profile(self.user2))
    
    def test_achievement_visibility_privacy(self):
        """Test achievement visibility privacy settings"""
        # Set user2's achievements to private
        privacy_settings = PrivacySettings.get_or_create_for_user(self.user2)
        privacy_settings.achievement_visibility = 'private'
        privacy_settings.save()
        
        privacy_checker = PrivacyChecker(self.user1)
        
        # User1 should not be able to view user2's achievements
        self.assertFalse(privacy_checker.can_view_achievements(self.user2))
    
    def test_privacy_cascade_on_friendship_deletion(self):
        """Test that privacy settings are cleaned up when friendship is deleted"""
        # Create friend privacy settings
        friend_settings = FriendPrivacySettings.get_or_create_for_friendship(
            self.user1, self.user2
        )
        
        # Delete the friendship
        Friendship.objects.filter(
            requester=self.user1,
            addressee=self.user2
        ).delete()
        
        # Friend privacy settings should be cleaned up
        self.assertFalse(
            FriendPrivacySettings.objects.filter(
                user=self.user1,
                friend=self.user2
            ).exists()
        )
    
    def test_privacy_aware_activity_creation(self):
        """Test that activities are created with proper privacy settings"""
        from user_accounts.privacy_utils import create_privacy_aware_activity
        
        # Set user1's activity feed to none
        privacy_settings = PrivacySettings.get_or_create_for_user(self.user1)
        privacy_settings.activity_feed_visibility = 'none'
        privacy_settings.save()
        
        # Try to create an activity
        activity = create_privacy_aware_activity(
            user=self.user1,
            activity_type='task_completed',
            title='Test Activity',
            description='Test Description'
        )
        
        # Activity should not be created due to privacy settings
        self.assertIsNone(activity)
    
    def test_privacy_recommendations(self):
        """Test privacy recommendations endpoint"""
        self.client.force_authenticate(user=self.user1)
        
        # Set inconsistent privacy settings
        privacy_settings = PrivacySettings.get_or_create_for_user(self.user1)
        privacy_settings.profile_visibility = 'private'
        privacy_settings.task_visibility = 'public'
        privacy_settings.save()
        
        url = reverse('user_accounts:privacy:privacy-recommendations')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('recommendations', response.data)
        
        # Should have recommendations about inconsistent settings
        recommendations = response.data['recommendations']
        self.assertTrue(any(
            'inconsistent' in rec.get('title', '').lower() 
            for rec in recommendations
        ))


class PrivacySignalTest(TestCase):
    """Test privacy-related signals"""
    
    def setUp(self):
        self.user1 = User.objects.create_user(
            phone_number='+1234567890',
            username='user1'
        )
        self.user2 = User.objects.create_user(
            phone_number='+1234567891',
            username='user2'
        )
    
    def test_privacy_settings_created_on_user_creation(self):
        """Test that privacy settings are created when user is created"""
        new_user = User.objects.create_user(
            phone_number='+1234567899',
            username='newuser'
        )
        
        # Privacy settings should be created automatically
        self.assertTrue(
            PrivacySettings.objects.filter(user=new_user).exists()
        )
    
    def test_friend_privacy_settings_on_friendship(self):
        """Test that friend privacy settings are created on friendship"""
        # Create friendship
        friendship = Friendship.objects.create(
            requester=self.user1,
            addressee=self.user2,
            status='accepted'
        )
        
        # Friend privacy settings should be created for both users
        self.assertTrue(
            FriendPrivacySettings.objects.filter(
                user=self.user1,
                friend=self.user2
            ).exists()
        )
        self.assertTrue(
            FriendPrivacySettings.objects.filter(
                user=self.user2,
                friend=self.user1
            ).exists()
        )
    
    def test_private_task_settings_on_task_creation(self):
        """Test that private task settings are created for private tasks"""
        task = Task.objects.create(
            user=self.user1,
            title='Private Task',
            is_private=True
        )
        
        # PrivateTask settings should be created
        self.assertTrue(
            PrivateTask.objects.filter(task=task).exists()
        )