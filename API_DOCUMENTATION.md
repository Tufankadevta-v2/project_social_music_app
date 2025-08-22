# Phone Authentication API Documentation

## Overview

This API provides phone number-based authentication with OTP verification, similar to WhatsApp's authentication system.

## Base URL
```
http://127.0.0.1:8000/api/user_accounts/
```

## Authentication Flow

### 1. Send OTP

**Endpoint:** `POST /auth/send-otp/`

**Description:** Send OTP to a phone number for verification.

**Request Body:**
```json
{
    "phone_number": "+1234567890"
}
```

**Response (Success - 200):**
```json
{
    "message": "OTP sent successfully",
    "phone_number": "+1234567890",
    "expires_in_minutes": 10
}
```

**Response (Error - 400):**
```json
{
    "phone_number": ["This phone number is already registered and verified."]
}
```

### 2. Verify OTP

**Endpoint:** `POST /auth/verify-otp/`

**Description:** Verify the OTP code sent to the phone number.

**Request Body:**
```json
{
    "phone_number": "+1234567890",
    "otp_code": "123456"
}
```

**Response (New User - 200):**
```json
{
    "message": "Phone number verified successfully",
    "user_exists": false,
    "phone_number": "+1234567890",
    "next_step": "complete_registration"
}
```

**Response (Existing User - 200):**
```json
{
    "message": "Phone number verified successfully",
    "user_exists": true,
    "token": "auth_token_here",
    "user": {
        "id": 1,
        "phone_number": "+1234567890",
        "username": "user_1234567890",
        "email": null,
        "first_name": "",
        "last_name": "",
        "is_phone_verified": true,
        "date_joined": "2024-01-01T00:00:00Z",
        "profile": {
            "display_name": "",
            "avatar": null,
            "bio": "",
            "total_points": 0
        }
    }
}
```

### 3. Complete Registration (New Users Only)

**Endpoint:** `POST /auth/register/`

**Description:** Complete user registration after phone verification.

**Request Body:**
```json
{
    "phone_number": "+1234567890",
    "password": "securepassword123",
    "password_confirm": "securepassword123",
    "first_name": "John",
    "last_name": "Doe",
    "display_name": "John D",
    "bio": "Hello, I'm John!"
}
```

**Response (Success - 201):**
```json
{
    "message": "User registered successfully",
    "token": "auth_token_here",
    "user": {
        "id": 1,
        "phone_number": "+1234567890",
        "username": "user_1234567890",
        "email": null,
        "first_name": "John",
        "last_name": "Doe",
        "is_phone_verified": true,
        "date_joined": "2024-01-01T00:00:00Z",
        "profile": {
            "display_name": "John D",
            "avatar": null,
            "bio": "Hello, I'm John!",
            "total_points": 0
        }
    }
}
```

### 4. Login (Existing Users)

**Endpoint:** `POST /auth/login/`

**Description:** Login with phone number and password.

**Request Body:**
```json
{
    "phone_number": "+1234567890",
    "password": "securepassword123"
}
```

**Response (Success - 200):**
```json
{
    "message": "Login successful",
    "token": "auth_token_here",
    "user": {
        "id": 1,
        "phone_number": "+1234567890",
        "username": "user_1234567890",
        "email": null,
        "first_name": "John",
        "last_name": "Doe",
        "is_phone_verified": true,
        "date_joined": "2024-01-01T00:00:00Z",
        "profile": {
            "display_name": "John D",
            "avatar": null,
            "bio": "Hello, I'm John!",
            "total_points": 0
        }
    }
}
```

### 5. Logout

**Endpoint:** `POST /auth/logout/`

**Description:** Logout user by invalidating their token.

**Headers:**
```
Authorization: Token your_auth_token_here
```

**Response (Success - 200):**
```json
{
    "message": "Logout successful"
}
```

### 6. Get User Profile

**Endpoint:** `GET /profile/`

**Description:** Get current user's profile information.

**Headers:**
```
Authorization: Token your_auth_token_here
```

**Response (Success - 200):**
```json
{
    "id": 1,
    "phone_number": "+1234567890",
    "username": "user_1234567890",
    "email": null,
    "first_name": "John",
    "last_name": "Doe",
    "is_phone_verified": true,
    "date_joined": "2024-01-01T00:00:00Z",
    "profile": {
        "display_name": "John D",
        "avatar": null,
        "bio": "Hello, I'm John!",
        "total_points": 0
    }
}
```

## Development Features

### Super OTP

For development and testing purposes, you can use the super OTP code: **123456**

This code will work for any phone number in development mode and bypasses the actual SMS sending.

### SMS Logging

In development mode, OTP codes are logged to the console:
```
📱 SMS to +1234567890: Your verification code is 654321
🔑 Development Super OTP: 123456
```

## Error Handling

All endpoints return appropriate HTTP status codes and error messages:

- **400 Bad Request:** Invalid input data
- **401 Unauthorized:** Authentication required
- **500 Internal Server Error:** Server error

Example error response:
```json
{
    "phone_number": ["Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."]
}
```

## Authentication

After successful login or registration, use the provided token in the Authorization header:

```
Authorization: Token your_auth_token_here
```

## Testing

Run the test suite:
```bash
python3 manage.py test user_accounts
```

Test the API manually:
```bash
python3 test_auth_api.py
```

## Requirements Covered

This implementation covers the following requirements:

- **1.1:** Phone number verification via OTP ✅
- **1.2:** OTP sending and verification ✅  
- **1.3:** Account creation with phone verification ✅
- **1.5:** Authentication using phone number and password ✅

## Next Steps

- Integrate with production SMS service (Twilio, AWS SNS, etc.)
- Add rate limiting for OTP requests
- Implement JWT tokens for enhanced security
- Add phone number change functionality