#!/usr/bin/env python3
"""
Simple test script for JWT authentication functionality
"""
import os
import sys
import django
import json

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'social_task_backend.settings')
django.setup()

from rest_framework.test import APIClient
from user_accounts.models import User, PhoneVerification
from rest_framework_simplejwt.tokens import RefreshToken


def test_jwt_simple():
    """Test JWT authentication with pre-created user"""
    print("Testing JWT Authentication (Simple)...")
    
    client = APIClient()
    
    # Test data
    phone_number = "+1234567890"
    password = "testpass123"
    
    # Clean up and create user directly
    User.objects.filter(phone_number=phone_number).delete()
    
    # Create user directly
    user = User.objects.create_user(
        phone_number=phone_number,
        password=password,
        username=f"user_{phone_number.replace('+', '').replace(' ', '')}",
        is_phone_verified=True
    )
    
    print(f"Created user: {user.phone_number}")
    
    def get_response_data(response):
        """Helper function to get response data"""
        if hasattr(response, 'data'):
            return response.data
        else:
            try:
                return json.loads(response.content.decode())
            except:
                return response.content.decode()
    
    print("\n1. Testing JWT login...")
    login_response = client.post('/api/auth/auth/jwt/login/', {
        'phone_number': phone_number,
        'password': password
    })
    print(f"JWT Login Response: {login_response.status_code}")
    login_data = get_response_data(login_response)
    print(f"Response data: {login_data}")
    
    if login_response.status_code == 200:
        access_token = login_data.get('access')
        refresh_token = login_data.get('refresh')
        
        print(f"\nAccess Token: {access_token[:50] if access_token else 'None'}...")
        print(f"Refresh Token: {refresh_token[:50] if refresh_token else 'None'}...")
        
        if access_token:
            print("\n2. Testing authenticated request with JWT...")
            client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
            profile_response = client.get('/api/auth/profile/')
            print(f"Profile Response: {profile_response.status_code}")
            print(f"Response data: {get_response_data(profile_response)}")
            
            print("\n3. Testing JWT token refresh...")
            refresh_response = client.post('/api/auth/auth/jwt/refresh/', {
                'refresh': refresh_token
            })
            print(f"Refresh Response: {refresh_response.status_code}")
            refresh_data = get_response_data(refresh_response)
            print(f"Response data: {refresh_data}")
            
            if refresh_response.status_code == 200:
                new_access_token = refresh_data.get('access')
                print(f"New Access Token: {new_access_token[:50] if new_access_token else 'None'}...")
                
                print("\n4. Testing with new access token...")
                client.credentials(HTTP_AUTHORIZATION=f'Bearer {new_access_token}')
                profile_response2 = client.get('/api/auth/profile/')
                print(f"Profile Response with new token: {profile_response2.status_code}")
            
            print("\n5. Testing JWT logout...")
            logout_response = client.post('/api/auth/auth/jwt/logout/', {
                'refresh': refresh_token
            })
            print(f"Logout Response: {logout_response.status_code}")
            print(f"Response data: {get_response_data(logout_response)}")
            
            print("\n6. Testing access with invalidated token...")
            profile_response_after_logout = client.get('/api/auth/profile/')
            print(f"Profile after logout Response: {profile_response_after_logout.status_code}")
            
            print("\n7. Testing refresh with blacklisted token...")
            refresh_after_logout = client.post('/api/auth/auth/jwt/refresh/', {
                'refresh': refresh_token
            })
            print(f"Refresh after logout Response: {refresh_after_logout.status_code}")
        
    print("\nJWT Authentication test completed!")


if __name__ == '__main__':
    test_jwt_simple()