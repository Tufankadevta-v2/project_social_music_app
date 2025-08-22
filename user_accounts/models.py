from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from .managers import UserManager
import uuid
import random
import string


class User(AbstractUser):
    """
    Custom User model extending AbstractUser with phone number authentication
    """
    phone_number = models.CharField(
        max_length=15,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
            )
        ],
        help_text="Phone number in international format"
    )
    
    is_phone_verified = models.BooleanField(
        default=False,
        help_text="Whether the phone number has been verified"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Make email optional since we're using phone-based auth
    email = models.EmailField(blank=True, null=True)
    
    # Use phone number as the unique identifier for authentication
    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['username']
    
    # Use custom manager
    objects = UserManager()
    
    class Meta:
        db_table = 'user_accounts_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return f"{self.phone_number} ({self.username})"
    
    def save(self, *args, **kwargs):
        # Generate username from phone number if not provided
        if not self.username:
            self.username = f"user_{self.phone_number.replace('+', '').replace(' ', '')}"
        super().save(*args, **kwargs)


class PhoneVerification(models.Model):
    """
    Model to handle OTP verification for phone numbers
    """
    phone_number = models.CharField(
        max_length=15,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
            )
        ]
    )
    
    otp_code = models.CharField(
        max_length=6,
        help_text="6-digit OTP code"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    is_used = models.BooleanField(
        default=False,
        help_text="Whether this OTP has been used for verification"
    )
    
    attempts = models.PositiveIntegerField(
        default=0,
        help_text="Number of verification attempts"
    )
    
    MAX_ATTEMPTS = 3
    OTP_EXPIRY_MINUTES = 10
    
    class Meta:
        db_table = 'user_accounts_phone_verification'
        verbose_name = 'Phone Verification'
        verbose_name_plural = 'Phone Verifications'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"OTP for {self.phone_number} - {self.otp_code}"
    
    def save(self, *args, **kwargs):
        if not self.otp_code:
            self.otp_code = self.generate_otp()
        
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(minutes=self.OTP_EXPIRY_MINUTES)
        
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_otp():
        """Generate a 6-digit OTP code"""
        return ''.join(random.choices(string.digits, k=6))
    
    def is_expired(self):
        """Check if the OTP has expired"""
        return timezone.now() > self.expires_at
    
    def is_valid(self):
        """Check if the OTP is valid (not expired, not used, attempts not exceeded)"""
        return (
            not self.is_expired() and 
            not self.is_used and 
            self.attempts < self.MAX_ATTEMPTS
        )
    
    def increment_attempts(self):
        """Increment the number of verification attempts"""
        self.attempts += 1
        self.save(update_fields=['attempts'])
    
    def mark_as_used(self):
        """Mark the OTP as used"""
        self.is_used = True
        self.save(update_fields=['is_used'])
    
    @classmethod
    def create_otp(cls, phone_number):
        """Create a new OTP for the given phone number"""
        # Invalidate any existing unused OTPs for this phone number
        cls.objects.filter(
            phone_number=phone_number,
            is_used=False
        ).update(is_used=True)
        
        # Create new OTP
        return cls.objects.create(phone_number=phone_number)
    
    @classmethod
    def verify_otp(cls, phone_number, otp_code):
        """
        Verify an OTP code for a phone number
        Returns (is_valid, verification_object)
        """
        # Check for super OTP in development (123456)
        from django.conf import settings
        if getattr(settings, 'DEBUG', True) and otp_code == "123456":
            # Create a temporary verification object for super OTP
            verification = cls(
                phone_number=phone_number,
                otp_code=otp_code,
                is_used=True
            )
            return True, verification
        
        try:
            verification = cls.objects.get(
                phone_number=phone_number,
                otp_code=otp_code,
                is_used=False
            )
            
            if verification.is_valid():
                verification.mark_as_used()
                return True, verification
            else:
                verification.increment_attempts()
                return False, verification
                
        except cls.DoesNotExist:
            return False, None


class UserProfile(models.Model):
    """
    Extended user profile information
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    
    display_name = models.CharField(
        max_length=50,
        blank=True,
        help_text="Display name for the user"
    )
    
    avatar = models.ImageField(
        upload_to='avatars/',
        blank=True,
        null=True,
        help_text="User avatar image"
    )
    
    bio = models.TextField(
        max_length=500,
        blank=True,
        help_text="User bio/description"
    )
    
    total_points = models.PositiveIntegerField(
        default=0,
        help_text="Total points earned by the user"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_accounts_user_profile'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
    
    def __str__(self):
        return f"Profile for {self.user.phone_number}"
    
    def get_display_name(self):
        """Get the display name or fallback to username"""
        return self.display_name or self.user.username or f"User {self.user.phone_number}"