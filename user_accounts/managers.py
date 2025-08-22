from django.contrib.auth.models import BaseUserManager
from django.core.exceptions import ValidationError
from django.core.validators import validate_email


class UserManager(BaseUserManager):
    """
    Custom manager for User model with phone number authentication
    """
    
    def _create_user(self, phone_number, password=None, **extra_fields):
        """
        Create and save a user with the given phone number and password
        """
        if not phone_number:
            raise ValueError('The Phone Number field must be set')
        
        # Generate username if not provided
        if not extra_fields.get('username'):
            extra_fields['username'] = f"user_{phone_number.replace('+', '').replace(' ', '')}"
        
        # Validate email if provided
        email = extra_fields.get('email')
        if email:
            try:
                validate_email(email)
                extra_fields['email'] = self.normalize_email(email)
            except ValidationError:
                raise ValueError('Invalid email address')
        
        user = self.model(phone_number=phone_number, **extra_fields)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_user(self, phone_number, password=None, **extra_fields):
        """
        Create and save a regular user
        """
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(phone_number, password, **extra_fields)
    
    def create_superuser(self, phone_number, password=None, **extra_fields):
        """
        Create and save a superuser
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_phone_verified', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self._create_user(phone_number, password, **extra_fields)
    
    def get_by_natural_key(self, username):
        """
        Allow authentication using phone number
        """
        return self.get(**{f'{self.model.USERNAME_FIELD}__iexact': username})
    
    def verified_users(self):
        """
        Return only users with verified phone numbers
        """
        return self.filter(is_phone_verified=True)
    
    def unverified_users(self):
        """
        Return only users with unverified phone numbers
        """
        return self.filter(is_phone_verified=False)
    
    def active_verified_users(self):
        """
        Return active users with verified phone numbers
        """
        return self.filter(is_active=True, is_phone_verified=True)