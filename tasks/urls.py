"""
URL configuration for tasks app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

app_name = 'tasks'

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
]