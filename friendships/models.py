from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
import hashlib
import hmac
from django.conf import settings

User = get_user_model()


class ContactHash(models.Model):
    """
    Model for storing hashed phone numbers to enable privacy-preserving contact matching.
    Phone numbers are hashed using HMAC-SHA256 with a secret key to prevent rainbow table attacks.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='contact_hashes',
        help_text="User who uploaded this contact"
    )
    
    phone_hash = models.CharField(
        max_length=64,  # SHA256 hash length
        db_index=True,
        help_text="HMAC-SHA256 hash of the phone number"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'friendships_contact_hash'
        verbose_name = 'Contact Hash'
        verbose_name_plural = 'Contact Hashes'
        unique_together = ('user', 'phone_hash')
        indexes = [
            models.Index(fields=['phone_hash']),
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        return f"Contact hash for {self.user.phone_number}: {self.phone_hash[:8]}..."
    
    @staticmethod
    def hash_phone_number(phone_number):
        """
        Create a privacy-preserving hash of a phone number using HMAC-SHA256.
        
        Args:
            phone_number (str): Phone number to hash
            
        Returns:
            str: HMAC-SHA256 hash of the phone number
        """
        # Normalize phone number (remove spaces, ensure + prefix)
        normalized_phone = phone_number.strip().replace(' ', '').replace('-', '')
        if not normalized_phone.startswith('+'):
            # Assume US number if no country code
            if len(normalized_phone) == 10:
                normalized_phone = '+1' + normalized_phone
            elif len(normalized_phone) == 11 and normalized_phone.startswith('1'):
                normalized_phone = '+' + normalized_phone
        
        # Use Django's SECRET_KEY as HMAC key for consistency
        secret_key = getattr(settings, 'SECRET_KEY', 'default-secret-key').encode('utf-8')
        
        # Create HMAC-SHA256 hash
        return hmac.new(
            secret_key,
            normalized_phone.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    @classmethod
    def create_contact_hash(cls, user, phone_number):
        """
        Create a contact hash for a user and phone number.
        
        Args:
            user: User instance
            phone_number (str): Phone number to hash
            
        Returns:
            ContactHash: Created contact hash instance
        """
        phone_hash = cls.hash_phone_number(phone_number)
        contact_hash, created = cls.objects.get_or_create(
            user=user,
            phone_hash=phone_hash
        )
        return contact_hash
    
    @classmethod
    def find_mutual_contacts(cls, user, phone_numbers):
        """
        Find mutual contacts between a user and a list of phone numbers.
        Returns users who have both uploaded each other's phone numbers.
        
        Args:
            user: User instance
            phone_numbers (list): List of phone numbers to check
            
        Returns:
            QuerySet: Users who are mutual contacts
        """
        if not phone_numbers:
            return User.objects.none()
        
        # Hash all provided phone numbers
        phone_hashes = [cls.hash_phone_number(phone) for phone in phone_numbers]
        
        # Find users who have uploaded the current user's phone number
        user_phone_hash = cls.hash_phone_number(user.phone_number)
        users_with_my_number = cls.objects.filter(
            phone_hash=user_phone_hash
        ).values_list('user_id', flat=True)
        
        # Find users whose phone numbers match the provided hashes
        # and who also have the current user's phone number
        users_in_my_contacts = User.objects.filter(
            phone_number__in=phone_numbers
        ).values_list('id', flat=True)
        
        # Get users who are both in my contacts and have my number
        mutual_user_ids = set(users_with_my_number) & set(users_in_my_contacts)
        
        # Return the actual user objects, excluding the current user
        return User.objects.filter(id__in=mutual_user_ids).exclude(id=user.id)


class Friendship(models.Model):
    """
    Model representing friendship relationships between users.
    Supports friend requests, acceptance, and blocking functionality.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('blocked', 'Blocked'),
        ('declined', 'Declined'),
    ]
    
    requester = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_friend_requests',
        help_text="User who sent the friend request"
    )
    
    addressee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='received_friend_requests',
        help_text="User who received the friend request"
    )
    
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending',
        help_text="Current status of the friendship"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'friendships_friendship'
        verbose_name = 'Friendship'
        verbose_name_plural = 'Friendships'
        unique_together = ('requester', 'addressee')
        indexes = [
            models.Index(fields=['requester', 'status']),
            models.Index(fields=['addressee', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.requester.phone_number} -> {self.addressee.phone_number} ({self.status})"
    
    def clean(self):
        """Validate that users cannot send friend requests to themselves"""
        if self.requester == self.addressee:
            raise ValidationError("Users cannot send friend requests to themselves")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    @classmethod
    def are_friends(cls, user1, user2):
        """
        Check if two users are friends (have accepted friendship).
        
        Args:
            user1: First user
            user2: Second user
            
        Returns:
            bool: True if users are friends, False otherwise
        """
        return cls.objects.filter(
            models.Q(requester=user1, addressee=user2, status='accepted') |
            models.Q(requester=user2, addressee=user1, status='accepted')
        ).exists()
    
    @classmethod
    def get_friendship(cls, user1, user2):
        """
        Get the friendship relationship between two users.
        
        Args:
            user1: First user
            user2: Second user
            
        Returns:
            Friendship or None: Friendship instance if exists, None otherwise
        """
        try:
            return cls.objects.get(
                models.Q(requester=user1, addressee=user2) |
                models.Q(requester=user2, addressee=user1)
            )
        except cls.DoesNotExist:
            return None
    
    @classmethod
    def send_friend_request(cls, requester, addressee):
        """
        Send a friend request between two users.
        
        Args:
            requester: User sending the request
            addressee: User receiving the request
            
        Returns:
            tuple: (Friendship instance, created boolean)
        """
        # Check if friendship already exists
        existing_friendship = cls.get_friendship(requester, addressee)
        if existing_friendship:
            if existing_friendship.status == 'blocked':
                raise ValidationError("Cannot send friend request to blocked user")
            elif existing_friendship.status == 'accepted':
                raise ValidationError("Users are already friends")
            elif existing_friendship.status == 'pending':
                raise ValidationError("Friend request already pending")
        
        # Create new friend request
        friendship, created = cls.objects.get_or_create(
            requester=requester,
            addressee=addressee,
            defaults={'status': 'pending'}
        )
        
        return friendship, created
    
    def accept(self):
        """Accept a pending friend request"""
        if self.status != 'pending':
            raise ValidationError("Can only accept pending friend requests")
        
        self.status = 'accepted'
        self.save(update_fields=['status', 'updated_at'])
    
    def decline(self):
        """Decline a pending friend request"""
        if self.status != 'pending':
            raise ValidationError("Can only decline pending friend requests")
        
        self.status = 'declined'
        self.save(update_fields=['status', 'updated_at'])
    
    def block(self):
        """Block the other user"""
        self.status = 'blocked'
        self.save(update_fields=['status', 'updated_at'])
    
    def unblock(self):
        """Unblock the other user (removes the friendship)"""
        if self.status != 'blocked':
            raise ValidationError("Can only unblock blocked users")
        
        self.delete()
    
    @classmethod
    def get_friends(cls, user):
        """
        Get all friends of a user (accepted friendships).
        
        Args:
            user: User instance
            
        Returns:
            QuerySet: Users who are friends with the given user
        """
        friend_ids = cls.get_friend_ids(user)
        return User.objects.filter(id__in=friend_ids)
    
    @classmethod
    def get_friend_ids(cls, user):
        """
        Get all friend IDs of a user (accepted friendships).
        
        Args:
            user: User instance
            
        Returns:
            list: List of user IDs who are friends with the given user
        """
        friend_ids = cls.objects.filter(
            models.Q(requester=user, status='accepted') |
            models.Q(addressee=user, status='accepted')
        ).values_list(
            models.Case(
                models.When(requester=user, then='addressee'),
                default='requester'
            ),
            flat=True
        )
        
        return list(friend_ids)
    
    @classmethod
    def get_pending_requests(cls, user):
        """
        Get all pending friend requests for a user.
        
        Args:
            user: User instance
            
        Returns:
            QuerySet: Pending friendship requests where user is addressee
        """
        return cls.objects.filter(
            addressee=user,
            status='pending'
        ).select_related('requester')
    
    @classmethod
    def get_sent_requests(cls, user):
        """
        Get all sent friend requests by a user.
        
        Args:
            user: User instance
            
        Returns:
            QuerySet: Friendship requests sent by the user
        """
        return cls.objects.filter(
            requester=user,
            status='pending'
        ).select_related('addressee')