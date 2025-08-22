from rest_framework import serializers
from django.contrib.auth import get_user_model
from .privacy_models import PrivacySettings, FriendPrivacySettings, PrivateTask

User = get_user_model()


class PrivacySettingsSerializer(serializers.ModelSerializer):
    """
    Serializer for user privacy settings
    """
    class Meta:
        model = PrivacySettings
        fields = [
            'profile_visibility',
            'task_visibility',
            'task_completion_visibility',
            'achievement_visibility',
            'activity_feed_visibility',
            'show_in_leaderboards',
            'allow_friend_requests',
            'allow_shared_task_invites',
            'share_location',
            'allow_contact_sync',
            'show_online_status',
            'show_last_seen',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def validate(self, data):
        """Validate privacy settings data"""
        # Ensure that if profile is private, other settings are also restrictive
        if data.get('profile_visibility') == 'private':
            if data.get('task_visibility') == 'public':
                raise serializers.ValidationError(
                    "Task visibility cannot be public when profile is private"
                )
            if data.get('achievement_visibility') == 'public':
                raise serializers.ValidationError(
                    "Achievement visibility cannot be public when profile is private"
                )
        
        return data


class FriendPrivacySettingsSerializer(serializers.ModelSerializer):
    """
    Serializer for friend-specific privacy settings
    """
    friend_phone_number = serializers.CharField(source='friend.phone_number', read_only=True)
    friend_display_name = serializers.SerializerMethodField()
    
    class Meta:
        model = FriendPrivacySettings
        fields = [
            'id',
            'friend',
            'friend_phone_number',
            'friend_display_name',
            'visibility_level',
            'can_see_tasks',
            'can_see_task_completions',
            'can_see_achievements',
            'can_invite_to_shared_tasks',
            'can_see_activity_feed',
            'can_see_leaderboard_position',
            'notify_on_activities',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_friend_display_name(self, obj):
        """Get friend's display name"""
        if hasattr(obj.friend, 'profile'):
            return obj.friend.profile.get_display_name()
        return obj.friend.username
    
    def validate_friend(self, value):
        """Validate that friend is different from user"""
        request = self.context.get('request')
        if request and request.user == value:
            raise serializers.ValidationError("Cannot set privacy settings for yourself")
        return value
    
    def update(self, instance, validated_data):
        """Update friend privacy settings and apply visibility level if changed"""
        visibility_level = validated_data.get('visibility_level')
        
        # If visibility level changed, apply preset permissions
        if visibility_level and visibility_level != instance.visibility_level:
            instance.visibility_level = visibility_level
            instance.apply_visibility_level()
            instance.save()
            
            # Update other fields if provided
            for attr, value in validated_data.items():
                if attr != 'visibility_level':
                    setattr(instance, attr, value)
            instance.save()
        else:
            # Normal update
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
        
        return instance


class PrivateTaskSerializer(serializers.ModelSerializer):
    """
    Serializer for private task settings
    """
    task_title = serializers.CharField(source='task.title', read_only=True)
    visible_to_friends_details = serializers.SerializerMethodField()
    
    class Meta:
        model = PrivateTask
        fields = [
            'id',
            'task',
            'task_title',
            'is_completely_private',
            'visible_to_friends',
            'visible_to_friends_details',
            'hide_from_activity_feed',
            'hide_from_leaderboards',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_visible_to_friends_details(self, obj):
        """Get details of friends who can see this private task"""
        friends = obj.visible_to_friends.all()
        return [
            {
                'id': friend.id,
                'phone_number': friend.phone_number,
                'display_name': friend.profile.get_display_name() if hasattr(friend, 'profile') else friend.username
            }
            for friend in friends
        ]
    
    def validate_task(self, value):
        """Validate that task belongs to the requesting user"""
        request = self.context.get('request')
        if request and value.user != request.user:
            raise serializers.ValidationError("You can only set privacy settings for your own tasks")
        return value
    
    def validate_visible_to_friends(self, value):
        """Validate that visible friends are actually friends of the user"""
        request = self.context.get('request')
        if request:
            from friendships.models import Friendship
            user_friends = set(Friendship.get_friends(request.user).values_list('id', flat=True))
            
            for friend in value:
                if friend.id not in user_friends:
                    raise serializers.ValidationError(
                        f"User {friend.phone_number} is not in your friends list"
                    )
        
        return value


class PrivacySettingsUpdateSerializer(serializers.Serializer):
    """
    Serializer for bulk privacy settings updates
    """
    privacy_settings = PrivacySettingsSerializer()
    friend_settings = serializers.ListField(
        child=FriendPrivacySettingsSerializer(),
        required=False,
        allow_empty=True
    )
    private_tasks = serializers.ListField(
        child=PrivateTaskSerializer(),
        required=False,
        allow_empty=True
    )
    
    def update(self, instance, validated_data):
        """Update all privacy settings in a single transaction"""
        from django.db import transaction
        
        with transaction.atomic():
            # Update main privacy settings
            privacy_data = validated_data.get('privacy_settings', {})
            if privacy_data:
                privacy_settings = PrivacySettings.get_or_create_for_user(instance)
                for attr, value in privacy_data.items():
                    setattr(privacy_settings, attr, value)
                privacy_settings.save()
            
            # Update friend settings
            friend_settings_data = validated_data.get('friend_settings', [])
            for friend_setting_data in friend_settings_data:
                friend_id = friend_setting_data.get('friend')
                if friend_id:
                    friend_settings, created = FriendPrivacySettings.objects.get_or_create(
                        user=instance,
                        friend_id=friend_id,
                        defaults=friend_setting_data
                    )
                    if not created:
                        for attr, value in friend_setting_data.items():
                            if attr != 'friend':
                                setattr(friend_settings, attr, value)
                        friend_settings.save()
            
            # Update private task settings
            private_tasks_data = validated_data.get('private_tasks', [])
            for private_task_data in private_tasks_data:
                task_id = private_task_data.get('task')
                if task_id:
                    private_task, created = PrivateTask.objects.get_or_create(
                        task_id=task_id,
                        defaults=private_task_data
                    )
                    if not created:
                        for attr, value in private_task_data.items():
                            if attr != 'task':
                                setattr(private_task, attr, value)
                        private_task.save()
        
        return instance


class PrivacyCheckSerializer(serializers.Serializer):
    """
    Serializer for checking privacy permissions
    """
    target_user_id = serializers.IntegerField()
    permission_type = serializers.ChoiceField(choices=[
        'profile', 'tasks', 'task_completions', 'achievements', 'activity_feed'
    ])
    
    def validate_target_user_id(self, value):
        """Validate that target user exists"""
        try:
            User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Target user does not exist")
        return value