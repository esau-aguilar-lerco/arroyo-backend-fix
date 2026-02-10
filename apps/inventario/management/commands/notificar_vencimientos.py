from django.core.management.base import BaseCommand
from apps.inventario.services.alertasvencimiento import (
    notificar_lotes_por_vencer
)


class Command(BaseCommand):
    help = "Notifica lotes próximos a vencer"

    def handle(self, *args, **options):
        total = notificar_lotes_por_vencer(dias_alerta=30)
        self.stdout.write(
            self.style.SUCCESS(f"✔ Notificaciones creadas: {total}")
        )
