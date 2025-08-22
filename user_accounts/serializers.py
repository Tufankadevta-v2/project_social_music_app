from rest_framework import serializers
from django.contrib.auth import authenticate
from django.core.validators import RegexValidator
from .models import User, PhoneVerification, UserProfile


class PhoneNumberField(serializers.CharField):
    """
    Custom field for phone number validation
    """
    def __init__(self, **kwargs):
        kwargs.setdefault('max_length', 15)
        kwargs.setdefault('validators', [
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
            )
        ])
        super().__init__(**kwargs)


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for UserProfile model
    """
    class Meta:
        model = UserProfile
        fields = ['display_name', 'avatar', 'bio', 'total_points']
        read_only_fields = ['total_points']


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model
    """
    profile = UserProfileSerializer(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'phone_number', 'username', 'email', 'first_name', 
            'last_name', 'is_phone_verified', 'date_joined', 'profile'
        ]
        read_only_fields = ['id', 'is_phone_verified', 'date_joined']
    
    def validate_phone_number(self, value):
        """
        Validate that phone number is unique (excluding current user)
        """
        if self.instance:
            # Update case - exclude current user
            if User.objects.filter(phone_number=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError("A user with this phone number already exists.")
        else:
            # Create case
            if User.objects.filter(phone_number=value).exists():
                raise serializers.ValidationError("A user with this phone number already exists.")
        return value


class PhoneRegistrationSerializer(serializers.Serializer):
    """
    Serializer for phone number registration
    """
    phone_number = PhoneNumberField()
    
    def validate_phone_number(self, value):
        """
        Check if phone number is already registered and verified
        """
        if User.objects.filter(phone_number=value, is_phone_verified=True).exists():
            raise serializers.ValidationError("This phone number is already registered and verified.")
        return value


class OTPVerificationSerializer(serializers.Serializer):
    """
    Serializer for OTP verification
    """
    phone_number = PhoneNumberField()
    otp_code = serializers.CharField(
        max_length=6,
        min_length=6,
        validators=[
            RegexValidator(
                regex=r'^\d{6}$',
                message="OTP must be exactly 6 digits."
            )
        ]
    )
    
    def validate(self, attrs):
        """
        Validate the OTP code
        """
        phone_number = attrs.get('phone_number')
        otp_code = attrs.get('otp_code')
        
        is_valid, verification = PhoneVerification.verify_otp(phone_number, otp_code)
        
        if not is_valid:
            if verification is None:
                raise serializers.ValidationError("Invalid OTP code.")
            elif verification.is_expired():
                raise serializers.ValidationError("OTP code has expired. Please request a new one.")
            elif verification.attempts >= PhoneVerification.MAX_ATTEMPTS:
                raise serializers.ValidationError("Maximum verification attempts exceeded. Please request a new OTP.")
            else:
                raise serializers.ValidationError("Invalid OTP code.")
        
        attrs['verification'] = verification
        return attrs


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration after phone verification
    """
    phone_number = PhoneNumberField()
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    
    # Profile fields
    display_name = serializers.CharField(max_length=50, required=False, allow_blank=True)
    bio = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    class Meta:
        model = User
        fields = [
            'phone_number', 'username', 'email', 'first_name', 'last_name',
            'password', 'password_confirm', 'display_name', 'bio'
        ]
        extra_kwargs = {
            'username': {'required': False},
            'email': {'required': False},
            'first_name': {'required': False},
            'last_name': {'required': False},
        }
    
    def validate(self, attrs):
        """
        Validate password confirmation and phone verification
        """
        password = attrs.get('password')
        password_confirm = attrs.pop('password_confirm', None)
        
        if password != password_confirm:
            raise serializers.ValidationError("Passwords do not match.")
        
        phone_number = attrs.get('phone_number')
        
        # Check if phone number has been verified
        if not PhoneVerification.objects.filter(
            phone_number=phone_number,
            is_used=True
        ).exists():
            raise serializers.ValidationError("Phone number must be verified before registration.")
        
        return attrs
    
    def create(self, validated_data):
        """
        Create user and profile
        """
        # Extract profile data
        display_name = validated_data.pop('display_name', '')
        bio = validated_data.pop('bio', '')
        
        # Create user
        user = User.objects.create_user(**validated_data)
        user.is_phone_verified = True
        user.save()
        
        # Update profile (created by signal)
        if hasattr(user, 'profile'):
            user.profile.display_name = display_name
            user.profile.bio = bio
            user.profile.save()
        
        return user


class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login
    """
    phone_number = PhoneNumberField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        """
        Validate login credentials
        """
        phone_number = attrs.get('phone_number')
        password = attrs.get('password')
        
        if phone_number and password:
            # Try to authenticate user
            user = authenticate(username=phone_number, password=password)
            
            if user:
                if not user.is_active:
                    raise serializers.ValidationError("User account is disabled.")
                if not user.is_phone_verified:
                    raise serializers.ValidationError("Phone number is not verified.")
                attrs['user'] = user
            else:
                raise serializers.ValidationError("Invalid phone number or password.")
        else:
            raise serializers.ValidationError("Must include phone number and password.")
        
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    """
    Serializer for password change
    """
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True)
    
    def validate_old_password(self, value):
        """
        Validate old password
        """
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value
    
    def validate(self, attrs):
        """
        Validate new password confirmation
        """
        new_password = attrs.get('new_password')
        new_password_confirm = attrs.get('new_password_confirm')
        
        if new_password != new_password_confirm:
            raise serializers.ValidationError("New passwords do not match.")
        
        return attrs
    
    def save(self):
        """
        Save new password
        """
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class JWTLoginSerializer(serializers.Serializer):
    """
    Serializer for JWT-based user login
    """
    phone_number = PhoneNumberField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        """
        Validate login credentials and return user
        """
        phone_number = attrs.get('phone_number')
        password = attrs.get('password')
        
        if phone_number and password:
            # Try to authenticate user
            user = authenticate(username=phone_number, password=password)
            
            if user:
                if not user.is_active:
                    raise serializers.ValidationError("User account is disabled.")
                if not user.is_phone_verified:
                    raise serializers.ValidationError("Phone number is not verified.")
                attrs['user'] = user
            else:
                raise serializers.ValidationError("Invalid phone number or password.")
        else:
            raise serializers.ValidationError("Must include phone number and password.")
        
        return attrs


class JWTTokenSerializer(serializers.Serializer):
    """
    Serializer for JWT token response
    """
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSerializer(read_only=True)