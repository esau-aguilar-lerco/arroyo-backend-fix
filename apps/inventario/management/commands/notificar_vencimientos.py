from django.core.management.base import BaseCommand
from apps.inventario.services.alertasvencimiento import (
    notificar_productos_por_vencer
)


class Command(BaseCommand):
    help = "Notifica productos próximos a vencer"

    def handle(self, *args, **options):
        total = notificar_productos_por_vencer(dias=30)
        self.stdout.write(
            self.style.SUCCESS(f"✔ Notificaciones creadas: {total}")
        )
