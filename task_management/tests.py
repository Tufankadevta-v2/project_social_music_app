from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from rest_framework.test import APITestCase
from rest_framework import status
from user_accounts.models import User
from .models import Task, SharedTask, TaskParticipation
from .serializers import TaskSerializer, TaskCompletionSerializer


class TaskModelTest(TestCase):
    """
    Test cases for Task model
    """
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            phone_number='+1234567890',
            username='testuser',
            password='testpass123'
        )
        
    def test_task_creation(self):
        """Test basic task creation"""
        task = Task.objects.create(
            user=self.user,
            title='Test Task',
            description='Test description',
            priority='high',
            points_value=20
        )
        
        self.assertEqual(task.title, 'Test Task')
        self.assertEqual(task.user, self.user)
        self.assertEqual(task.status, 'pending')
        self.assertEqual(task.priority, 'high')
        self.assertEqual(task.points_value, 20)
        self.assertFalse(task.is_shared)
        self.assertFalse(task.is_private)
    
    def test_default_points_calculation(self):
        """Test automatic points calculation based on priority"""
        # Test with default points (should calculate based on priority)
        high_task = Task.objects.create(
            user=self.user,
            title='High Priority Task',
            priority='high'
        )
        
        medium_task = Task.objects.create(
            user=self.user,
            title='Medium Priority Task',
            priority='medium'
        )
        
        low_task = Task.objects.create(
            user=self.user,
            title='Low Priority Task',
            priority='low'
        )
        
        self.assertEqual(high_task.points_value, 20)
        self.assertEqual(medium_task.points_value, 10)
        self.assertEqual(low_task.points_value, 5)
    
    def test_task_completion(self):
        """Test task completion functionality"""
        task = Task.objects.create(
            user=self.user,
            title='Test Task',
            priority='medium'
        )
        
        # Initially not completed
        self.assertEqual(task.status, 'pending')
        self.assertIsNone(task.completed_at)
        
        # Mark as completed
        result = task.mark_completed()
        
        self.assertTrue(result)
        self.assertEqual(task.status, 'completed')
        self.assertIsNotNone(task.completed_at)
        
        # Try to complete again (should return False)
        result = task.mark_completed()
        self.assertFalse(result)
    
    def test_overdue_detection(self):
        """Test overdue task detection"""
        # Create task with past deadline
        past_deadline = timezone.now() - timezone.timedelta(hours=1)
        task = Task.objects.create(
            user=self.user,
            title='Overdue Task',
            deadline=past_deadline
        )
        
        # Task should be automatically marked as overdue during creation
        self.assertTrue(task.is_overdue())
        self.assertEqual(task.status, 'overdue')
        
        # Test with a task that becomes overdue after creation
        future_deadline = timezone.now() + timezone.timedelta(seconds=1)
        pending_task = Task.objects.create(
            user=self.user,
            title='Soon Overdue Task',
            deadline=future_deadline,
            status='pending'
        )
        
        # Initially pending
        self.assertEqual(pending_task.status, 'pending')
        
        # Wait a moment and update
        import time
        time.sleep(1.1)
        
        result = pending_task.update_overdue_status()
        self.assertTrue(result)
        self.assertEqual(pending_task.status, 'overdue')
    
    def test_completion_points_calculation(self):
        """Test points calculation for task completion"""
        # Task with deadline - early completion
        future_deadline = timezone.now() + timezone.timedelta(hours=2)
        task = Task.objects.create(
            user=self.user,
            title='Early Task',
            deadline=future_deadline,
            points_value=10
        )
        
        task.mark_completed()
        points = task.calculate_completion_points()
        
        # Should get bonus for early completion
        self.assertGreater(points, 10)
        
        # Task with past deadline - late completion
        past_deadline = timezone.now() - timezone.timedelta(hours=1)
        late_task = Task.objects.create(
            user=self.user,
            title='Late Task',
            deadline=past_deadline,
            points_value=10
        )
        
        late_task.mark_completed()
        late_points = late_task.calculate_completion_points()
        
        # Should get penalty for late completion
        self.assertLess(late_points, 10)
    
    def test_days_until_deadline(self):
        """Test days until deadline calculation"""
        # Task with future deadline (use hours to be more precise)
        future_deadline = timezone.now() + timezone.timedelta(hours=72)  # 3 days
        task = Task.objects.create(
            user=self.user,
            title='Future Task',
            deadline=future_deadline
        )
        
        # Should be 2 or 3 days depending on exact timing
        days_until = task.days_until_deadline
        self.assertIn(days_until, [2, 3])
        
        # Task without deadline
        no_deadline_task = Task.objects.create(
            user=self.user,
            title='No Deadline Task'
        )
        
        self.assertIsNone(no_deadline_task.days_until_deadline)


