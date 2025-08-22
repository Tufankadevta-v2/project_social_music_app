from django.apps import AppConfig


class TaskManagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'task_management'
    
    def ready(self):
        """Import signals when the app is ready"""
        import task_management.signals
