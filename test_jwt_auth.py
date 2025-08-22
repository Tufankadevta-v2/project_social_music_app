#!/usr/bin/env python3
"""
Test script for JWT authentication functionality
"""
import os
import sys
import django
import requests
import json

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'social_task_backend.settings')
django.setup()

from django.test import TestCase, Client
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from user_accounts.models import User, PhoneVerification
from rest_framework_simplejwt.tokens import RefreshToken


def get_response_data(response):
    """Helper function to get response data"""
    if hasattr(response, 'data'):
        return response.data
    else:
        try:
            return json.loads(response.content.decode())
        except:
            return response.content.decode()

def test_jwt_authentication():
    """Test JWT authentication endpoints"""
    print("Testing JWT Authentication...")
    
    client = APIClient()
    
    # Test data
    phone_number = "+1234567890"
    password = "testpass123"
    
    # Clean up any existing user
    User.objects.filter(phone_number=phone_number).delete()
    
    print("\n1. Testing OTP sending...")
    response = client.post('/api/auth/auth/send-otp/', {
        'phone_number': phone_number
    })
    print(f"Send OTP Response: {response.status_code}")
    print(f"Response data: {get_response_data(response)}")
    
    print("\n2. Testing OTP verification...")
    # Use the super OTP for testing
    response = client.post('/api/auth/auth/verify-otp/', {
        'phone_number': phone_number,
        'otp_code': '123456'
    })
    print(f"Verify OTP Response: {response.status_code}")
    print(f"Response data: {get_response_data(response)}")
    
    print("\n3. Testing user registration with JWT...")
    response = client.post('/api/auth/auth/register/', {
        'phone_number': phone_number,
        'password': password,
        'password_confirm': password,
        'first_name': 'Test',
        'last_name': 'User'
    })
    print(f"Register Response: {response.status_code}")
    response_data = get_response_data(response)
    print(f"Response data: {response_data}")
    
    if response.status_code == 201:
        access_token = response_data.get('access')
        refresh_token = response_data.get('refresh')
        
        print(f"\nAccess Token: {access_token[:50] if access_token else 'None'}...")
        print(f"Refresh Token: {refresh_token[:50] if refresh_token else 'None'}...")
        
        print("\n4. Testing JWT login...")
        login_response = client.post('/api/auth/auth/jwt/login/', {
            'phone_number': phone_number,
            'password': password
        })
        print(f"JWT Login Response: {login_response.status_code}")
        login_data = get_response_data(login_response)
        print(f"Response data: {login_data}")
        
        # Use tokens from login if registration didn't provide them
        if not access_token and login_response.status_code == 200:
            access_token = login_data.get('access')
            refresh_token = login_data.get('refresh')
        
        if access_token:
            print("\n5. Testing authenticated request with JWT...")
            client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
            profile_response = client.get('/api/auth/profile/')
            print(f"Profile Response: {profile_response.status_code}")
            print(f"Response data: {get_response_data(profile_response)}")
            
            print("\n6. Testing JWT token refresh...")
            refresh_response = client.post('/api/auth/auth/jwt/refresh/', {
                'refresh': refresh_token
            })
            print(f"Refresh Response: {refresh_response.status_code}")
            print(f"Response data: {get_response_data(refresh_response)}")
            
            print("\n7. Testing JWT logout...")
            logout_response = client.post('/api/auth/auth/jwt/logout/', {
                'refresh': refresh_token
            })
            print(f"Logout Response: {logout_response.status_code}")
            print(f"Response data: {get_response_data(logout_response)}")
            
            print("\n8. Testing access with invalidated token...")
            profile_response_after_logout = client.get('/api/auth/profile/')
            print(f"Profile after logout Response: {profile_response_after_logout.status_code}")
        
    print("\nJWT Authentication test completed!")


if __name__ == '__main__':
    test_jwt_authentication()