class SharedTaskModelTest(TestCase):
    """
    Test cases for SharedTask and TaskParticipation models
    """
    
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
        
        self.task = Task.objects.create(
            user=self.user1,
            title='Shared Task',
            is_shared=True,
            points_value=20
        )
        
        self.shared_task = SharedTask.objects.create(
            task=self.task,
            creator=self.user1,
            is_competitive=True
        )
    
    def test_shared_task_creation(self):
        """Test shared task creation"""
        self.assertEqual(self.shared_task.task, self.task)
        self.assertEqual(self.shared_task.creator, self.user1)
        self.assertTrue(self.shared_task.is_competitive)
        self.assertEqual(self.shared_task.max_participants, 10)
    
    def test_task_participation(self):
        """Test task participation functionality"""
        # Add participants
        participation1 = TaskParticipation.objects.create(
            shared_task=self.shared_task,
            user=self.user1
        )
        participation2 = TaskParticipation.objects.create(
            shared_task=self.shared_task,
            user=self.user2
        )
        
        self.assertEqual(self.shared_task.get_participant_count(), 2)
        self.assertTrue(self.shared_task.can_add_participant())
        
        # Test completion
        result = participation1.mark_completed()
        self.assertTrue(result)
        self.assertEqual(participation1.status, 'completed')
        self.assertIsNotNone(participation1.completed_at)
        
        # First to complete should get bonus points
        self.assertGreater(participation1.points_earned, 20)
        
        # Second to complete
        participation2.mark_completed()
        self.assertLess(participation2.points_earned, participation1.points_earned)
    
    def test_completion_stats(self):
        """Test completion statistics"""
        # Add participants
        TaskParticipation.objects.create(
            shared_task=self.shared_task,
            user=self.user1
        )
        participation2 = TaskParticipation.objects.create(
            shared_task=self.shared_task,
            user=self.user2
        )
        
        # Initially no completions
        stats = self.shared_task.get_completion_stats()
        self.assertEqual(stats['total_participants'], 2)
        self.assertEqual(stats['completed_count'], 0)
        self.assertEqual(stats['completion_rate'], 0)
        
        # Complete one task
        participation2.mark_completed()
        
        stats = self.shared_task.get_completion_stats()
        self.assertEqual(stats['completed_count'], 1)
        self.assertEqual(stats['completion_rate'], 50.0)


