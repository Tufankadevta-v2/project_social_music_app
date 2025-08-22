"""
Serializers for friendship and contact syncing API endpoints.
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class ContactSyncSerializer(serializers.Serializer):
    """
    Serializer for contact synchronization endpoint.
    """
    phone_numbers = serializers.ListField(
        child=serializers.CharField(max_length=20),
        min_length=1,
        max_length=1000,  # Limit to prevent abuse
        help_text="List of phone numbers to sync"
    )
    
    def validate_phone_numbers(self, value):
        """
        Validate that phone numbers are provided and not empty.
        """
        if not value:
            raise serializers.ValidationError("At least one phone number is required")
        
        # Remove empty strings
        cleaned_numbers = [phone.strip() for phone in value if phone.strip()]
        
        if not cleaned_numbers:
            raise serializers.ValidationError("At least one valid phone number is required")
        
        return cleaned_numbers


class FriendRequestSerializer(serializers.Serializer):
    """
    Serializer for sending friend requests.
    """
    addressee_id = serializers.IntegerField(
        min_value=1,
        help_text="ID of the user to send friend request to"
    )
    
    def validate_addressee_id(self, value):
        """
        Validate that the addressee exists and is not the requester.
        """
        request = self.context.get('request')
        
        if request and request.user.id == value:
            raise serializers.ValidationError("Cannot send friend request to yourself")
        
        try:
            User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User does not exist")
        
        return value


class FriendshipResponseSerializer(serializers.Serializer):
    """
    Serializer for responding to friend requests.
    """
    ACTION_CHOICES = [
        ('accept', 'Accept'),
        ('decline', 'Decline'),
    ]
    
    action = serializers.ChoiceField(
        choices=ACTION_CHOICES,
        help_text="Action to take on the friend request"
    )


class BlockUserSerializer(serializers.Serializer):
    """
    Serializer for blocking/unblocking users.
    """
    user_id = serializers.IntegerField(
        min_value=1,
        help_text="ID of the user to block/unblock"
    )
    
    def validate_user_id(self, value):
        """
        Validate that the user exists and is not the current user.
        """
        request = self.context.get('request')
        
        if request and request.user.id == value:
            raise serializers.ValidationError("Cannot block/unblock yourself")
        
        try:
            User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User does not exist")
        
        return value


class UserBasicSerializer(serializers.ModelSerializer):
    """
    Basic user serializer for friend-related responses.
    """
    display_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'phone_number', 'username', 'display_name']
    
    def get_display_name(self, obj):
        """Get display name from user profile if available."""
        if hasattr(obj, 'profile') and obj.profile.display_name:
            return obj.profile.display_name
        return obj.username or f"User {obj.phone_number}"


class MutualContactSerializer(serializers.Serializer):
    """
    Serializer for mutual contact information.
    """
    id = serializers.IntegerField()
    phone_number = serializers.CharField()
    username = serializers.CharField()
    display_name = serializers.CharField()
    is_friend = serializers.BooleanField()
    friendship_status = serializers.CharField()


class FriendSerializer(serializers.Serializer):
    """
    Serializer for friend information.
    """
    id = serializers.IntegerField()
    phone_number = serializers.CharField()
    username = serializers.CharField()
    display_name = serializers.CharField()
    total_points = serializers.IntegerField()


class PendingRequestSerializer(serializers.Serializer):
    """
    Serializer for pending friend request information.
    """
    id = serializers.IntegerField()
    requester = UserBasicSerializer()
    created_at = serializers.CharField()


class FriendshipSerializer(serializers.Serializer):
    """
    Serializer for friendship relationship information.
    """
    id = serializers.IntegerField()
    requester_id = serializers.IntegerField()
    addressee_id = serializers.IntegerField()
    status = serializers.CharField()
    created_at = serializers.CharField()
    updated_at = serializers.CharField(required=False)