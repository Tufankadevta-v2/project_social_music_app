from django.urls import path, include
from rest_framework.routers import DefaultRouter

app_name = 'user_notifications'

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
]