from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TaskViewSet, SharedTaskViewSet, AchievementViewSet, UserAchievementViewSet

app_name = 'task_management'

router = DefaultRouter()
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'shared-tasks', SharedTaskViewSet, basename='shared-task')
router.register(r'achievements', AchievementViewSet, basename='achievement')
router.register(r'user-achievements', UserAchievementViewSet, basename='user-achievement')

urlpatterns = [
    path('', include(router.urls)),
]