import django_filters
from django.utils import timezone
from .models import Task


class TaskFilter(django_filters.FilterSet):
    """
    Filter class for Task model with various filtering options
    """
    # Status filtering
    status = django_filters.ChoiceFilter(choices=Task.STATUS_CHOICES)
    
    # Priority filtering
    priority = django_filters.ChoiceFilter(choices=Task.PRIORITY_CHOICES)
    
    # Date range filtering
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    
    # Deadline filtering
    deadline_after = django_filters.DateTimeFilter(field_name='deadline', lookup_expr='gte')
    deadline_before = django_filters.DateTimeFilter(field_name='deadline', lookup_expr='lte')
    
    # Points range filtering
    min_points = django_filters.NumberFilter(field_name='points_value', lookup_expr='gte')
    max_points = django_filters.NumberFilter(field_name='points_value', lookup_expr='lte')
    
    # Boolean filters
    is_shared = django_filters.BooleanFilter()
    is_private = django_filters.BooleanFilter()
    has_deadline = django_filters.BooleanFilter(field_name='deadline', lookup_expr='isnull', exclude=True)
    
    # Custom filters
    is_overdue = django_filters.BooleanFilter(method='filter_overdue')
    due_soon = django_filters.BooleanFilter(method='filter_due_soon')
    completed_today = django_filters.BooleanFilter(method='filter_completed_today')
    completed_this_week = django_filters.BooleanFilter(method='filter_completed_this_week')
    
    class Meta:
        model = Task
        fields = [
            'status', 'priority', 'is_shared', 'is_private',
            'created_after', 'created_before',
            'deadline_after', 'deadline_before',
            'min_points', 'max_points', 'has_deadline',
            'is_overdue', 'due_soon', 'completed_today', 'completed_this_week'
        ]
    
    def filter_overdue(self, queryset, name, value):
        """Filter for overdue tasks"""
        if value:
            now = timezone.now()
            return queryset.filter(
                deadline__lt=now,
                status__in=['pending', 'overdue']
            )
        return queryset
    
    def filter_due_soon(self, queryset, name, value):
        """Filter for tasks due within next 24 hours"""
        if value:
            now = timezone.now()
            tomorrow = now + timezone.timedelta(days=1)
            return queryset.filter(
                deadline__gte=now,
                deadline__lte=tomorrow,
                status='pending'
            )
        return queryset
    
    def filter_completed_today(self, queryset, name, value):
        """Filter for tasks completed today"""
        if value:
            today = timezone.now().date()
            return queryset.filter(
                status='completed',
                completed_at__date=today
            )
        return queryset
    
    def filter_completed_this_week(self, queryset, name, value):
        """Filter for tasks completed this week"""
        if value:
            now = timezone.now()
            week_start = now - timezone.timedelta(days=now.weekday())
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            
            return queryset.filter(
                status='completed',
                completed_at__gte=week_start
            )
        return queryset