class TaskAPITest(APITestCase):
    """
    Test cases for Task API endpoints
    """
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            phone_number='+1234567890',
            username='testuser',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
    def test_create_task(self):
        """Test task creation via API"""
        data = {
            'title': 'API Test Task',
            'description': 'Test description',
            'priority': 'high',
            'points_value': 15
        }
        
        response = self.client.post('/api/tasks/tasks/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        task = Task.objects.get(id=response.data['id'])
        self.assertEqual(task.title, 'API Test Task')
        self.assertEqual(task.user, self.user)
        self.assertEqual(task.priority, 'high')
    
    def test_list_tasks(self):
        """Test task listing via API"""
        # Create test tasks
        Task.objects.create(
            user=self.user,
            title='Task 1',
            priority='high'
        )
        Task.objects.create(
            user=self.user,
            title='Task 2',
            priority='low'
        )
        
        response = self.client.get('/api/tasks/tasks/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_complete_task(self):
        """Test task completion via API"""
        task = Task.objects.create(
            user=self.user,
            title='Complete Me',
            points_value=10
        )
        
        response = self.client.post(f'/api/tasks/tasks/{task.id}/complete_task/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        task.refresh_from_db()
        self.assertEqual(task.status, 'completed')
        self.assertIsNotNone(task.completed_at)
        
        # Check response data
        self.assertIn('points_earned', response.data)
        self.assertIn('message', response.data)
    
    def test_task_filtering(self):
        """Test task filtering functionality"""
        # Create tasks with different statuses
        Task.objects.create(
            user=self.user,
            title='Pending Task',
            status='pending'
        )
        completed_task = Task.objects.create(
            user=self.user,
            title='Completed Task'
        )
        completed_task.mark_completed()
        
        # Filter by status
        response = self.client.get('/api/tasks/tasks/?status=pending')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['title'], 'Pending Task')
        
        response = self.client.get('/api/tasks/tasks/?status=completed')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['title'], 'Completed Task')
    
    def test_task_statistics(self):
        """Test task statistics endpoint"""
        # Create test tasks
        Task.objects.create(user=self.user, title='Task 1', priority='high')
        completed_task = Task.objects.create(user=self.user, title='Task 2', priority='medium')
        completed_task.mark_completed()
        
        response = self.client.get('/api/tasks/tasks/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        stats = response.data
        self.assertEqual(stats['total_tasks'], 2)
        self.assertEqual(stats['completed_tasks'], 1)
        self.assertEqual(stats['pending_tasks'], 1)
        self.assertIn('tasks_by_priority', stats)


class TaskCompletionAndPointsTest(TestCase):
    """
    Test cases for task completion and point system functionality
    """
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            phone_number='+1234567890',
            username='testuser',
            password='testpass123'
        )
        # Get or create user profile for point tracking
        from user_accounts.models import UserProfile
        self.user_profile, created = UserProfile.objects.get_or_create(
            user=self.user,
            defaults={'total_points': 0}
        )
    
    def test_point_calculation_early_completion(self):
        """Test point calculation for early task completion"""
        # Create task with deadline 4 hours from now
        deadline = timezone.now() + timezone.timedelta(hours=4)
        task = Task.objects.create(
            user=self.user,
            title='Early Completion Task',
            deadline=deadline,
            points_value=20
        )
        
        # Complete task immediately (very early)
        task.mark_completed()
        points = task.calculate_completion_points()
        
        # Should get 50% bonus for completing in first half of time
        self.assertEqual(points, 30)  # 20 * 1.5
    
    def test_point_calculation_late_completion(self):
        """Test point calculation for late task completion"""
        # Create task with past deadline
        past_deadline = timezone.now() - timezone.timedelta(hours=2)
        task = Task.objects.create(
            user=self.user,
            title='Late Completion Task',
            deadline=past_deadline,
            points_value=20
        )
        
        # Complete task after deadline
        task.mark_completed()
        points = task.calculate_completion_points()
        
        # Should get 25% penalty for late completion
        self.assertEqual(points, 15)  # 20 * 0.75
    
    def test_point_calculation_no_deadline(self):
        """Test point calculation for tasks without deadline"""
        task = Task.objects.create(
            user=self.user,
            title='No Deadline Task',
            points_value=15
        )
        
        task.mark_completed()
        points = task.calculate_completion_points()
        
        # Should get base points
        self.assertEqual(points, 15)
    
    def test_overdue_task_detection_and_update(self):
        """Test overdue task detection and status updates"""
        # Create task with future deadline first
        future_deadline = timezone.now() + timezone.timedelta(hours=1)
        task = Task.objects.create(
            user=self.user,
            title='Future Task',
            deadline=future_deadline
        )
        
        # Initially should not be overdue
        self.assertFalse(task.is_overdue())
        self.assertEqual(task.status, 'pending')
        
        # Manually update deadline to past using update() to bypass save() logic
        past_deadline = timezone.now() - timezone.timedelta(hours=1)
        Task.objects.filter(id=task.id).update(deadline=past_deadline)
        task.refresh_from_db()
        
        # Now task should detect it's overdue
        self.assertTrue(task.is_overdue())
        
        # Update overdue status
        result = task.update_overdue_status()
        self.assertTrue(result)
        self.assertEqual(task.status, 'overdue')
        
        # Trying to update again should return False
        result = task.update_overdue_status()
        self.assertFalse(result)
    
    def test_competitive_points_calculation(self):
        """Test competitive point calculation in shared tasks"""
        # Create shared task
        task = Task.objects.create(
            user=self.user,
            title='Competitive Task',
            is_shared=True,
            points_value=20
        )
        
        shared_task = SharedTask.objects.create(
            task=task,
            creator=self.user,
            is_competitive=True
        )
        
        # Create participants
        user2 = User.objects.create_user(
            phone_number='+1234567891',
            username='user2',
            password='testpass123'
        )
        
        participation1 = TaskParticipation.objects.create(
            shared_task=shared_task,
            user=self.user
        )
        participation2 = TaskParticipation.objects.create(
            shared_task=shared_task,
            user=user2
        )
        
        # First completion should get 2x points
        participation1.mark_completed()
        self.assertEqual(participation1.points_earned, 40)  # 20 * 2.0
        self.assertEqual(participation1.completion_rank, 1)
        
        # Second completion should get 1.5x points
        participation2.mark_completed()
        self.assertEqual(participation2.points_earned, 30)  # 20 * 1.5
        self.assertEqual(participation2.completion_rank, 2)
    
    def test_minimum_points_awarded(self):
        """Test that minimum 1 point is always awarded"""
        # Create task with very low points and late completion
        past_deadline = timezone.now() - timezone.timedelta(hours=5)
        task = Task.objects.create(
            user=self.user,
            title='Low Points Task',
            deadline=past_deadline,
            points_value=1  # Very low base points
        )
        
        task.mark_completed()
        points = task.calculate_completion_points()
        
        # Should get at least 1 point even with penalty
        self.assertEqual(points, 1)


class TaskDeletionTest(APITestCase):
    """
    Test cases for task deletion with proper cleanup
    """
    
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
        
    def test_delete_regular_task(self):
        """Test deletion of regular (non-shared) task"""
        self.client.force_authenticate(user=self.user1)
        
        task = Task.objects.create(
            user=self.user1,
            title='Regular Task'
        )
        
        response = self.client.delete(f'/api/tasks/tasks/{task.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('deleted successfully', response.data['message'])
        self.assertFalse(response.data['deleted_shared_task'])
        
        # Task should be deleted
        self.assertFalse(Task.objects.filter(id=task.id).exists())
    
    def test_delete_shared_task_as_creator(self):
        """Test deletion of shared task by creator"""
        self.client.force_authenticate(user=self.user1)
        
        # Create shared task
        task = Task.objects.create(
            user=self.user1,
            title='Shared Task',
            is_shared=True
        )
        
        shared_task = SharedTask.objects.create(
            task=task,
            creator=self.user1
        )
        
        # Add participants
        TaskParticipation.objects.create(
            shared_task=shared_task,
            user=self.user1
        )
        TaskParticipation.objects.create(
            shared_task=shared_task,
            user=self.user2
        )
        
        response = self.client.delete(f'/api/tasks/tasks/{task.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['deleted_shared_task'])
        self.assertIn('participants were notified', response.data['message'])
        
        # Both task and shared task should be deleted
        self.assertFalse(Task.objects.filter(id=task.id).exists())
        self.assertFalse(SharedTask.objects.filter(id=shared_task.id).exists())
    
    def test_delete_shared_task_as_participant(self):
        """Test deletion of shared task by participant (should leave task)"""
        self.client.force_authenticate(user=self.user2)
        
        # Create shared task
        task = Task.objects.create(
            user=self.user1,
            title='Shared Task',
            is_shared=True
        )
        
        shared_task = SharedTask.objects.create(
            task=task,
            creator=self.user1
        )
        
        # Add participants
        TaskParticipation.objects.create(
            shared_task=shared_task,
            user=self.user1
        )
        participation = TaskParticipation.objects.create(
            shared_task=shared_task,
            user=self.user2
        )
        
        response = self.client.delete(f'/api/tasks/tasks/{task.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['left_shared_task'])
        self.assertIn('removed from the shared task', response.data['message'])
        
        # Task should still exist, but participation should be removed
        self.assertTrue(Task.objects.filter(id=task.id).exists())
        self.assertTrue(SharedTask.objects.filter(id=shared_task.id).exists())
        self.assertFalse(TaskParticipation.objects.filter(id=participation.id).exists())


class OverdueTaskManagementTest(TestCase):
    """
    Test cases for overdue task management command
    """
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            phone_number='+1234567890',
            username='testuser',
            password='testpass123'
        )
    
    def test_update_overdue_tasks_command(self):
        """Test the management command for updating overdue tasks"""
        from django.core.management import call_command
        from io import StringIO
        
        # Create tasks with different statuses
        past_deadline = timezone.now() - timezone.timedelta(hours=2)
        future_deadline = timezone.now() + timezone.timedelta(hours=2)
        
        # Create overdue task by first creating with future deadline, then updating
        overdue_task = Task.objects.create(
            user=self.user,
            title='Should be Overdue',
            deadline=future_deadline,
            status='pending'
        )
        # Update deadline to past using raw SQL to bypass save() logic
        Task.objects.filter(id=overdue_task.id).update(deadline=past_deadline)
        
        # Future task (should not be affected)
        future_task = Task.objects.create(
            user=self.user,
            title='Future Task',
            deadline=future_deadline,
            status='pending'
        )
        
        # Already completed task (should not be affected)
        completed_task = Task.objects.create(
            user=self.user,
            title='Completed Task',
            deadline=future_deadline,
            status='completed'
        )
        Task.objects.filter(id=completed_task.id).update(deadline=past_deadline)
        
        # Run the command
        out = StringIO()
        call_command('update_overdue_tasks', stdout=out)
        
        # Check results
        overdue_task.refresh_from_db()
        future_task.refresh_from_db()
        completed_task.refresh_from_db()
        
        self.assertEqual(overdue_task.status, 'overdue')
        self.assertEqual(future_task.status, 'pending')
        self.assertEqual(completed_task.status, 'completed')
        
        # Check command output
        output = out.getvalue()
        self.assertIn('Successfully updated 1 tasks', output)
    
    def test_update_overdue_tasks_dry_run(self):
        """Test the management command dry run functionality"""
        from django.core.management import call_command
        from io import StringIO
        
        # Create overdue task by first creating with future deadline, then updating
        past_deadline = timezone.now() - timezone.timedelta(hours=1)
        future_deadline = timezone.now() + timezone.timedelta(hours=1)
        
        overdue_task = Task.objects.create(
            user=self.user,
            title='Should be Overdue',
            deadline=future_deadline,
            status='pending'
        )
        # Update deadline to past using raw SQL to bypass save() logic
        Task.objects.filter(id=overdue_task.id).update(deadline=past_deadline)
        
        # Run dry run
        out = StringIO()
        call_command('update_overdue_tasks', '--dry-run', stdout=out)
        
        # Task should not be updated (still pending)
        overdue_task.refresh_from_db()
        self.assertEqual(overdue_task.status, 'pending')
        
        # Check command output
        output = out.getvalue()
        self.assertIn('DRY RUN: Would update 1 tasks', output)


class TaskSerializerTest(TestCase):
    """
    Test cases for Task serializers
    """
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            phone_number='+1234567890',
            username='testuser',
            password='testpass123'
        )
    
    def test_task_serializer_validation(self):
        """Test task serializer validation"""
        # Valid data
        valid_data = {
            'title': 'Valid Task',
            'description': 'Valid description',
            'priority': 'medium',
            'points_value': 15
        }
        
        serializer = TaskSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid())
        
        # Invalid points value
        invalid_data = valid_data.copy()
        invalid_data['points_value'] = 150  # Too high
        
        serializer = TaskSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('points_value', serializer.errors)
        
        # Past deadline
        invalid_data = valid_data.copy()
        invalid_data['deadline'] = timezone.now() - timezone.timedelta(hours=1)
        
        serializer = TaskSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('deadline', serializer.errors)
    
    def test_shared_private_validation(self):
        """Test that shared tasks cannot be private"""
        data = {
            'title': 'Invalid Task',
            'is_shared': True,
            'is_private': True
        }
        
        serializer = TaskSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)
    
    def test_points_to_earn_calculation(self):
        """Test points_to_earn serializer field"""
        from rest_framework.test import APIRequestFactory
        
        factory = APIRequestFactory()
        request = factory.get('/')
        request.user = self.user
        
        # Create task with deadline
        deadline = timezone.now() + timezone.timedelta(hours=2)
        task = Task.objects.create(
            user=self.user,
            title='Test Task',
            deadline=deadline,
            points_value=20
        )
        
        serializer = TaskSerializer(task, context={'request': request})
        
        # Should calculate potential points if completed now
        self.assertIn('points_to_earn', serializer.data)
        self.assertGreater(serializer.data['points_to_earn'], 20)  # Should get bonus for early completion


