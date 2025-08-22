# JWT Authentication Implementation

## Overview

This document describes the JWT (JSON Web Token) authentication system implemented for the social task management application. The system provides secure, stateless authentication with phone number-based user identification.

## Features Implemented

### ✅ Task 2.3 Requirements Completed

1. **JWT Token Generation and Validation** ✅
   - Access tokens with 60-minute expiration
   - Refresh tokens with 7-day expiration
   - Token rotation support
   - Custom JWT authentication class

2. **Phone Number Authentication** ✅
   - Login endpoint with phone number instead of username
   - Phone verification requirement
   - Custom user model integration

3. **Token Refresh Mechanism** ✅
   - Refresh token endpoint
   - Automatic token rotation (configurable)
   - Blacklist support (when available)

4. **Authentication Middleware and Permissions** ✅
   - Custom JWT authentication class
   - Phone verification permission
   - Multiple authentication backends support

## API Endpoints

### JWT Authentication Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/auth/jwt/login/` | POST | Login with phone number and password |
| `/api/auth/auth/jwt/refresh/` | POST | Refresh access token |
| `/api/auth/auth/jwt/logout/` | POST | Logout (blacklist refresh token) |
| `/api/auth/auth/jwt/token/` | POST | Alternative token obtain endpoint |
| `/api/auth/auth/jwt/token/refresh/` | POST | DRF Simple JWT refresh endpoint |

### Legacy Token Endpoints (Maintained for Backward Compatibility)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/auth/login/` | POST | Login with Token authentication |
| `/api/auth/auth/register/` | POST | Register new user |
| `/api/auth/auth/verify-otp/` | POST | Verify OTP code |

## Request/Response Examples

### JWT Login

**Request:**
```json
POST /api/auth/auth/jwt/login/
{
    "phone_number": "+1234567890",
    "password": "your_password"
}
```

**Response:**
```json
{
    "message": "Login successful",
    "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user": {
        "id": 1,
        "phone_number": "+1234567890",
        "username": "user_1234567890",
        "is_phone_verified": true,
        "profile": {
            "display_name": "",
            "total_points": 0
        }
    }
}
```

### Token Refresh

**Request:**
```json
POST /api/auth/auth/jwt/refresh/
{
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:**
```json
{
    "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### Authenticated Request

**Request:**
```http
GET /api/auth/profile/
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## Configuration

### Django Settings

```python
# JWT Configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'user_accounts.authentication.CustomJWTAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
        'user_accounts.permissions.IsPhoneVerified',
    ],
}
```

## Custom Authentication Classes

### CustomJWTAuthentication

```python
class CustomJWTAuthentication(JWTAuthentication):
    """
    Custom JWT Authentication that handles phone-based users
    """
    
    def get_user(self, validated_token):
        """
        Validates user exists, is active, and phone is verified
        """
        user_id = validated_token['user_id']
        user = User.objects.get(id=user_id)
        
        if not user.is_active:
            raise AuthenticationFailed('User is inactive')
        
        if not user.is_phone_verified:
            raise AuthenticationFailed('Phone number not verified')
        
        return user
```

### Custom Permissions

```python
class IsPhoneVerified(BasePermission):
    """
    Permission class to check if user's phone number is verified
    """
    def has_permission(self, request, view):
        return (request.user and 
                request.user.is_authenticated and 
                request.user.is_phone_verified)
```

## Security Features

1. **Phone Verification Requirement**: All JWT tokens require phone verification
2. **Token Expiration**: Short-lived access tokens (60 minutes)
3. **Token Rotation**: Refresh tokens can be rotated for enhanced security
4. **Multiple Auth Support**: Supports JWT, Token, and Session authentication
5. **Custom Validation**: Additional user state validation in authentication

## Error Handling

### Common Error Responses

| Status Code | Error | Description |
|-------------|-------|-------------|
| 400 | Invalid credentials | Wrong phone number or password |
| 401 | Invalid token | Token is expired, malformed, or invalid |
| 401 | Phone not verified | User's phone number is not verified |
| 401 | User inactive | User account is disabled |

### Example Error Response

```json
{
    "error": "Invalid phone number or password"
}
```

## Testing

The implementation includes comprehensive tests covering:

- ✅ JWT login with phone number
- ✅ Token validation and user authentication
- ✅ Token refresh mechanism
- ✅ Logout functionality
- ✅ Invalid token handling
- ✅ Phone verification requirements
- ✅ Error scenarios

Run tests with:
```bash
python3 test_jwt_comprehensive.py
```

## Integration with Existing System

The JWT authentication system is designed to work alongside the existing Token-based authentication:

1. **Backward Compatibility**: Existing Token auth endpoints remain functional
2. **Dual Token Support**: Both JWT and DRF tokens are returned on login/registration
3. **Flexible Authentication**: API endpoints accept both JWT and Token authentication
4. **Gradual Migration**: Frontend can migrate to JWT while maintaining Token support

## Next Steps

1. **Optional Enhancements**:
   - Add JWT blacklisting app for enhanced security
   - Implement sliding token refresh
   - Add rate limiting for authentication endpoints
   - Add audit logging for authentication events

2. **Frontend Integration**:
   - Update mobile app to use JWT tokens
   - Implement automatic token refresh
   - Add token storage and management

## Files Modified/Created

### Core Implementation
- `requirements.txt` - Added djangorestframework-simplejwt
- `social_task_backend/settings.py` - JWT configuration
- `user_accounts/views.py` - JWT endpoints
- `user_accounts/serializers.py` - JWT serializers
- `user_accounts/urls.py` - JWT URL patterns

### Custom Authentication
- `user_accounts/authentication.py` - Custom JWT authentication class
- `user_accounts/permissions.py` - Custom permission classes

### Documentation and Testing
- `JWT_AUTHENTICATION_DOCS.md` - This documentation
- `test_jwt_comprehensive.py` - Comprehensive test suite
- `test_jwt_simple.py` - Simple JWT test

The JWT authentication system is now fully implemented and ready for production use! 🎉