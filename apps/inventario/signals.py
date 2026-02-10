import logging
from datetime import date, timedelta
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.inventario.models import Producto, LoteInventario
from apps.inventario.services.alertasvencimiento import notificar_lotes_por_vencer, _usuarios_con_permiso_notificaciones

logger = logging.getLogger(__name__)


@receiver(user_logged_in)
def notificar_lotes_por_vencer_login(sender, request, user, **kwargs):
    # Solo notificar a usuarios con permiso
    if not _usuarios_con_permiso_notificaciones().filter(id=user.id).exists():
        logger.info("Notificaciones vencimiento | usuario=%s | sin permiso", user.username)
        return
    total = notificar_lotes_por_vencer(dias_alerta=3, usuarios=[user])
    logger.info("Notificaciones vencimiento | usuario=%s | creadas=%s", user.username, total)


@receiver(post_save, sender=Producto)
def notificar_producto_actualizado(sender, instance, created, **kwargs):
    """
    Dispara notificación al crear/actualizar producto (revisa lotes activos).
    """
    lotes = LoteInventario.objects.filter(
        producto=instance,
        fecha_vencimiento__isnull=False,
        status_model=LoteInventario.STATUS_MODEL_ACTIVE,
        cantidad__gt=0
    )
    if not lotes.exists():
        logger.info("Producto actualizado sin lotes activos | producto_id=%s", instance.id)
        return
    total = notificar_lotes_por_vencer(dias_alerta=3, lotes=lotes)
    logger.info("Producto actualizado | producto_id=%s | notificaciones=%s", instance.id, total)


@receiver(post_save, sender=LoteInventario)
def notificar_lote_actualizado(sender, instance, created, **kwargs):
    """
    Dispara notificación al crear/actualizar lotes con fecha de vencimiento.
    """
    if not instance.fecha_vencimiento:
        logger.info("Lote actualizado sin fecha_vencimiento | lote_id=%s", instance.id)
        return
    total = notificar_lotes_por_vencer(dias_alerta=3, lotes=[instance])
    logger.info("Lote actualizado | lote_id=%s | notificaciones=%s", instance.id, total)