class SharedTaskAPITest(APITestCase):
    """
    Test cases for SharedTask API endpoints with friend validation
    """
    
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
        
        # Create friendship between user1 and user2
        from friendships.models import Friendship
        friendship = Friendship.send_friend_request(self.user1, self.user2)[0]
        friendship.accept()
        
        self.client.force_authenticate(user=self.user1)
    
    def test_create_shared_task_with_friends(self):
        """Test creating shared task with friend validation"""
        data = {
            'task_data': {
                'title': 'Shared Task with Friends',
                'description': 'Test shared task',
                'priority': 'medium',
                'points_value': 20
            },
            'participant_ids': [self.user2.id],  # user2 is a friend
            'is_competitive': True
        }
        
        response = self.client.post('/api/tasks/shared-tasks/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check that shared task was created
        self.assertTrue(SharedTask.objects.filter(creator=self.user1).exists())
        shared_task = SharedTask.objects.get(creator=self.user1)
        self.assertEqual(shared_task.creator, self.user1)
        self.assertEqual(shared_task.get_participant_count(), 2)  # Creator + invited friend
    
    def test_create_shared_task_with_non_friend(self):
        """Test creating shared task with non-friend should fail"""
        data = {
            'task_data': {
                'title': 'Shared Task with Non-Friend',
                'description': 'Test shared task',
                'priority': 'medium',
                'points_value': 20
            },
            'participant_ids': [self.user3.id],  # user3 is not a friend
            'is_competitive': True
        }
        
        response = self.client.post('/api/tasks/shared-tasks/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not your friend', str(response.data))
    
    def test_invite_participants_to_existing_shared_task(self):
        """Test inviting additional participants to existing shared task"""
        # Create shared task
        task = Task.objects.create(
            user=self.user1,
            title='Existing Shared Task',
            is_shared=True
        )
        shared_task = SharedTask.objects.create(
            task=task,
            creator=self.user1
        )
        TaskParticipation.objects.create(
            shared_task=shared_task,
            user=self.user1
        )
        
        # Invite friend
        data = {'participant_ids': [self.user2.id]}
        response = self.client.post(
            f'/api/tasks/shared-tasks/{shared_task.id}/invite_participants/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['invited_count'], 1)
        self.assertEqual(shared_task.get_participant_count(), 2)
    
    def test_invite_non_friend_to_existing_shared_task(self):
        """Test inviting non-friend to existing shared task should fail"""
        # Create shared task
        task = Task.objects.create(
            user=self.user1,
            title='Existing Shared Task',
            is_shared=True
        )
        shared_task = SharedTask.objects.create(
            task=task,
            creator=self.user1
        )
        TaskParticipation.objects.create(
            shared_task=shared_task,
            user=self.user1
        )
        
        # Try to invite non-friend
        data = {'participant_ids': [self.user3.id]}
        response = self.client.post(
            f'/api/tasks/shared-tasks/{shared_task.id}/invite_participants/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not your friend', str(response.data))
    
    def test_remove_participant_from_shared_task(self):
        """Test removing participant from shared task"""
        # Create shared task with participants
        task = Task.objects.create(
            user=self.user1,
            title='Shared Task',
            is_shared=True
        )
        shared_task = SharedTask.objects.create(
            task=task,
            creator=self.user1
        )
        TaskParticipation.objects.create(
            shared_task=shared_task,
            user=self.user1
        )
        TaskParticipation.objects.create(
            shared_task=shared_task,
            user=self.user2
        )
        
        # Remove participant
        data = {'participant_id': self.user2.id}
        response = self.client.post(
            f'/api/tasks/shared-tasks/{shared_task.id}/remove_participant/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('removed from shared task', response.data['message'])
        self.assertEqual(shared_task.get_participant_count(), 1)  # Only creator left
    
    def test_get_invitable_friends(self):
        """Test getting list of friends who can be invited"""
        # Create shared task
        task = Task.objects.create(
            user=self.user1,
            title='Shared Task',
            is_shared=True
        )
        shared_task = SharedTask.objects.create(
            task=task,
            creator=self.user1
        )
        TaskParticipation.objects.create(
            shared_task=shared_task,
            user=self.user1
        )
        
        response = self.client.get(
            f'/api/tasks/shared-tasks/{shared_task.id}/invitable_friends/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)  # user2 is the only friend
        self.assertEqual(response.data['invitable_friends'][0]['id'], self.user2.id)
    
    def test_get_my_shared_tasks(self):
        """Test getting user's shared tasks grouped by status"""
        # Create shared task where user1 is creator
        task1 = Task.objects.create(
            user=self.user1,
            title='Created Task',
            is_shared=True
        )
        shared_task1 = SharedTask.objects.create(
            task=task1,
            creator=self.user1
        )
        participation1 = TaskParticipation.objects.create(
            shared_task=shared_task1,
            user=self.user1
        )
        
        # Create shared task where user1 is participant
        task2 = Task.objects.create(
            user=self.user2,
            title='Joined Task',
            is_shared=True
        )
        shared_task2 = SharedTask.objects.create(
            task=task2,
            creator=self.user2
        )
        participation2 = TaskParticipation.objects.create(
            shared_task=shared_task2,
            user=self.user1
        )
        
        # Complete one participation
        participation2.mark_completed()
        
        response = self.client.get('/api/tasks/shared-tasks/my_shared_tasks/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_pending'], 1)
        self.assertEqual(response.data['total_completed'], 1)
        self.assertEqual(len(response.data['pending_shared_tasks']), 1)
        self.assertEqual(len(response.data['completed_shared_tasks']), 1)
    
    def test_non_creator_cannot_invite_participants(self):
        """Test that non-creator cannot invite participants"""
        # Create shared task
        task = Task.objects.create(
            user=self.user1,
            title='Shared Task',
            is_shared=True
        )
        shared_task = SharedTask.objects.create(
            task=task,
            creator=self.user1
        )
        TaskParticipation.objects.create(
            shared_task=shared_task,
            user=self.user2
        )
        
        # Switch to user2 (participant, not creator)
        self.client.force_authenticate(user=self.user2)
        
        data = {'participant_ids': [self.user3.id]}
        response = self.client.post(
            f'/api/tasks/shared-tasks/{shared_task.id}/invite_participants/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Only the task creator', response.data['error'])


class SharedTaskNotificationTest(TestCase):
    """
    Test cases for shared task notification functionality
    """
    
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
        
        self.task = Task.objects.create(
            user=self.user1,
            title='Test Shared Task',
            is_shared=True,
            points_value=20
        )
        
        self.shared_task = SharedTask.objects.create(
            task=self.task,
            creator=self.user1,
            is_competitive=True
        )
    
    def test_prepare_invitation_notification(self):
        """Test preparing invitation notification data"""
        from task_management.notifications import prepare_shared_task_invitation_notification
        
        invited_users = [self.user2]
        notifications = prepare_shared_task_invitation_notification(self.shared_task, invited_users)
        
        self.assertEqual(len(notifications), 1)
        notification = notifications[0]
        
        self.assertEqual(notification['user_id'], self.user2.id)
        self.assertEqual(notification['notification_type'], 'shared_task_invite')
        self.assertIn('invited you to join', notification['message'])
        self.assertEqual(notification['data']['shared_task_id'], self.shared_task.id)
        self.assertEqual(notification['data']['creator_phone'], self.user1.phone_number)
    
    def test_prepare_completion_notification(self):
        """Test preparing completion notification data"""
        from task_management.notifications import prepare_shared_task_completion_notification
        
        # Create participations
        participation1 = TaskParticipation.objects.create(
            shared_task=self.shared_task,
            user=self.user1
        )
        participation2 = TaskParticipation.objects.create(
            shared_task=self.shared_task,
            user=self.user2
        )
        
        # Complete user1's participation
        participation1.mark_completed()
        
        notifications = prepare_shared_task_completion_notification(participation1)
        
        self.assertEqual(len(notifications), 1)  # Only user2 should be notified
        notification = notifications[0]
        
        self.assertEqual(notification['user_id'], self.user2.id)
        self.assertEqual(notification['notification_type'], 'shared_task_completed')
        self.assertIn('completed', notification['message'])
        self.assertEqual(notification['data']['completed_by_phone'], self.user1.phone_number)
    
    def test_prepare_reminder_notification(self):
        """Test preparing deadline reminder notification data"""
        from task_management.notifications import prepare_shared_task_reminder_notification
        from django.utils import timezone
        
        # Set deadline
        self.task.deadline = timezone.now() + timezone.timedelta(hours=6)
        self.task.save()
        
        # Create participations
        TaskParticipation.objects.create(
            shared_task=self.shared_task,
            user=self.user1
        )
        TaskParticipation.objects.create(
            shared_task=self.shared_task,
            user=self.user2
        )
        
        notifications = prepare_shared_task_reminder_notification(self.shared_task, 6)
        
        self.assertEqual(len(notifications), 2)  # Both users should be reminded
        
        for notification in notifications:
            self.assertEqual(notification['notification_type'], 'shared_task_reminder')
            self.assertIn('due in 6 hours', notification['message'])
            self.assertEqual(notification['data']['hours_until_deadline'], 6)


class CompetitiveFeatureTest(APITestCase):
    """
    Test cases for competitive features and leaderboards
    """
    
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
        
        self.client.force_authenticate(user=self.user1)
    
    def test_competitive_stats_endpoint(self):
        """Test competitive statistics endpoint"""
        # Create competitive shared tasks
        task1 = Task.objects.create(
            user=self.user1,
            title='Competitive Task 1',
            is_shared=True,
            points_value=20
        )
        shared_task1 = SharedTask.objects.create(
            task=task1,
            creator=self.user1,
            is_competitive=True
        )
        
        # Create participations
        participation1 = TaskParticipation.objects.create(
            shared_task=shared_task1,
            user=self.user1
        )
        participation2 = TaskParticipation.objects.create(
            shared_task=shared_task1,
            user=self.user2
        )
        
        # Complete tasks (user1 wins)
        participation1.mark_completed()
        participation2.mark_completed()
        
        response = self.client.get('/api/tasks/shared-tasks/competitive_stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        stats = response.data
        self.assertEqual(stats['total_competitive_tasks'], 1)
        self.assertEqual(stats['completed_competitive_tasks'], 1)
        self.assertEqual(stats['rank_distribution']['first_place'], 1)
        self.assertGreater(stats['points_statistics']['total_points'], 0)
        self.assertGreater(stats['performance_metrics']['win_rate'], 0)
    
    def test_global_leaderboard_endpoint(self):
        """Test global leaderboard endpoint"""
        # Create multiple competitive tasks
        for i in range(3):
            task = Task.objects.create(
                user=self.user1,
                title=f'Competitive Task {i+1}',
                is_shared=True,
                points_value=20
            )
            shared_task = SharedTask.objects.create(
                task=task,
                creator=self.user1,
                is_competitive=True
            )
            
            # Add participants
            participation1 = TaskParticipation.objects.create(
                shared_task=shared_task,
                user=self.user1
            )
            participation2 = TaskParticipation.objects.create(
                shared_task=shared_task,
                user=self.user2
            )
            
            # Complete tasks
            participation1.mark_completed()
            participation2.mark_completed()
        
        response = self.client.get('/api/tasks/shared-tasks/global_leaderboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        leaderboard = response.data
        self.assertEqual(leaderboard['period'], 'all_time')
        self.assertGreater(len(leaderboard['leaderboard']), 0)
        self.assertGreater(leaderboard['total_participants'], 0)
        
        # Check leaderboard structure
        top_user = leaderboard['leaderboard'][0]
        self.assertIn('rank', top_user)
        self.assertIn('user', top_user)
        self.assertIn('total_points', top_user)
        self.assertIn('win_rate', top_user)
    
    def test_achievements_endpoint(self):
        """Test achievements endpoint"""
        response = self.client.get('/api/tasks/shared-tasks/achievements/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        achievements = response.data
        self.assertIn('unlocked_achievements', achievements)
        self.assertIn('all_achievements', achievements)
        self.assertIn('completion_percentage', achievements)
        
        # Should have some achievements available
        self.assertGreater(len(achievements['all_achievements']), 0)
    
    def test_completion_analytics_endpoint(self):
        """Test completion analytics endpoint"""
        # Create shared task
        task = Task.objects.create(
            user=self.user1,
            title='Analytics Task',
            is_shared=True,
            points_value=30
        )
        shared_task = SharedTask.objects.create(
            task=task,
            creator=self.user1,
            is_competitive=True
        )
        
        # Add participants
        participation1 = TaskParticipation.objects.create(
            shared_task=shared_task,
            user=self.user1
        )
        participation2 = TaskParticipation.objects.create(
            shared_task=shared_task,
            user=self.user2
        )
        participation3 = TaskParticipation.objects.create(
            shared_task=shared_task,
            user=self.user3
        )
        
        # Complete some tasks
        participation1.mark_completed()
        participation2.mark_completed()
        # participation3 remains incomplete
        
        response = self.client.get(
            f'/api/tasks/shared-tasks/{shared_task.id}/completion_analytics/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        analytics = response.data
        self.assertEqual(analytics['shared_task_id'], shared_task.id)
        self.assertEqual(len(analytics['completion_timeline']), 2)  # 2 completed
        
        stats = analytics['statistics']
        self.assertEqual(stats['total_participants'], 3)
        self.assertEqual(stats['completed_count'], 2)
        self.assertAlmostEqual(stats['completion_rate'], 66.67, places=1)
        
        # Check timeline structure
        timeline_entry = analytics['completion_timeline'][0]
        self.assertIn('user_id', timeline_entry)
        self.assertIn('points_earned', timeline_entry)
        self.assertIn('completion_rank', timeline_entry)
        self.assertIn('time_to_complete', timeline_entry)


class LeaderboardSystemTest(APITestCase):
    """
    Test cases for the leaderboard system
    """
    
    def setUp(self):
        self.user1 = User.objects.create_user(
            phone_number='+1234567890',
            username='testuser1',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            phone_number='+1234567891',
            username='testuser2',
            password='testpass123'
        )
        self.user3 = User.objects.create_user(
            phone_number='+1234567892',
            username='testuser3',
            password='testpass123'
        )
        
        # Create friendships
        from friendships.models import Friendship
        Friendship.objects.create(requester=self.user1, addressee=self.user2, status='accepted')
        Friendship.objects.create(requester=self.user1, addressee=self.user3, status='accepted')
        
        # Authenticate as user1
        self.client.force_authenticate(user=self.user1)
        
        # Create some competitive tasks and participations
        self.create_test_data()
    
    def create_test_data(self):
        """Create test data for leaderboard tests"""
        # Create competitive shared tasks
        for i in range(3):
            task = Task.objects.create(
                user=self.user1,
                title=f'Test Task {i+1}',
                description=f'Test task {i+1} description',
                priority='high',
                points_value=20,
                is_shared=True
            )
            
            shared_task = SharedTask.objects.create(
                task=task,
                creator=self.user1,
                is_competitive=True
            )
            
            # Add participations
            for j, user in enumerate([self.user1, self.user2, self.user3]):
                participation = TaskParticipation.objects.create(
                    shared_task=shared_task,
                    user=user
                )
                
                # Complete tasks with different completion times and ranks
                participation.status = 'completed'
                participation.completed_at = timezone.now() - timezone.timedelta(hours=j)
                participation.points_earned = 20 - (j * 5)  # Different points based on rank
                participation.save()
    
    def test_global_leaderboard_endpoint(self):
        """Test global leaderboard endpoint"""
        response = self.client.get('/api/tasks/shared-tasks/global_leaderboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertIn('leaderboard', data)
        self.assertIn('period', data)
        self.assertIn('category', data)
        self.assertIn('total_participants', data)
        
        # Check leaderboard structure
        if data['leaderboard']:
            entry = data['leaderboard'][0]
            self.assertIn('rank', entry)
            self.assertIn('user', entry)
            self.assertIn('total_points', entry)
            self.assertIn('total_tasks', entry)
    
    def test_friends_leaderboard_endpoint(self):
        """Test friends-only leaderboard endpoint"""
        response = self.client.get('/api/tasks/shared-tasks/friends_leaderboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertIn('leaderboard', data)
        
        # Should only include friends and the user
        user_ids_in_leaderboard = {entry['user']['id'] for entry in data['leaderboard']}
        expected_user_ids = {self.user1.id, self.user2.id, self.user3.id}
        self.assertTrue(user_ids_in_leaderboard.issubset(expected_user_ids))
    
    def test_leaderboard_categories(self):
        """Test different leaderboard categories"""
        categories = ['competitive_points', 'task_completion', 'win_rate']
        
        for category in categories:
            response = self.client.get(
                f'/api/tasks/shared-tasks/global_leaderboard/?category={category}'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data['category'], category)
    
    def test_leaderboard_time_periods(self):
        """Test different time periods"""
        periods = ['daily', 'weekly', 'monthly', 'all_time']
        
        for period in periods:
            response = self.client.get(
                f'/api/tasks/shared-tasks/global_leaderboard/?period={period}'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data['period'], period)
    
    def test_leaderboard_summary_endpoint(self):
        """Test leaderboard summary endpoint"""
        response = self.client.get('/api/tasks/shared-tasks/leaderboard_summary/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertIn('global_rankings', data)
        self.assertIn('friends_rankings', data)
        self.assertIn('achievements_ranking', data)
        self.assertIn('recent_performance', data)
    
    def test_my_ranking_endpoint(self):
        """Test user's personal ranking endpoint"""
        response = self.client.get('/api/tasks/shared-tasks/my_ranking/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertIn('user_rank', data)
        self.assertIn('total_participants', data)
        self.assertIn('period', data)
        self.assertIn('category', data)
    
    def test_leaderboard_options_endpoint(self):
        """Test leaderboard configuration options endpoint"""
        response = self.client.get('/api/tasks/shared-tasks/leaderboard_options/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertIn('periods', data)
        self.assertIn('categories', data)
        
        # Check that we have expected periods and categories
        period_keys = {period['key'] for period in data['periods']}
        self.assertIn('weekly', period_keys)
        self.assertIn('monthly', period_keys)
        self.assertIn('all_time', period_keys)
        
        category_keys = {category['key'] for category in data['categories']}
        self.assertIn('competitive_points', category_keys)
        self.assertIn('win_rate', category_keys)


class AchievementSystemTest(TestCase):
    """
    Test cases for the achievement system
    """
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            phone_number='+1234567890',
            username='testuser',
            password='testpass123'
        )
    
    def test_first_win_achievement(self):
        """Test first win achievement"""
        from task_management.achievements import FirstWinAchievement
        
        achievement = FirstWinAchievement()
        
        # Initially not unlocked
        self.assertFalse(achievement.check_unlocked(self.user))
        
        # Create competitive task and win it
        task = Task.objects.create(
            user=self.user,
            title='Win Task',
            is_shared=True,
            points_value=20
        )
        shared_task = SharedTask.objects.create(
            task=task,
            creator=self.user,
            is_competitive=True
        )
        participation = TaskParticipation.objects.create(
            shared_task=shared_task,
            user=self.user
        )
        participation.mark_completed()
        
        # Should be unlocked now
        self.assertTrue(achievement.check_unlocked(self.user))
    
    def test_win_streak_achievement(self):
        """Test win streak achievement"""
        from task_management.achievements import WinStreakAchievement
        
        achievement = WinStreakAchievement(3)
        
        # Create 3 competitive tasks and win them all
        for i in range(3):
            task = Task.objects.create(
                user=self.user,
                title=f'Streak Task {i+1}',
                is_shared=True,
                points_value=20
            )
            shared_task = SharedTask.objects.create(
                task=task,
                creator=self.user,
                is_competitive=True
            )
            participation = TaskParticipation.objects.create(
                shared_task=shared_task,
                user=self.user
            )
            participation.mark_completed()
        
        # Should unlock 3-win streak
        self.assertTrue(achievement.check_unlocked(self.user))
    
    def test_point_master_achievement(self):
        """Test point master achievement"""
        from task_management.achievements import PointMasterAchievement
        
        achievement = PointMasterAchievement(1000)
        
        # Initially not unlocked
        self.assertFalse(achievement.check_unlocked(self.user))
        
        # Create tasks worth enough points
        for i in range(25):  # 25 tasks * 40 points (first place bonus) = 1000 points
            task = Task.objects.create(
                user=self.user,
                title=f'Point Task {i+1}',
                is_shared=True,
                points_value=20
            )
            shared_task = SharedTask.objects.create(
                task=task,
                creator=self.user,
                is_competitive=True
            )
            participation = TaskParticipation.objects.create(
                shared_task=shared_task,
                user=self.user
            )
            participation.mark_completed()  # Gets 40 points for first place
        
        # Should be unlocked now
        self.assertTrue(achievement.check_unlocked(self.user))
    
    def test_check_user_achievements(self):
        """Test checking all user achievements"""
        from task_management.achievements import check_user_achievements
        
        # Create a winning task
        task = Task.objects.create(
            user=self.user,
            title='Achievement Task',
            is_shared=True,
            points_value=20
        )
        shared_task = SharedTask.objects.create(
            task=task,
            creator=self.user,
            is_competitive=True
        )
        participation = TaskParticipation.objects.create(
            shared_task=shared_task,
            user=self.user
        )
        participation.mark_completed()
        
        achievements = check_user_achievements(self.user)
        
        # Should have at least the first win achievement
        achievement_ids = [ach['id'] for ach in achievements]
        self.assertIn('first_win', achievement_ids)
