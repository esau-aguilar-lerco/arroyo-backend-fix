from django.apps import AppConfig


class InventarioConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.inventario'

    def ready(self):
        try:
            # Importar específicamente el módulo de permisos
            import apps.inventario.signals 
            print("✅ Signals de inventario cargados correctamente")
        except ImportError as e:
            print(f"❌ Error cargando signals de inventario: {e}")