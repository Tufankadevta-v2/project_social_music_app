"""
WebSocket authentication middleware for Django Channels.
"""
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from user_accounts.models import User
from urllib.parse import parse_qs


class JWTAuthMiddleware(BaseMiddleware):
    """
    Custom middleware to authenticate WebSocket connections using JWT tokens.
    """
    
    def __init__(self, inner):
        super().__init__(inner)
    
    async def __call__(self, scope, receive, send):
        # Only process WebSocket connections
        if scope['type'] == 'websocket':
            # Extract token from query parameters
            query_string = scope.get('query_string', b'').decode()
            query_params = parse_qs(query_string)
            token = query_params.get('token', [None])[0]
            
            if token:
                user = await self.get_user_from_token(token)
                scope['user'] = user
            else:
                scope['user'] = AnonymousUser()
        
        return await super().__call__(scope, receive, send)
    
    @database_sync_to_async
    def get_user_from_token(self, token):
        """
        Validate JWT token and return the associated user.
        """
        try:
            # Validate the token
            access_token = AccessToken(token)
            user_id = access_token['user_id']
            
            # Get the user
            user = User.objects.get(id=user_id)
            
            # Check if user is active and phone verified
            if user.is_active and user.is_phone_verified:
                return user
            else:
                return AnonymousUser()
                
        except (InvalidToken, TokenError, User.DoesNotExist, KeyError):
            return AnonymousUser()
        except Exception:
            return AnonymousUser()


def JWTAuthMiddlewareStack(inner):
    """
    Convenience function to create the JWT auth middleware stack.
    """
    return JWTAuthMiddleware(inner)