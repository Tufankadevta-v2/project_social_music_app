from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from .privacy_utils import PrivacyChecker
from .privacy_models import PrivacySettings
import json

User = get_user_model()


class PrivacyValidationMiddleware(MiddlewareMixin):
    """
    Middleware to validate privacy permissions for API requests
    """
    
    # Endpoints that require privacy validation
    PRIVACY_PROTECTED_ENDPOINTS = {
        '/api/tasks/': ['GET'],  # Viewing tasks
        '/api/feed/': ['GET'],   # Viewing activity feed
        '/api/friends/': ['GET'], # Viewing friend profiles
    }
    
    def process_request(self, request):
        """Process incoming request for privacy validation"""
        # Skip privacy validation for non-authenticated users
        if not request.user.is_authenticated:
            return None
        
        # Skip for non-API requests
        if not request.path.startswith('/api/'):
            return None
        
        # Check if this endpoint requires privacy validation
        endpoint_requires_validation = False
        for endpoint, methods in self.PRIVACY_PROTECTED_ENDPOINTS.items():
            if request.path.startswith(endpoint) and request.method in methods:
                endpoint_requires_validation = True
                break
        
        if not endpoint_requires_validation:
            return None
        
        # Add privacy checker to request
        request.privacy_checker = PrivacyChecker(request.user)
        
        return None
    
    def process_response(self, request, response):
        """Process response to ensure privacy compliance"""
        # Skip for non-API requests
        if not request.path.startswith('/api/'):
            return response
        
        # Skip if no privacy checker was added
        if not hasattr(request, 'privacy_checker'):
            return response
        
        # For JSON responses, filter out private data
        if (response.get('Content-Type', '').startswith('application/json') and 
            hasattr(response, 'data')):
            
            try:
                # Filter response data based on privacy settings
                filtered_data = self._filter_response_data(
                    response.data, 
                    request.privacy_checker,
                    request.user
                )
                
                # Update response with filtered data
                response.data = filtered_data
                response.content = json.dumps(filtered_data).encode('utf-8')
                
            except Exception:
                # If filtering fails, return original response
                pass
        
        return response
    
    def _filter_response_data(self, data, privacy_checker, requesting_user):
        """Filter response data based on privacy settings"""
        if isinstance(data, dict):
            # Handle paginated responses
            if 'results' in data:
                data['results'] = [
                    self._filter_item(item, privacy_checker, requesting_user)
                    for item in data['results']
                ]
            else:
                data = self._filter_item(data, privacy_checker, requesting_user)
        
        elif isinstance(data, list):
            data = [
                self._filter_item(item, privacy_checker, requesting_user)
                for item in data
            ]
        
        return data
    
    def _filter_item(self, item, privacy_checker, requesting_user):
        """Filter individual item based on privacy settings"""
        if not isinstance(item, dict):
            return item
        
        # If item has a user field, check privacy permissions
        if 'user' in item and isinstance(item['user'], dict):
            user_id = item['user'].get('id')
            if user_id and user_id != requesting_user.id:
                try:
                    target_user = User.objects.get(id=user_id)
                    
                    # Check if requesting user can view this user's content
                    if not privacy_checker.can_view_user_profile(target_user):
                        # Remove or anonymize private fields
                        item = self._anonymize_user_data(item)
                
                except User.DoesNotExist:
                    pass
        
        # Filter task-specific data
        if 'task' in item or 'title' in item:
            item = self._filter_task_data(item, privacy_checker, requesting_user)
        
        # Filter activity feed data
        if 'activity_type' in item:
            item = self._filter_activity_data(item, privacy_checker, requesting_user)
        
        return item
    
    def _anonymize_user_data(self, item):
        """Anonymize user data for privacy"""
        if 'user' in item and isinstance(item['user'], dict):
            # Keep only basic, non-identifying information
            item['user'] = {
                'id': item['user'].get('id'),
                'username': 'Private User',
                'is_private': True
            }
        
        # Remove sensitive fields
        sensitive_fields = ['phone_number', 'email', 'location', 'bio']
        for field in sensitive_fields:
            if field in item:
                del item[field]
        
        return item
    
    def _filter_task_data(self, item, privacy_checker, requesting_user):
        """Filter task data based on privacy settings"""
        # If this is task data and user can't view tasks, remove details
        if 'user' in item and isinstance(item['user'], dict):
            user_id = item['user'].get('id')
            if user_id and user_id != requesting_user.id:
                try:
                    target_user = User.objects.get(id=user_id)
                    
                    if not privacy_checker.can_view_user_tasks(target_user):
                        # Remove task details but keep basic info
                        item = {
                            'id': item.get('id'),
                            'user': item.get('user'),
                            'title': 'Private Task',
                            'is_private': True
                        }
                
                except User.DoesNotExist:
                    pass
        
        return item
    
    def _filter_activity_data(self, item, privacy_checker, requesting_user):
        """Filter activity feed data based on privacy settings"""
        if 'user' in item and isinstance(item['user'], dict):
            user_id = item['user'].get('id')
            if user_id and user_id != requesting_user.id:
                try:
                    target_user = User.objects.get(id=user_id)
                    
                    if not privacy_checker.can_view_activity_feed(target_user):
                        # This activity should not be visible
                        return None
                    
                    # Check specific activity type permissions
                    activity_type = item.get('activity_type')
                    if activity_type in ['task_completed', 'shared_task_completed']:
                        if not privacy_checker.can_view_task_completions(target_user):
                            return None
                    elif activity_type in ['achievement_earned', 'milestone_reached']:
                        if not privacy_checker.can_view_achievements(target_user):
                            return None
                
                except User.DoesNotExist:
                    pass
        
        return item


class PrivacyHeaderMiddleware(MiddlewareMixin):
    """
    Middleware to add privacy-related headers to responses
    """
    
    def process_response(self, request, response):
        """Add privacy headers to response"""
        if request.path.startswith('/api/'):
            # Add privacy policy header
            response['X-Privacy-Policy'] = 'https://yourapp.com/privacy'
            
            # Add privacy level header for authenticated users
            if request.user.is_authenticated:
                try:
                    privacy_settings = PrivacySettings.get_or_create_for_user(request.user)
                    privacy_level = 'high' if privacy_settings.profile_visibility == 'private' else 'medium'
                    response['X-Privacy-Level'] = privacy_level
                except Exception:
                    response['X-Privacy-Level'] = 'unknown'
        
        return response