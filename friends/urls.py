"""
URL configuration for friends app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

app_name = 'friends'

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
]