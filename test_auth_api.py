#!/usr/bin/env python3
"""
Test script to demonstrate the phone authentication API endpoints
"""

import requests
import json
import sys

BASE_URL = "http://127.0.0.1:8000"

def test_authentication_flow():
    """Test the complete authentication flow"""
    
    print("🚀 Testing Phone Authentication API")
    print("=" * 50)
    
    phone_number = "+1234567890"
    
    # Step 1: Send OTP
    print("\n📱 Step 1: Sending OTP...")
    response = requests.post(f"{BASE_URL}/api/user_accounts/auth/send-otp/", {
        "phone_number": phone_number
    })
    
    if response.status_code == 200:
        print("✅ OTP sent successfully!")
        print(f"Response: {response.json()}")
    else:
        print(f"❌ Failed to send OTP: {response.status_code}")
        print(f"Error: {response.text}")
        return
    
    # Step 2: Verify OTP (using super OTP)
    print("\n🔐 Step 2: Verifying OTP with super OTP (123456)...")
    response = requests.post(f"{BASE_URL}/api/user_accounts/auth/verify-otp/", {
        "phone_number": phone_number,
        "otp_code": "123456"
    })
    
    if response.status_code == 200:
        data = response.json()
        print("✅ OTP verified successfully!")
        print(f"User exists: {data.get('user_exists')}")
        
        if not data.get('user_exists'):
            # Step 3: Complete registration for new user
            print("\n👤 Step 3: Completing user registration...")
            response = requests.post(f"{BASE_URL}/api/user_accounts/auth/register/", {
                "phone_number": phone_number,
                "password": "testpass123",
                "password_confirm": "testpass123",
                "first_name": "Test",
                "last_name": "User",
                "display_name": "Test User"
            })
            
            if response.status_code == 201:
                data = response.json()
                print("✅ User registered successfully!")
                token = data.get('token')
                print(f"Auth token: {token}")
                
                # Step 4: Test authenticated endpoint
                print("\n🔒 Step 4: Testing authenticated profile endpoint...")
                headers = {"Authorization": f"Token {token}"}
                response = requests.get(f"{BASE_URL}/api/user_accounts/profile/", headers=headers)
                
                if response.status_code == 200:
                    print("✅ Profile retrieved successfully!")
                    print(f"Profile: {json.dumps(response.json(), indent=2)}")
                else:
                    print(f"❌ Failed to get profile: {response.status_code}")
            else:
                print(f"❌ Registration failed: {response.status_code}")
                print(f"Error: {response.text}")
        else:
            # Existing user - already has token
            token = data.get('token')
            print(f"✅ Existing user logged in! Token: {token}")
    else:
        print(f"❌ OTP verification failed: {response.status_code}")
        print(f"Error: {response.text}")
    
    print("\n🎉 Authentication flow test completed!")

if __name__ == "__main__":
    try:
        test_authentication_flow()
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure Django server is running:")
        print("   python3 manage.py runserver")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        sys.exit(1)