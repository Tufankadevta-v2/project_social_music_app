from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate, login
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
import logging

# JWT imports
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, PhoneVerification, UserProfile
from .serializers import (
    PhoneRegistrationSerializer,
    OTPVerificationSerializer,
    UserRegistrationSerializer,
    LoginSerializer,
    UserSerializer
)
from .services import SMSService

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])
def send_otp(request):
    """
    Send OTP to phone number for registration/verification
    """
    serializer = PhoneRegistrationSerializer(data=request.data)
    
    if serializer.is_valid():
        phone_number = serializer.validated_data['phone_number']
        
        try:
            # Create new OTP
            verification = PhoneVerification.create_otp(phone_number)
            
            # Send OTP via SMS
            sms_service = SMSService()
            success = sms_service.send_otp(phone_number, verification.otp_code)
            
            if success:
                return Response({
                    'message': 'OTP sent successfully',
                    'phone_number': phone_number,
                    'expires_in_minutes': PhoneVerification.OTP_EXPIRY_MINUTES
                }, status=status.HTTP_200_OK)
            else:
                # Delete the OTP if SMS failed
                verification.delete()
                return Response({
                    'error': 'Failed to send OTP. Please try again.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            logger.error(f"Error sending OTP to {phone_number}: {str(e)}")
            return Response({
                'error': 'Failed to send OTP. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp(request):
    """
    Verify OTP code for phone number
    """
    serializer = OTPVerificationSerializer(data=request.data)
    
    if serializer.is_valid():
        phone_number = serializer.validated_data['phone_number']
        verification = serializer.validated_data['verification']
        
        # Check if user already exists
        try:
            user = User.objects.get(phone_number=phone_number)
            if not user.is_phone_verified:
                user.is_phone_verified = True
                user.save()
            
            # Generate tokens for existing user
            token, created = Token.objects.get_or_create(user=user)
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            access_token = refresh.access_token
            
            return Response({
                'message': 'Phone number verified successfully',
                'user_exists': True,
                'token': token.key,  # Legacy token
                'access': str(access_token),  # JWT access token
                'refresh': str(refresh),  # JWT refresh token
                'user': UserSerializer(user).data
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            # User doesn't exist, they need to complete registration
            return Response({
                'message': 'Phone number verified successfully',
                'user_exists': False,
                'phone_number': phone_number,
                'next_step': 'complete_registration'
            }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    """
    Complete user registration after phone verification
    """
    serializer = UserRegistrationSerializer(data=request.data)
    
    if serializer.is_valid():
        try:
            user = serializer.save()
            
            # Generate authentication tokens
            token, created = Token.objects.get_or_create(user=user)
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            access_token = refresh.access_token
            
            return Response({
                'message': 'User registered successfully',
                'token': token.key,  # Legacy token
                'access': str(access_token),  # JWT access token
                'refresh': str(refresh),  # JWT refresh token
                'user': UserSerializer(user).data
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error registering user: {str(e)}")
            return Response({
                'error': 'Registration failed. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_user(request):
    """
    Login user with phone number and password
    """
    serializer = LoginSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.validated_data['user']
        
        # Generate or get token
        token, created = Token.objects.get_or_create(user=user)
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token
        
        return Response({
            'message': 'Login successful',
            'token': token.key,  # Legacy token
            'access': str(access_token),  # JWT access token
            'refresh': str(refresh),  # JWT refresh token
            'user': UserSerializer(user).data
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def logout_user(request):
    """
    Logout user by deleting their token
    """
    try:
        request.user.auth_token.delete()
        return Response({
            'message': 'Logout successful'
        }, status=status.HTTP_200_OK)
    except:
        return Response({
            'error': 'Logout failed'
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def user_profile(request):
    """
    Get current user profile
    """
    serializer = UserSerializer(request.user)
    return Response(serializer.data, status=status.HTTP_200_OK)

# JWT Authentication Views
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from .serializers import JWTLoginSerializer, JWTTokenSerializer


@api_view(['POST'])
@permission_classes([AllowAny])
def jwt_login(request):
    """
    JWT-based login endpoint with phone number authentication
    """
    serializer = JWTLoginSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.validated_data['user']
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token
        
        return Response({
            'message': 'Login successful',
            'access': str(access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def jwt_refresh(request):
    """
    JWT token refresh endpoint
    """
    refresh_token = request.data.get('refresh')
    
    if not refresh_token:
        return Response({
            'error': 'Refresh token is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        refresh = RefreshToken(refresh_token)
        access_token = refresh.access_token
        
        # Optionally rotate refresh token
        simple_jwt_settings = getattr(settings, 'SIMPLE_JWT', {})
        if simple_jwt_settings.get('ROTATE_REFRESH_TOKENS', False):
            # Get user from token payload
            user_id = refresh.payload.get('user_id')
            user = User.objects.get(id=user_id)
            
            # Create new refresh token
            new_refresh = RefreshToken.for_user(user)
            
            # Try to blacklist old token if blacklist app is available
            try:
                refresh.blacklist()
            except AttributeError:
                # Blacklist functionality not available, just continue
                pass
            
            return Response({
                'access': str(access_token),
                'refresh': str(new_refresh)
            }, status=status.HTTP_200_OK)
        
        return Response({
            'access': str(access_token)
        }, status=status.HTTP_200_OK)
        
    except TokenError as e:
        return Response({
            'error': 'Invalid refresh token'
        }, status=status.HTTP_401_UNAUTHORIZED)
    except User.DoesNotExist:
        return Response({
            'error': 'User not found'
        }, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
def jwt_logout(request):
    """
    JWT logout endpoint - blacklist refresh token
    """
    refresh_token = request.data.get('refresh')
    
    if not refresh_token:
        return Response({
            'error': 'Refresh token is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        token = RefreshToken(refresh_token)
        
        # Try to blacklist token if blacklist app is available
        try:
            token.blacklist()
        except AttributeError:
            # Blacklist functionality not available, just return success
            pass
        
        return Response({
            'message': 'Logout successful'
        }, status=status.HTTP_200_OK)
        
    except TokenError:
        return Response({
            'error': 'Invalid refresh token'
        }, status=status.HTTP_400_BAD_REQUEST)


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom JWT token obtain view with phone number authentication
    """
    def post(self, request, *args, **kwargs):
        # Use phone number instead of username
        if 'phone_number' in request.data:
            request.data['username'] = request.data['phone_number']
        
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == 200:
            # Add user data to response
            user = authenticate(
                username=request.data.get('username'),
                password=request.data.get('password')
            )
            if user:
                response.data['user'] = UserSerializer(user).data
        
        return response