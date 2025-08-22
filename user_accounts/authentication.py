"""
Custom authentication classes for JWT and phone-based authentication
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class CustomJWTAuthentication(JWTAuthentication):
    """
    Custom JWT Authentication that handles phone-based users
    """
    
    def get_user(self, validated_token):
        """
        Attempts to find and return a user using the given validated token.
        """
        try:
            user_id = validated_token['user_id']
        except KeyError:
            raise InvalidToken(_('Token contained no recognizable user identification'))

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise AuthenticationFailed(_('User not found'), code='user_not_found')

        if not user.is_active:
            raise AuthenticationFailed(_('User is inactive'), code='user_inactive')
        
        if not user.is_phone_verified:
            raise AuthenticationFailed(_('Phone number not verified'), code='phone_not_verified')

        return user


class PhoneNumberAuthentication(BaseAuthentication):
    """
    Custom authentication backend for phone number based authentication
    """
    
    def authenticate(self, request):
        """
        Authenticate using phone number and password from request headers
        """
        phone_number = request.META.get('HTTP_X_PHONE_NUMBER')
        password = request.META.get('HTTP_X_PASSWORD')
        
        if not phone_number or not password:
            return None
        
        try:
            user = User.objects.get(phone_number=phone_number)
            if user.check_password(password) and user.is_active and user.is_phone_verified:
                return (user, None)
        except User.DoesNotExist:
            pass
        
        return None
    
    def authenticate_header(self, request):
        """
        Return a string to be used as the value of the `WWW-Authenticate`
        header in a `401 Unauthenticated` response, or `None` if the
        authentication scheme should return `403 Permission Denied` responses.
        """
        return 'PhoneNumber'