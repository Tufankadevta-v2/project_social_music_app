"""
URL configuration for accounts app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

app_name = 'accounts'

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
]