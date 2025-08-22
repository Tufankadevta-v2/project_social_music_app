# Design Document

## Overview

The social task management application will be built using Django REST Framework for the backend API and React Native for cross-platform mobile frontend. The architecture follows a microservices-inspired approach within Django using separate apps for different domains. The system emphasizes real-time features, privacy controls, and social gamification.

## Architecture

### Backend Architecture (Django)
- **Django REST Framework**: RESTful API endpoints with token-based authentication
- **Django Channels**: WebSocket support for real-time notifications and updates
- **Celery**: Asynchronous task processing for notifications, OTP sending, and background jobs
- **Redis**: Caching layer and message broker for Celery and Channels
- **PostgreSQL**: Primary database for relational data storage
- **Django Apps Structure**:
  - `accounts`: User authentication, phone verification, profile management
  - `friends`: Friend connections, contact syncing, privacy controls
  - `tasks`: Task management, shared tasks, completion tracking
  - `social`: Activity feeds, achievements, leaderboards, interactions
  - `notifications`: Push notifications, in-app notifications, real-time updates

### Frontend Architecture
- **React Native**: Cross-platform mobile app (iOS/Android)
- **Redux Toolkit**: State management for app data and user sessions
- **React Navigation**: Tab-based navigation (Tasks/Friends tabs)
- **Socket.IO Client**: Real-time communication with backend
- **Expo Notifications**: Push notification handling

### External Services
- **Twilio/AWS SNS**: SMS OTP delivery service
- **Firebase Cloud Messaging**: Push notifications
- **Contact Sync API**: Secure contact matching without storing full contact lists

## Components and Interfaces

### Authentication System
```python
# Phone-based authentication with OTP
class PhoneAuthView(APIView):
    def post(self, request):
        # Send OTP to phone number
        # Return temporary token for verification
        
class OTPVerifyView(APIView):
    def post(self, request):
        # Verify OTP and create/login user
        # Return JWT tokens
```

### Contact-Based Friend Discovery
```python
class ContactSyncView(APIView):
    def post(self, request):
        # Hash phone numbers for privacy
        # Find mutual contacts without storing raw numbers
        # Return potential friends list
        
class FriendRequestView(APIView):
    def post(self, request):
        # Send friend request only to mutual contacts
        # Validate privacy constraints
```

### Task Management System
```python
class TaskViewSet(ModelViewSet):
    # CRUD operations for personal tasks
    # Task completion with point calculation
    
class SharedTaskViewSet(ModelViewSet):
    # Shared task creation and management
    # Multi-user completion tracking
    
class TaskCompletionView(APIView):
    def post(self, request):
        # Mark task complete
        # Calculate and award points
        # Trigger social feed updates
```

### Social Feed and Gamification
```python
class ActivityFeedView(ListAPIView):
    # Paginated friend activity feed
    # Privacy-filtered content
    
class LeaderboardView(APIView):
    def get(self, request):
        # Friend rankings by points
        # Time-period filtering (daily, weekly, monthly)
        
class AchievementView(APIView):
    # Achievement unlocking logic
    # Badge management
```

### Real-time Notifications
```python
# WebSocket consumers for real-time updates
class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Join user-specific notification group
        
    async def task_reminder(self, event):
        # Send task deadline reminders
        
    async def friend_activity(self, event):
        # Send friend completion notifications
```

## Data Models

### User and Authentication
```python
class User(AbstractUser):
    phone_number = models.CharField(unique=True)
    is_phone_verified = models.BooleanField(default=False)
    total_points = models.IntegerField(default=0)
    privacy_settings = models.JSONField(default=dict)
    
class PhoneVerification(models.Model):
    phone_number = models.CharField()
    otp_code = models.CharField()
    expires_at = models.DateTimeField()
    is_verified = models.BooleanField(default=False)
```

### Friend System
```python
class Friendship(models.Model):
    user1 = models.ForeignKey(User, related_name='friendships_initiated')
    user2 = models.ForeignKey(User, related_name='friendships_received')
    status = models.CharField(choices=[('pending', 'Pending'), ('accepted', 'Accepted')])
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user1', 'user2')

class ContactHash(models.Model):
    user = models.ForeignKey(User)
    phone_hash = models.CharField()  # Hashed phone numbers for privacy
    created_at = models.DateTimeField(auto_now_add=True)
```

