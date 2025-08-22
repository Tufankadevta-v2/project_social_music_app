"""
Custom permission classes for JWT authentication and phone verification
"""
from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied


class IsPhoneVerified(BasePermission):
    """
    Permission class to check if user's phone number is verified
    """
    message = 'Phone number must be verified to access this resource.'
    
    def has_permission(self, request, view):
        """
        Check if user is authenticated and phone is verified
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        return request.user.is_phone_verified


class IsOwnerOrReadOnly(BasePermission):
    """
    Permission class to allow owners to edit their own objects
    """
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user owns the object or is requesting read-only access
        """
        # Read permissions for any request
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        
        # Write permissions only to the owner
        return obj.user == request.user


class IsActiveUser(BasePermission):
    """
    Permission class to check if user account is active
    """
    message = 'User account is inactive.'
    
    def has_permission(self, request, view):
        """
        Check if user is authenticated and active
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        return request.user.is_active


class JWTAuthenticationRequired(BasePermission):
    """
    Permission class that requires JWT authentication
    """
    message = 'JWT authentication required.'
    
    def has_permission(self, request, view):
        """
        Check if request has valid JWT authentication
        """
        # Check if user is authenticated via JWT
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if authentication was done via JWT
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return False
        
        return True