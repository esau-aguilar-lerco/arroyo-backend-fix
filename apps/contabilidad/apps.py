from django.apps import AppConfig


class ContabilidadConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.contabilidad'
    
    def ready(self):
        import apps.contabilidad.signals  # Asegúrate de que la ruta sea correcta