### Task Management
```python
class Task(models.Model):
    PRIORITY_CHOICES = [('low', 'Low'), ('medium', 'Medium'), ('high', 'High')]
    STATUS_CHOICES = [('pending', 'Pending'), ('completed', 'Completed'), ('overdue', 'Overdue')]
    
    user = models.ForeignKey(User, related_name='tasks')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    priority = models.CharField(choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(choices=STATUS_CHOICES, default='pending')
    deadline = models.DateTimeField(null=True, blank=True)
    points_value = models.IntegerField(default=10)
    is_shared = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

class SharedTask(models.Model):
    task = models.OneToOneField(Task, related_name='shared_details')
    participants = models.ManyToManyField(User, through='TaskParticipation')
    creator = models.ForeignKey(User, related_name='created_shared_tasks')
    is_competitive = models.BooleanField(default=True)
    
class TaskParticipation(models.Model):
    shared_task = models.ForeignKey(SharedTask)
    user = models.ForeignKey(User)
    status = models.CharField(choices=Task.STATUS_CHOICES, default='pending')
    completed_at = models.DateTimeField(null=True, blank=True)
    points_earned = models.IntegerField(default=0)
```

### Social and Gamification
```python
class Achievement(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=50)  # Icon identifier
    points_required = models.IntegerField()
    
class UserAchievement(models.Model):
    user = models.ForeignKey(User)
    achievement = models.ForeignKey(Achievement)
    earned_at = models.DateTimeField(auto_now_add=True)
    
class ActivityFeed(models.Model):
    ACTIVITY_TYPES = [
        ('task_completed', 'Task Completed'),
        ('achievement_earned', 'Achievement Earned'),
        ('shared_task_completed', 'Shared Task Completed'),
        ('milestone_reached', 'Milestone Reached')
    ]
    
    user = models.ForeignKey(User, related_name='activities')
    activity_type = models.CharField(choices=ACTIVITY_TYPES)
    content = models.JSONField()  # Flexible content storage
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class ActivityInteraction(models.Model):
    INTERACTION_TYPES = [('like', 'Like'), ('comment', 'Comment'), ('cheer', 'Cheer')]
    
    activity = models.ForeignKey(ActivityFeed, related_name='interactions')
    user = models.ForeignKey(User)
    interaction_type = models.CharField(choices=INTERACTION_TYPES)
    comment_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### Notifications
```python
class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('task_reminder', 'Task Reminder'),
        ('friend_request', 'Friend Request'),
        ('task_completed', 'Task Completed'),
        ('achievement_earned', 'Achievement Earned'),
        ('shared_task_invite', 'Shared Task Invite')
    ]
    
    user = models.ForeignKey(User, related_name='notifications')
    notification_type = models.CharField(choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    data = models.JSONField(default=dict)  # Additional notification data
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
```

## Error Handling

### API Error Responses
```python
# Standardized error response format
{
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Invalid input data",
        "details": {
            "phone_number": ["This field is required"]
        }
    }
}

# Custom exception handling
class APIException(Exception):
    def __init__(self, message, code, status_code=400):
        self.message = message
        self.code = code
        self.status_code = status_code
```

### Privacy and Security Errors
- Contact sync failures with graceful degradation
- Friend request validation with clear error messages
- Task sharing permission errors
- Rate limiting for OTP requests

## Testing Strategy

### Unit Testing
- Model validation and business logic testing
- API endpoint testing with Django REST Framework test client
- Authentication and permission testing
- Point calculation and achievement logic testing

### Integration Testing
- End-to-end API workflow testing
- WebSocket connection and real-time notification testing
- Contact sync and friend discovery testing
- Shared task collaboration testing

### Performance Testing
- Database query optimization testing
- API response time benchmarking
- Real-time notification load testing
- Contact sync scalability testing

### Security Testing
- Authentication and authorization testing
- Privacy control validation
- Input sanitization and validation testing
- Rate limiting and abuse prevention testing