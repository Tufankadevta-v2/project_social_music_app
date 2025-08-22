"""
Models for the notifications system.
"""
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Notification(models.Model):
    """
    Model for storing notification data.
    """
    NOTIFICATION_TYPES = [
        ('task_reminder', 'Task Reminder'),
        ('friend_request', 'Friend Request'),
        ('task_completed', 'Task Completed'),
        ('achievement_earned', 'Achievement Earned'),
        ('shared_task_invite', 'Shared Task Invite'),
        ('friend_activity', 'Friend Activity'),
        ('general', 'General Notification'),
    ]
    
    user = models.ForeignKey(User, related_name='notifications', on_delete=models.CASCADE)
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    data = models.JSONField(default=dict, blank=True)  # Additional notification data
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'is_read']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"
    
    def mark_as_read(self):
        """Mark notification as read."""
        self.is_read = True
        self.save(update_fields=['is_read'])