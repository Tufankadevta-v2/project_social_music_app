"""
URL configuration for social_task_backend project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns  # Import this

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('admin/', admin.site.urls),
    
    # API URLs
    path('api/', views.api_root, name='api_root'),
    path('api/auth/', include('user_accounts.urls')),
    path('api/friends/', include('friendships.urls')),
    path('api/tasks/', include('task_management.urls')),
    path('api/feed/', include('social_feed.urls')),
]

# This is the correct way to serve static and media files in development
if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns() # Add this line
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)