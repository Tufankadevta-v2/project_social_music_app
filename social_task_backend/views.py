from django.http import JsonResponse
from django.shortcuts import render

def home(request):
    """Home page view that serves the main dashboard UI"""
    return render(request, 'dashboard.html')

def api_root(request):
    """API root view"""
    return JsonResponse({
        'message': 'Social Task Management API',
        'version': '1.0.0',
        'endpoints': {
            'auth': '/api/auth/',
            'friends': '/api/friends/',
            'tasks': '/api/tasks/',
            'social': '/api/social/',
            'notifications': '/api/notifications/',
        }
    })