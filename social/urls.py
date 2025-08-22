"""
URL configuration for social app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

app_name = 'social'

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
]