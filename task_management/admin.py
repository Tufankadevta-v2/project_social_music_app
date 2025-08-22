from django.contrib import admin
from django.utils.html import format_html
from .models import Task, SharedTask, TaskParticipation, Achievement, UserAchievement, AchievementProgress


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """
    Admin interface for Task model
    """
    list_display = [
        'title', 'user', 'status', 'priority', 'points_value',
        'deadline', 'is_shared', 'is_private', 'created_at'
    ]
    list_filter = [
        'status', 'priority', 'is_shared', 'is_private',
        'created_at', 'deadline'
    ]
    search_fields = ['title', 'description', 'user__phone_number', 'user__username']
    readonly_fields = ['created_at', 'updated_at', 'completed_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'user')
        }),
        ('Task Settings', {
            'fields': ('priority', 'status', 'deadline', 'points_value')
        }),
        ('Sharing & Privacy', {
            'fields': ('is_shared', 'is_private')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'completed_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('user')
    
    def save_model(self, request, obj, form, change):
        """Custom save logic"""
        if not change:  # Creating new task
            obj.user = obj.user or request.user
        super().save_model(request, obj, form, change)


class TaskParticipationInline(admin.TabularInline):
    """
    Inline admin for TaskParticipation
    """
    model = TaskParticipation
    extra = 0
    readonly_fields = ['joined_at', 'completed_at', 'points_earned', 'completion_rank']
    fields = ['user', 'status', 'joined_at', 'completed_at', 'points_earned']
    
    def completion_rank(self, obj):
        """Display completion rank"""
        return obj.completion_rank or 'Not completed'
    completion_rank.short_description = 'Rank'


@admin.register(SharedTask)
class SharedTaskAdmin(admin.ModelAdmin):
    """
    Admin interface for SharedTask model
    """
    list_display = [
        'task_title', 'creator', 'participant_count', 'is_competitive',
        'max_participants', 'completion_rate', 'created_at'
    ]
    list_filter = ['is_competitive', 'created_at']
    search_fields = ['task__title', 'task__description', 'creator__phone_number']
    readonly_fields = ['created_at', 'participant_count', 'completion_stats_display']
    inlines = [TaskParticipationInline]
    
    fieldsets = (
        ('Task Information', {
            'fields': ('task', 'creator')
        }),
        ('Sharing Settings', {
            'fields': ('is_competitive', 'max_participants')
        }),
        ('Statistics', {
            'fields': ('participant_count', 'completion_stats_display'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'task', 'creator'
        ).prefetch_related('participants')
    
    def task_title(self, obj):
        """Display task title"""
        return obj.task.title
    task_title.short_description = 'Task Title'
    task_title.admin_order_field = 'task__title'
    
    def participant_count(self, obj):
        """Display participant count"""
        return obj.get_participant_count()
    participant_count.short_description = 'Participants'
    
    def completion_rate(self, obj):
        """Display completion rate"""
        stats = obj.get_completion_stats()
        rate = stats['completion_rate']
        color = 'green' if rate >= 75 else 'orange' if rate >= 50 else 'red'
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color, rate
        )
    completion_rate.short_description = 'Completion Rate'
    
    def completion_stats_display(self, obj):
        """Display detailed completion statistics"""
        stats = obj.get_completion_stats()
        return format_html(
            '<strong>Total:</strong> {} | <strong>Completed:</strong> {} | '
            '<strong>Pending:</strong> {} | <strong>Rate:</strong> {:.1f}%',
            stats['total_participants'],
            stats['completed_count'],
            stats['pending_count'],
            stats['completion_rate']
        )
    completion_stats_display.short_description = 'Completion Statistics'


@admin.register(TaskParticipation)
class TaskParticipationAdmin(admin.ModelAdmin):
    """
    Admin interface for TaskParticipation model
    """
    list_display = [
        'shared_task_title', 'user', 'status', 'points_earned',
        'completion_rank_display', 'joined_at', 'completed_at'
    ]
    list_filter = ['status', 'joined_at', 'completed_at']
    search_fields = [
        'shared_task__task__title', 'user__phone_number',
        'user__username'
    ]
    readonly_fields = ['joined_at', 'completion_rank']
    date_hierarchy = 'joined_at'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'shared_task__task', 'user'
        )
    
    def shared_task_title(self, obj):
        """Display shared task title"""
        return obj.shared_task.task.title
    shared_task_title.short_description = 'Shared Task'
    shared_task_title.admin_order_field = 'shared_task__task__title'
    
    def completion_rank_display(self, obj):
        """Display completion rank with formatting"""
        rank = obj.completion_rank
        if rank:
            if rank == 1:
                return format_html('<span style="color: gold;">🥇 1st</span>')
            elif rank == 2:
                return format_html('<span style="color: silver;">🥈 2nd</span>')
            elif rank == 3:
                return format_html('<span style="color: #CD7F32;">🥉 3rd</span>')
            else:
                return f'{rank}th'
        return 'Not completed'
    completion_rank_display.short_description = 'Rank'

@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    """
    Admin interface for Achievement model
    """
    list_display = [
        'name', 'achievement_id', 'category', 'rarity', 'points_reward',
        'unlock_count', 'is_active', 'created_at'
    ]
    list_filter = ['category', 'rarity', 'is_active', 'created_at']
    search_fields = ['name', 'description', 'achievement_id']
    readonly_fields = ['created_at', 'updated_at', 'unlock_count']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('achievement_id', 'name', 'description', 'icon')
        }),
        ('Classification', {
            'fields': ('category', 'rarity', 'points_reward')
        }),
        ('Settings', {
            'fields': ('is_active', 'requirements_data')
        }),
        ('Statistics', {
            'fields': ('unlock_count',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def unlock_count(self, obj):
        """Display number of users who unlocked this achievement"""
        count = obj.user_unlocks.count()
        return format_html(
            '<span style="font-weight: bold;">{}</span>',
            count
        )
    unlock_count.short_description = 'Unlocks'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).prefetch_related('user_unlocks')


class UserAchievementInline(admin.TabularInline):
    """
    Inline admin for UserAchievement
    """
    model = UserAchievement
    extra = 0
    readonly_fields = ['earned_at', 'points_awarded', 'notification_sent']
    fields = ['achievement', 'earned_at', 'points_awarded', 'is_featured', 'notification_sent']


@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    """
    Admin interface for UserAchievement model
    """
    list_display = [
        'user_display', 'achievement_name', 'achievement_category',
        'points_awarded', 'is_featured', 'earned_at'
    ]
    list_filter = [
        'achievement__category', 'achievement__rarity', 'is_featured',
        'earned_at', 'notification_sent'
    ]
    search_fields = [
        'user__phone_number', 'user__username',
        'achievement__name', 'achievement__achievement_id'
    ]
    readonly_fields = ['earned_at', 'points_awarded', 'notification_sent']
    date_hierarchy = 'earned_at'
    
    fieldsets = (
        ('Achievement Information', {
            'fields': ('user', 'achievement', 'earned_at', 'points_awarded')
        }),
        ('Settings', {
            'fields': ('is_featured', 'notification_sent')
        }),
        ('Progress Data', {
            'fields': ('progress_data',),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('user', 'achievement')
    
    def user_display(self, obj):
        """Display user information"""
        return obj.user.phone_number or obj.user.username
    user_display.short_description = 'User'
    user_display.admin_order_field = 'user__phone_number'
    
    def achievement_name(self, obj):
        """Display achievement name"""
        return obj.achievement.name
    achievement_name.short_description = 'Achievement'
    achievement_name.admin_order_field = 'achievement__name'
    
    def achievement_category(self, obj):
        """Display achievement category"""
        return obj.achievement.get_category_display()
    achievement_category.short_description = 'Category'
    achievement_category.admin_order_field = 'achievement__category'


@admin.register(AchievementProgress)
class AchievementProgressAdmin(admin.ModelAdmin):
    """
    Admin interface for AchievementProgress model
    """
    list_display = [
        'user_display', 'achievement_name', 'progress_display',
        'completion_percentage', 'is_completed', 'last_updated'
    ]
    list_filter = [
        'achievement__category', 'last_updated', 'created_at'
    ]
    search_fields = [
        'user__phone_number', 'user__username',
        'achievement__name', 'achievement__achievement_id'
    ]
    readonly_fields = ['completion_percentage', 'is_completed', 'created_at', 'last_updated']
    date_hierarchy = 'last_updated'
    
    fieldsets = (
        ('Progress Information', {
            'fields': ('user', 'achievement', 'current_progress', 'target_progress')
        }),
        ('Status', {
            'fields': ('completion_percentage', 'is_completed')
        }),
        ('Progress Data', {
            'fields': ('progress_data',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'last_updated'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('user', 'achievement')
    
    def user_display(self, obj):
        """Display user information"""
        return obj.user.phone_number or obj.user.username
    user_display.short_description = 'User'
    user_display.admin_order_field = 'user__phone_number'
    
    def achievement_name(self, obj):
        """Display achievement name"""
        return obj.achievement.name
    achievement_name.short_description = 'Achievement'
    achievement_name.admin_order_field = 'achievement__name'
    
    def progress_display(self, obj):
        """Display progress as fraction"""
        return f"{obj.current_progress}/{obj.target_progress}"
    progress_display.short_description = 'Progress'
    
    def completion_percentage(self, obj):
        """Display completion percentage with color coding"""
        percentage = obj.completion_percentage
        if percentage >= 100:
            color = 'green'
        elif percentage >= 75:
            color = 'orange'
        elif percentage >= 50:
            color = 'blue'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, percentage
        )
    completion_percentage.short_description = 'Completion %'