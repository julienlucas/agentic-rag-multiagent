from django.apps import AppConfig


class SaasConfig(AppConfig):
    name = "backend.saas"
    label = "saas"
    verbose_name = "Produit"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from django.contrib.auth import get_user_model
        from django.db.models.signals import post_save

        from . import ingestion
        from .accounts import create_workspace

        post_save.connect(create_workspace, sender=get_user_model(), dispatch_uid="saas_create_workspace")
        if ingestion.is_running_server():
            ingestion.start()
