from datetime import date, timedelta
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from apps.inventario.models import Producto
from apps.erp.models import Notificacion


@receiver(user_logged_in)
def notificar_productos_por_vencer(sender, request, user, **kwargs):
    hoy = date.today()
    dias_alerta = 3
    alerta = hoy + timedelta(days=dias_alerta)

    productos = Producto.objects.exclude(horas_caducidad=None)

    for producto in productos:
        fecha_vencimiento = (
            producto.created_at + timedelta(hours=producto.horas_caducidad)
        ).date()

        # Solo vencidos o por vencer en 72 hrs
        if fecha_vencimiento <= alerta:
            estado = "vencido" if fecha_vencimiento < hoy else "por vencer"

            titulo = "⚠ Producto vencido" if estado == "vencido" else "⚠ Producto por vencer"

            mensaje = (
                f"El producto '{producto.nombre}' "
                f"{'ya venció' if estado == 'vencido' else 'vencerá'} el "
                f"{fecha_vencimiento}."
            )

            # Evitar duplicados
            Notificacion.objects.get_or_create(
                tipo=Notificacion.TIPO_MENSAJE,
                titulo=titulo,
                mensaje=mensaje,
                usuario=user
            )
