from django.apps import AppConfig


class SocialFeedConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'social_feed'
    verbose_name = 'Social Feed'
    
    def ready(self):
        """Import signals when app is ready"""
        try:
            import social_feed.signals
        except ImportError:
            pass