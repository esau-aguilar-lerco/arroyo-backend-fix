from django.apps import AppConfig


class CreditoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.credito'
    
    def ready(self):
        import apps.credito.signals.permisos  # Importar señales al iniciar la aplicación
