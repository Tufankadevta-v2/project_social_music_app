from django.test import TestCase
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase
from rest_framework import status
from user_accounts.models import User
from friendships.models import Friendship
from task_management.models import Task, SharedTask, TaskParticipation
from .models import (
    ActivityFeed, ActivityInteraction, ActivityFeedSettings, ActivityPhoto,
    UserLocation, NearbyFriendRecommendation, SocialFeedPost, SocialPostPhoto,
    SocialPostInteraction
)
from .utils import ActivityFeedManager, LocationManager, SocialFeedAnalytics
import tempfile
from PIL import Image
import io


class ActivityFeedModelTest(TestCase):
    """Test cases for ActivityFeed model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            phone_number='+1234567890',
            username='testuser',
            password='testpass123'
        )
    
    def test_activity_feed_creation(self):
        """Test basic activity feed creation"""
        activity = ActivityFeed.objects.create(
            user=self.user,
            activity_type='task_completed',
            title='Completed morning workout',
            description='Earned 20 points',
            points_earned=20
        )
        
        self.assertEqual(activity.user, self.user)
        self.assertEqual(activity.activity_type, 'task_completed')
        self.assertEqual(activity.title, 'Completed morning workout')
        self.assertEqual(activity.points_earned, 20)
        self.assertTrue(activity.is_public)
        self.assertTrue(activity.is_recent)
    
    def test_activity_visibility(self):
        """Test activity visibility logic"""
        friend = User.objects.create_user(
            phone_number='+1234567891',
            username='friend',
            password='testpass123'
        )
        
        # Create friendship
        friendship = Friendship.send_friend_request(self.user, friend)[0]
        friendship.accept()
        
        # Create activity
        activity = ActivityFeed.objects.create(
            user=self.user,
            activity_type='task_completed',
            title='Test activity',
            is_public=True
        )
        
        # Should be visible to friend
        self.assertTrue(activity.get_visible_to_user(friend))
        
        # Should be visible to self
        self.assertTrue(activity.get_visible_to_user(self.user))
        
        # Should not be visible to non-friend
        stranger = User.objects.create_user(
            phone_number='+1234567892',
            username='stranger',
            password='testpass123'
        )
        self.assertFalse(activity.get_visible_to_user(stranger))
    
    def test_activity_with_photos(self):
        """Test activity with photo attachments"""
        activity = ActivityFeed.objects.create(
            user=self.user,
            activity_type='photo_shared',
            title='Workout selfie'
        )
        
        # Create test image
        image = Image.new('RGB', (100, 100), color='red')
        image_file = io.BytesIO()
        image.save(image_file, 'JPEG')
        image_file.seek(0)
        
        photo = ActivityPhoto.objects.create(
            activity=activity,
            image=SimpleUploadedFile('test.jpg', image_file.getvalue(), content_type='image/jpeg'),
            caption='Post-workout selfie'
        )
        
        self.assertEqual(activity.photos.count(), 1)
        self.assertEqual(photo.caption, 'Post-workout selfie')


class UserLocationModelTest(TestCase):
    """Test cases for UserLocation model"""
    
    def setUp(self):
        """Set up test data"""
        self.user1 = User.objects.create_user(
            phone_number='+1234567890',
            username='user1',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            phone_number='+1234567891',
            username='user2',
            password='testpass123'
        )
    
    def test_location_creation(self):
        """Test user location creation"""
        location = UserLocation.objects.create(
            user=self.user1,
            latitude=40.7128,
            longitude=-74.0060,
            city='New York',
            country='USA',
            is_location_enabled=True,
            location_precision='city'
        )
        
        self.assertEqual(location.user, self.user1)
        self.assertEqual(location.city, 'New York')
        self.assertTrue(location.is_location_enabled)
    
    def test_distance_calculation(self):
        """Test distance calculation between locations"""
        # New York
        location1 = UserLocation.objects.create(
            user=self.user1,
            latitude=40.7128,
            longitude=-74.0060,
            is_location_enabled=True
        )
        
        # Los Angeles
        location2 = UserLocation.objects.create(
            user=self.user2,
            latitude=34.0522,
            longitude=-118.2437,
            is_location_enabled=True
        )
        
        distance = location1.calculate_distance_to(location2)
        
        # Distance between NYC and LA is approximately 3944 km
        self.assertIsNotNone(distance)
        self.assertGreater(distance, 3900)
        self.assertLess(distance, 4000)
    
    def test_find_nearby_users(self):
        """Test finding nearby users"""
        # Create locations in same city (close)
        UserLocation.objects.create(
            user=self.user1,
            latitude=40.7128,
            longitude=-74.0060,
            is_location_enabled=True
        )
        
        UserLocation.objects.create(
            user=self.user2,
            latitude=40.7589,  # Slightly different coordinates (same city)
            longitude=-73.9851,
            is_location_enabled=True
        )
        
        nearby_users = UserLocation.find_nearby_users(self.user1, radius_km=50)
        
        self.assertIn(self.user2, nearby_users)


class SocialFeedPostModelTest(TestCase):
    """Test cases for SocialFeedPost model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            phone_number='+1234567890',
            username='testuser',
            password='testpass123'
        )
    
    def test_social_post_creation(self):
        """Test social post creation"""
        post = SocialFeedPost.objects.create(
            user=self.user,
            post_type='photo',
            title='Great workout today!',
            content='Feeling amazing after my morning run',
            location_name='Central Park, NYC',
            latitude=40.7829,
            longitude=-73.9654
        )
        
        self.assertEqual(post.user, self.user)
        self.assertEqual(post.post_type, 'photo')
        self.assertEqual(post.title, 'Great workout today!')
        self.assertEqual(post.location_name, 'Central Park, NYC')
        self.assertTrue(post.is_public)
    
    def test_post_interactions(self):
        """Test post interactions (likes, comments)"""
        post = SocialFeedPost.objects.create(
            user=self.user,
            post_type='text',
            content='Test post'
        )
        
        friend = User.objects.create_user(
            phone_number='+1234567891',
            username='friend',
            password='testpass123'
        )
        
        # Create like interaction
        like = SocialPostInteraction.objects.create(
            post=post,
            user=friend,
            interaction_type='like'
        )
        
        # Create comment interaction
        comment = SocialPostInteraction.objects.create(
            post=post,
            user=friend,
            interaction_type='comment',
            comment_text='Great post!'
        )
        
        self.assertEqual(post.interactions.count(), 2)
        self.assertEqual(post.likes_count, 1)
        self.assertEqual(post.comments_count, 1)


