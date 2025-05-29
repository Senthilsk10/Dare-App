from django.apps import AppConfig
from django.db.models.signals import post_migrate


def create_groups_and_permissions(sender, **kwargs):
    from .signals import create_default_groups_and_permissions
    create_default_groups_and_permissions(sender, **kwargs)


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "users"
    
    def ready(self):
        import users.signals
        
        # Connect the post_migrate signal to create default groups and permissions
        post_migrate.connect(
            create_groups_and_permissions, 
            sender=self,
            dispatch_uid="create_default_groups_and_permissions"
        )
