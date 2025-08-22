from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User, PhoneVerification, UserProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Admin configuration for custom User model
    """
    list_display = (
        'phone_number', 'username', 'email', 'is_phone_verified', 
        'is_active', 'is_staff', 'date_joined'
    )
    list_filter = (
        'is_phone_verified', 'is_active', 'is_staff', 'is_superuser', 'date_joined'
    )
    search_fields = ('phone_number', 'username', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {
            'fields': ('phone_number', 'username', 'password')
        }),
        ('Personal info', {
            'fields': ('first_name', 'last_name', 'email')
        }),
        ('Verification', {
            'fields': ('is_phone_verified',)
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important dates', {
            'fields': ('last_login', 'date_joined')
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'username', 'password1', 'password2'),
        }),
    )
    
    readonly_fields = ('date_joined', 'last_login')


@admin.register(PhoneVerification)
class PhoneVerificationAdmin(admin.ModelAdmin):
    """
    Admin configuration for PhoneVerification model
    """
    list_display = (
        'phone_number', 'otp_code', 'created_at', 'expires_at', 
        'is_used', 'attempts', 'is_expired_display'
    )
    list_filter = ('is_used', 'created_at', 'expires_at')
    search_fields = ('phone_number', 'otp_code')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'expires_at', 'is_expired_display')
    
    def is_expired_display(self, obj):
        """Display whether the OTP is expired with color coding"""
        if obj.is_expired():
            return format_html('<span style="color: red;">Expired</span>')
        else:
            return format_html('<span style="color: green;">Valid</span>')
    is_expired_display.short_description = 'Status'
    
    def has_add_permission(self, request):
        """Disable manual addition of OTP records"""
        return False


class UserProfileInline(admin.StackedInline):
    """
    Inline admin for UserProfile
    """
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = ('display_name', 'bio', 'avatar', 'total_points')
    readonly_fields = ('total_points',)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """
    Admin configuration for UserProfile model
    """
    list_display = ('user', 'display_name', 'total_points', 'created_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('user__phone_number', 'user__username', 'display_name')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at', 'total_points')
    
    fieldsets = (
        (None, {
            'fields': ('user', 'display_name', 'bio', 'avatar')
        }),
        ('Statistics', {
            'fields': ('total_points',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


# Add UserProfile inline to User admin
UserAdmin.inlines = [UserProfileInline]