class ActivityFeedAPITest(APITestCase):
    """Test cases for ActivityFeed API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            phone_number='+1234567890',
            username='testuser',
            password='testpass123'
        )
        self.friend = User.objects.create_user(
            phone_number='+1234567891',
            username='friend',
            password='testpass123'
        )
        
        # Create friendship
        friendship = Friendship.send_friend_request(self.user, self.friend)[0]
        friendship.accept()
        
        self.client.force_authenticate(user=self.user)
    
    def test_get_activity_feed(self):
        """Test getting activity feed"""
        # Create activities
        ActivityFeed.objects.create(
            user=self.user,
            activity_type='task_completed',
            title='Completed workout',
            points_earned=20
        )
        
        ActivityFeed.objects.create(
            user=self.friend,
            activity_type='achievement_earned',
            title='Earned fitness badge',
            points_earned=50
        )
        
        response = self.client.get('/api/feed/activities/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_create_activity(self):
        """Test creating activity via API"""
        data = {
            'activity_type': 'celebration',
            'title': 'Reached 1000 points!',
            'description': 'Milestone celebration',
            'points_earned': 100
        }
        
        response = self.client.post('/api/feed/activities/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        activity = ActivityFeed.objects.get(id=response.data['id'])
        self.assertEqual(activity.user, self.user)
        self.assertEqual(activity.title, 'Reached 1000 points!')
    
    def test_interact_with_activity(self):
        """Test interacting with activity (like, comment)"""
        activity = ActivityFeed.objects.create(
            user=self.friend,
            activity_type='task_completed',
            title='Completed morning run'
        )
        
        # Like the activity
        response = self.client.post(
            f'/api/feed/activities/{activity.id}/interact/',
            {'interaction_type': 'like'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check interaction was created
        self.assertTrue(
            ActivityInteraction.objects.filter(
                activity=activity,
                user=self.user,
                interaction_type='like'
            ).exists()
        )
        
        # Comment on the activity
        response = self.client.post(
            f'/api/feed/activities/{activity.id}/interact/',
            {
                'interaction_type': 'comment',
                'comment_text': 'Great job!'
            }
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_get_trending_activities(self):
        """Test getting trending activities"""
        activity = ActivityFeed.objects.create(
            user=self.friend,
            activity_type='achievement_earned',
            title='Earned streak badge'
        )
        
        # Add interactions to make it trending
        ActivityInteraction.objects.create(
            activity=activity,
            user=self.user,
            interaction_type='like'
        )
        ActivityInteraction.objects.create(
            activity=activity,
            user=self.user,
            interaction_type='cheer'
        )
        
        response = self.client.get('/api/feed/activities/trending/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data), 0)


class SocialFeedPostAPITest(APITestCase):
    """Test cases for SocialFeedPost API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            phone_number='+1234567890',
            username='testuser',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    def test_create_social_post(self):
        """Test creating social post"""
        data = {
            'post_type': 'photo',
            'title': 'Morning workout',
            'content': 'Great start to the day!',
            'location_name': 'Local Gym'
        }
        
        response = self.client.post('/api/feed/posts/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        post = SocialFeedPost.objects.get(id=response.data['id'])
        self.assertEqual(post.user, self.user)
        self.assertEqual(post.title, 'Morning workout')
    
    def test_react_to_post(self):
        """Test reacting to social post"""
        post = SocialFeedPost.objects.create(
            user=self.user,
            post_type='text',
            content='Test post'
        )
        
        response = self.client.post(
            f'/api/feed/posts/{post.id}/react/',
            {'interaction_type': 'fire'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check reaction was created
        self.assertTrue(
            SocialPostInteraction.objects.filter(
                post=post,
                user=self.user,
                interaction_type='fire'
            ).exists()
        )


class UserLocationAPITest(APITestCase):
    """Test cases for UserLocation API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            phone_number='+1234567890',
            username='testuser',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    def test_update_location(self):
        """Test updating user location"""
        data = {
            'latitude': 40.7128,
            'longitude': -74.0060,
            'city': 'New York',
            'country': 'USA',
            'is_location_enabled': True,
            'location_precision': 'city'
        }
        
        response = self.client.put('/api/feed/location/1/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        location = UserLocation.objects.get(user=self.user)
        self.assertEqual(location.city, 'New York')
        self.assertTrue(location.is_location_enabled)
    
    def test_get_nearby_friends(self):
        """Test getting nearby friend recommendations"""
        # Create user location
        UserLocation.objects.create(
            user=self.user,
            latitude=40.7128,
            longitude=-74.0060,
            is_location_enabled=True
        )
        
        response = self.client.get('/api/feed/location/nearby_friends/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_location_stats(self):
        """Test getting location statistics"""
        response = self.client.get('/api/feed/location/location_stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('location_enabled', response.data)


class ActivityFeedUtilsTest(TestCase):
    """Test cases for activity feed utility functions"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            phone_number='+1234567890',
            username='testuser',
            password='testpass123'
        )
        self.friend = User.objects.create_user(
            phone_number='+1234567891',
            username='friend',
            password='testpass123'
        )
        
        # Create friendship
        friendship = Friendship.send_friend_request(self.user, self.friend)[0]
        friendship.accept()
    
    def test_activity_feed_manager(self):
        """Test ActivityFeedManager functionality"""
        # Create task completion activity
        task = Task.objects.create(
            user=self.user,
            title='Test Task',
            points_value=20
        )
        
        activity = ActivityFeedManager.create_task_completion_activity(task, 20)
        
        self.assertIsNotNone(activity)
        self.assertEqual(activity.user, self.user)
        self.assertEqual(activity.activity_type, 'task_completed')
        self.assertEqual(activity.points_earned, 20)
    
    def test_location_manager(self):
        """Test LocationManager functionality"""
        location = LocationManager.update_user_location(
            self.user,
            latitude=40.7128,
            longitude=-74.0060,
            city='New York',
            is_enabled=True
        )
        
        self.assertEqual(location.user, self.user)
        self.assertEqual(location.city, 'New York')
        self.assertTrue(location.is_location_enabled)
    
    def test_social_feed_analytics(self):
        """Test SocialFeedAnalytics functionality"""
        # Create some activities
        ActivityFeed.objects.create(
            user=self.user,
            activity_type='task_completed',
            title='Test activity',
            points_earned=20
        )
        
        # Create interaction
        activity = ActivityFeed.objects.create(
            user=self.friend,
            activity_type='achievement_earned',
            title='Friend activity',
            points_earned=50
        )
        
        ActivityInteraction.objects.create(
            activity=activity,
            user=self.user,
            interaction_type='like'
        )
        
        # Get engagement stats
        stats = SocialFeedAnalytics.get_user_engagement_stats(self.user, days=30)
        
        self.assertEqual(stats['activities_count'], 1)
        self.assertEqual(stats['total_points_earned'], 20)
        self.assertEqual(stats['interactions_given'], 1)


class NearbyFriendRecommendationTest(TestCase):
    """Test cases for nearby friend recommendations"""
    
    def setUp(self):
        """Set up test data"""
        self.user1 = User.objects.create_user(
            phone_number='+1234567890',
            username='user1',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            phone_number='+1234567891',
            username='user2',
            password='testpass123'
        )
        
        # Create locations
        UserLocation.objects.create(
            user=self.user1,
            latitude=40.7128,
            longitude=-74.0060,
            is_location_enabled=True
        )
        
        UserLocation.objects.create(
            user=self.user2,
            latitude=40.7589,  # Close to user1
            longitude=-73.9851,
            is_location_enabled=True
        )
    
    def test_generate_recommendations(self):
        """Test generating nearby friend recommendations"""
        recommendations = NearbyFriendRecommendation.generate_recommendations_for_user(self.user1)
        
        self.assertGreater(recommendations.count(), 0)
        
        recommendation = recommendations.first()
        self.assertEqual(recommendation.user, self.user1)
        self.assertEqual(recommendation.recommended_user, self.user2)
        self.assertGreater(recommendation.recommendation_score, 0)
    
    def test_recommendation_scoring(self):
        """Test recommendation score calculation"""
        recommendation = NearbyFriendRecommendation.objects.create(
            user=self.user1,
            recommended_user=self.user2,
            distance_km=5.0
        )
        
        score = recommendation.calculate_recommendation_score()
        
        self.assertGreater(score, 100)  # Base score + distance bonus
        self.assertEqual(recommendation.recommendation_score, score)


class MilestoneAchievementAPITest(APITestCase):
    """Test cases for milestone and achievement celebration endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            phone_number='+1234567890',
            username='testuser',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    def test_create_milestone_celebration(self):
        """Test creating milestone celebration post"""
        data = {
            'milestone_type': 'tasks completed',
            'milestone_value': 100,
            'custom_message': 'Feeling accomplished! 💪'
        }
        
        response = self.client.post('/api/feed/milestones/create_milestone_celebration/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check that both activity and post were created
        self.assertTrue(
            ActivityFeed.objects.filter(
                user=self.user,
                activity_type='milestone_reached'
            ).exists()
        )
        
        self.assertTrue(
            SocialFeedPost.objects.filter(
                user=self.user,
                post_type='milestone'
            ).exists()
        )
        
        post = SocialFeedPost.objects.get(user=self.user, post_type='milestone')
        self.assertIn('100 tasks completed', post.title)
        self.assertEqual(post.content, 'Feeling accomplished! 💪')
    
    def test_create_achievement_celebration(self):
        """Test creating achievement celebration post"""
        data = {
            'achievement_name': 'Fitness Enthusiast',
            'achievement_description': 'Completed 50 workout tasks',
            'custom_message': 'Finally earned this badge! 🏆'
        }
        
        response = self.client.post('/api/feed/milestones/create_achievement_celebration/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check that both activity and post were created
        self.assertTrue(
            ActivityFeed.objects.filter(
                user=self.user,
                activity_type='achievement_earned'
            ).exists()
        )
        
        self.assertTrue(
            SocialFeedPost.objects.filter(
                user=self.user,
                post_type='achievement'
            ).exists()
        )
        
        post = SocialFeedPost.objects.get(user=self.user, post_type='achievement')
        self.assertIn('Fitness Enthusiast', post.title)
        self.assertEqual(post.content, 'Finally earned this badge! 🏆')
    
    def test_create_celebration_post(self):
        """Test creating general celebration post"""
        data = {
            'title': 'Great workout today!',
            'content': 'Pushed my limits and feel amazing!',
            'celebration_type': 'workout'
        }
        
        response = self.client.post('/api/feed/milestones/create_celebration_post/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check that both activity and post were created
        self.assertTrue(
            ActivityFeed.objects.filter(
                user=self.user,
                activity_type='celebration'
            ).exists()
        )
        
        self.assertTrue(
            SocialFeedPost.objects.filter(
                user=self.user,
                post_type='celebration'
            ).exists()
        )
    
    def test_milestone_celebration_with_photos(self):
        """Test creating milestone celebration with photos"""
        # Create test image
        image = Image.new('RGB', (100, 100), color='blue')
        image_file = io.BytesIO()
        image.save(image_file, 'JPEG')
        image_file.seek(0)
        
        data = {
            'milestone_type': 'points earned',
            'milestone_value': 1000,
            'custom_message': 'Hit 1000 points! 🎯'
        }
        
        response = self.client.post(
            '/api/feed/milestones/create_milestone_celebration/',
            data,
            files={'photos': SimpleUploadedFile('test.jpg', image_file.getvalue(), content_type='image/jpeg')}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        post = SocialFeedPost.objects.get(user=self.user, post_type='milestone')
        self.assertEqual(post.photos.count(), 1)
    
    def test_milestone_celebration_validation(self):
        """Test validation for milestone celebration"""
        # Missing required fields
        response = self.client.post('/api/feed/milestones/create_milestone_celebration/', {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Missing milestone_value
        data = {'milestone_type': 'tasks completed'}
        response = self.client.post('/api/feed/milestones/create_milestone_celebration/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_achievement_celebration_validation(self):
        """Test validation for achievement celebration"""
        # Missing required fields
        response = self.client.post('/api/feed/milestones/create_achievement_celebration/', {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class SocialInteractionAPITest(APITestCase):
    """Test cases for social interaction endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            phone_number='+1234567890',
            username='testuser',
            password='testpass123'
        )
        self.friend = User.objects.create_user(
            phone_number='+1234567891',
            username='friend',
            password='testpass123'
        )
        
        # Create friendship
        friendship = Friendship.send_friend_request(self.user, self.friend)[0]
        friendship.accept()
        
        self.client.force_authenticate(user=self.user)
        
        # Create test content
        self.activity = ActivityFeed.objects.create(
            user=self.friend,
            activity_type='task_completed',
            title='Completed morning run',
            points_earned=20
        )
        
        self.post = SocialFeedPost.objects.create(
            user=self.friend,
            post_type='photo',
            title='Great workout!',
            content='Feeling strong today'
        )
    
    def test_bulk_interact(self):
        """Test bulk interaction functionality"""
        data = {
            'interactions': [
                {
                    'content_type': 'activity',
                    'content_id': self.activity.id,
                    'interaction_type': 'like'
                },
                {
                    'content_type': 'post',
                    'content_id': self.post.id,
                    'interaction_type': 'fire'
                },
                {
                    'content_type': 'activity',
                    'content_id': self.activity.id,
                    'interaction_type': 'comment',
                    'comment_text': 'Great job!'
                }
            ]
        }
        
        response = self.client.post('/api/feed/interactions/bulk_interact/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check that interactions were created
        self.assertTrue(
            ActivityInteraction.objects.filter(
                activity=self.activity,
                user=self.user,
                interaction_type='like'
            ).exists()
        )
        
        self.assertTrue(
            ActivityInteraction.objects.filter(
                activity=self.activity,
                user=self.user,
                interaction_type='comment',
                comment_text='Great job!'
            ).exists()
        )
        
        self.assertTrue(
            SocialPostInteraction.objects.filter(
                post=self.post,
                user=self.user,
                interaction_type='fire'
            ).exists()
        )
        
        # Check response format
        results = response.data['results']
        self.assertEqual(len(results), 3)
        for result in results:
            self.assertEqual(result['status'], 'success')
    
    def test_bulk_interact_with_invalid_content(self):
        """Test bulk interaction with invalid content"""
        data = {
            'interactions': [
                {
                    'content_type': 'activity',
                    'content_id': 99999,  # Non-existent ID
                    'interaction_type': 'like'
                },
                {
                    'content_type': 'post',
                    'content_id': self.post.id,
                    'interaction_type': 'love'
                }
            ]
        }
        
        response = self.client.post('/api/feed/interactions/bulk_interact/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        results = response.data['results']
        self.assertEqual(results[0]['status'], 'error')
        self.assertEqual(results[0]['message'], 'Content not found')
        self.assertEqual(results[1]['status'], 'success')
    
    def test_get_my_interactions(self):
        """Test getting user's interactions"""
        # Create some interactions
        ActivityInteraction.objects.create(
            activity=self.activity,
            user=self.user,
            interaction_type='like'
        )
        
        ActivityInteraction.objects.create(
            activity=self.activity,
            user=self.user,
            interaction_type='comment',
            comment_text='Nice work!'
        )
        
        SocialPostInteraction.objects.create(
            post=self.post,
            user=self.user,
            interaction_type='celebrate'
        )
        
        response = self.client.get('/api/feed/interactions/my_interactions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.assertEqual(response.data['total_count'], 3)
        self.assertEqual(len(response.data['interactions']), 3)
        
        # Check interaction data structure
        interaction = response.data['interactions'][0]
        self.assertIn('content_type', interaction)
        self.assertIn('content_id', interaction)
        self.assertIn('interaction_type', interaction)
        self.assertIn('created_at', interaction)
    
    def test_get_my_interactions_with_date_filter(self):
        """Test getting user's interactions with date filter"""
        # Create old interaction (should be filtered out)
        old_interaction = ActivityInteraction.objects.create(
            activity=self.activity,
            user=self.user,
            interaction_type='like'
        )
        old_interaction.created_at = timezone.now() - timezone.timedelta(days=10)
        old_interaction.save()
        
        # Create recent interaction
        ActivityInteraction.objects.create(
            activity=self.activity,
            user=self.user,
            interaction_type='cheer'
        )
        
        response = self.client.get('/api/feed/interactions/my_interactions/?days=7')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should only return recent interaction
        self.assertEqual(response.data['total_count'], 1)
        self.assertEqual(response.data['interactions'][0]['interaction_type'], 'cheer')
    
    def test_get_interaction_stats(self):
        """Test getting interaction statistics"""
        # Create interactions given by user
        ActivityInteraction.objects.create(
            activity=self.activity,
            user=self.user,
            interaction_type='like'
        )
        
        ActivityInteraction.objects.create(
            activity=self.activity,
            user=self.user,
            interaction_type='comment',
            comment_text='Great!'
        )
        
        SocialPostInteraction.objects.create(
            post=self.post,
            user=self.user,
            interaction_type='celebrate'
        )
        
        # Create interactions received by user
        user_activity = ActivityFeed.objects.create(
            user=self.user,
            activity_type='achievement_earned',
            title='Test achievement'
        )
        
        ActivityInteraction.objects.create(
            activity=user_activity,
            user=self.friend,
            interaction_type='cheer'
        )
        
        response = self.client.get('/api/feed/interactions/interaction_stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        stats = response.data
        self.assertEqual(stats['given']['total'], 3)
        self.assertEqual(stats['given']['likes'], 1)
        self.assertEqual(stats['given']['comments'], 1)
        self.assertEqual(stats['given']['celebrates'], 1)
        
        self.assertEqual(stats['received']['total'], 1)
        self.assertEqual(stats['received']['cheers'], 1)
    
    def test_bulk_interact_validation(self):
        """Test validation for bulk interactions"""
        # Empty interactions list
        response = self.client.post('/api/feed/interactions/bulk_interact/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Invalid interaction data
        data = {
            'interactions': [
                {
                    'content_type': 'invalid',
                    'content_id': self.activity.id,
                    'interaction_type': 'like'
                }
            ]
        }
        
        response = self.client.post('/api/feed/interactions/bulk_interact/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should return error for invalid content type
        results = response.data['results']
        self.assertEqual(results[0]['status'], 'error')


class ActivityInteractionModelTest(TestCase):
    """Test cases for ActivityInteraction model validation and behavior"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            phone_number='+1234567890',
            username='testuser',
            password='testpass123'
        )
        self.friend = User.objects.create_user(
            phone_number='+1234567891',
            username='friend',
            password='testpass123'
        )
        
        self.activity = ActivityFeed.objects.create(
            user=self.friend,
            activity_type='task_completed',
            title='Test activity'
        )
    
    def test_comment_interaction_validation(self):
        """Test that comment interactions require comment text"""
        from django.core.exceptions import ValidationError
        
        # Comment without text should fail validation
        interaction = ActivityInteraction(
            activity=self.activity,
            user=self.user,
            interaction_type='comment',
            comment_text=''
        )
        
        with self.assertRaises(ValidationError):
            interaction.clean()
    
    def test_non_comment_interaction_validation(self):
        """Test that non-comment interactions should not have comment text"""
        from django.core.exceptions import ValidationError
        
        # Like with comment text should fail validation
        interaction = ActivityInteraction(
            activity=self.activity,
            user=self.user,
            interaction_type='like',
            comment_text='This should not be here'
        )
        
        with self.assertRaises(ValidationError):
            interaction.clean()
    
    def test_valid_interactions(self):
        """Test valid interaction creation"""
        # Valid like interaction
        like = ActivityInteraction.objects.create(
            activity=self.activity,
            user=self.user,
            interaction_type='like'
        )
        self.assertEqual(like.interaction_type, 'like')
        self.assertEqual(like.comment_text, '')
        
        # Valid comment interaction
        comment = ActivityInteraction.objects.create(
            activity=self.activity,
            user=self.user,
            interaction_type='comment',
            comment_text='Great job!'
        )
        self.assertEqual(comment.interaction_type, 'comment')
        self.assertEqual(comment.comment_text, 'Great job!')
    
    def test_unique_constraint(self):
        """Test unique constraint for non-comment interactions"""
        # Create first like
        ActivityInteraction.objects.create(
            activity=self.activity,
            user=self.user,
            interaction_type='like'
        )
        
        # Creating another like should replace the first one (handled in views)
        # But at model level, unique constraint should prevent duplicates
        from django.db import IntegrityError
        
        with self.assertRaises(IntegrityError):
            ActivityInteraction.objects.create(
                activity=self.activity,
                user=self.user,
                interaction_type='like'
            )


class SocialFeedIntegrationTest(APITestCase):
    """Integration tests for complete social feed functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user1 = User.objects.create_user(
            phone_number='+1234567890',
            username='user1',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            phone_number='+1234567891',
            username='user2',
            password='testpass123'
        )
        self.user3 = User.objects.create_user(
            phone_number='+1234567892',
            username='user3',
            password='testpass123'
        )
        
        # Create friendships
        friendship1 = Friendship.send_friend_request(self.user1, self.user2)[0]
        friendship1.accept()
        
        friendship2 = Friendship.send_friend_request(self.user1, self.user3)[0]
        friendship2.accept()
        
        self.client.force_authenticate(user=self.user1)
    
    def test_complete_social_interaction_flow(self):
        """Test complete flow of creating content and interactions"""
        # User2 creates a milestone celebration
        self.client.force_authenticate(user=self.user2)
        
        milestone_data = {
            'milestone_type': 'tasks completed',
            'milestone_value': 50,
            'custom_message': 'Halfway to 100! 🎯'
        }
        
        response = self.client.post('/api/feed/milestones/create_milestone_celebration/', milestone_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        milestone_post_id = response.data['post']['id']
        
        # User3 creates an achievement celebration
        self.client.force_authenticate(user=self.user3)
        
        achievement_data = {
            'achievement_name': 'Early Bird',
            'achievement_description': 'Completed 10 morning tasks',
            'custom_message': 'Love starting my day productive! ☀️'
        }
        
        response = self.client.post('/api/feed/milestones/create_achievement_celebration/', achievement_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        achievement_post_id = response.data['post']['id']
        
        # User1 views their feed and sees both celebrations
        self.client.force_authenticate(user=self.user1)
        
        response = self.client.get('/api/feed/activities/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        activities = response.data['results']
        self.assertGreaterEqual(len(activities), 2)
        
        # User1 interacts with both posts using bulk interaction
        bulk_data = {
            'interactions': [
                {
                    'content_type': 'post',
                    'content_id': milestone_post_id,
                    'interaction_type': 'celebrate'
                },
                {
                    'content_type': 'post',
                    'content_id': achievement_post_id,
                    'interaction_type': 'fire'
                },
                {
                    'content_type': 'post',
                    'content_id': milestone_post_id,
                    'interaction_type': 'comment',
                    'comment_text': 'Keep it up! You got this! 💪'
                }
            ]
        }
        
        response = self.client.post('/api/feed/interactions/bulk_interact/', bulk_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify all interactions were successful
        results = response.data['results']
        for result in results:
            self.assertEqual(result['status'], 'success')
        
        # Check interaction statistics
        response = self.client.get('/api/feed/interactions/interaction_stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        stats = response.data
        self.assertEqual(stats['given']['total'], 3)
        self.assertEqual(stats['given']['celebrates'], 1)
        self.assertEqual(stats['given']['comments'], 1)
        
        # User2 checks their received interactions
        self.client.force_authenticate(user=self.user2)
        
        response = self.client.get('/api/feed/interactions/interaction_stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        stats = response.data
        self.assertGreater(stats['received']['total'], 0)
        
        # Test trending activities (posts with interactions should appear)
        self.client.force_authenticate(user=self.user1)
        
        response = self.client.get('/api/feed/activities/trending/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should have trending activities due to interactions
        self.assertGreater(len(response.data), 0)
    
    def test_privacy_and_visibility(self):
        """Test privacy settings and content visibility"""
        # Create private post by user2
        self.client.force_authenticate(user=self.user2)
        
        private_post_data = {
            'post_type': 'text',
            'content': 'This is a private post',
            'is_public': False
        }
        
        response = self.client.post('/api/feed/posts/', private_post_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        private_post_id = response.data['id']
        
        # User1 (friend) should not see private post in feed
        self.client.force_authenticate(user=self.user1)
        
        response = self.client.get('/api/feed/posts/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        post_ids = [post['id'] for post in response.data['results']]
        self.assertNotIn(private_post_id, post_ids)
        
        # User1 should not be able to interact with private post
        interaction_data = {
            'interactions': [
                {
                    'content_type': 'post',
                    'content_id': private_post_id,
                    'interaction_type': 'like'
                }
            ]
        }
        
        response = self.client.post('/api/feed/interactions/bulk_interact/', interaction_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should return permission denied
        results = response.data['results']
        self.assertEqual(results[0]['status'], 'error')
        self.assertEqual(results[0]['message'], 'Permission denied')