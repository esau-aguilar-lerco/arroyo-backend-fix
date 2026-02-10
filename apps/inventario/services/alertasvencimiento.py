import logging
from datetime import date, timedelta
from django.db.models import Q
from apps.inventario.models import LoteInventario
from apps.erp.models import Notificacion
from apps.usuarios.models import Usuario

logger = logging.getLogger(__name__)


def evaluar_vencimiento(fecha_vencimiento, dias_alerta=3):
    dias_restantes = (fecha_vencimiento - date.today()).days

    if dias_restantes < 0:
        return "vencido", dias_restantes

    if dias_restantes <= dias_alerta:
        return "por_vencer", dias_restantes

    return "vigente", dias_restantes


def _usuarios_con_permiso_notificaciones():
    return Usuario.objects.filter(is_active=True).filter(
        Q(is_superuser=True) |
        Q(groups__name__in=['Compras']) |
        Q(user_permissions__codename='can_create_orden_compra')
    ).distinct()


def lotes_por_vencer(dias_alerta=3, lotes=None):
    if lotes is None:
        lotes = LoteInventario.objects.filter(
            fecha_vencimiento__isnull=False,
            status_model=LoteInventario.STATUS_MODEL_ACTIVE,
            cantidad__gt=0
        ).select_related('producto', 'almacen')

    resultado = []

    for lote in lotes:
        if not lote.fecha_vencimiento:
            continue
        fecha_vencimiento = lote.fecha_vencimiento.date()
        estado, dias_restantes = evaluar_vencimiento(
            fecha_vencimiento, dias_alerta
        )

        if estado != "vigente":
            resultado.append({
                "id": lote.id,
                "producto_id": lote.producto_id,
                "producto_nombre": lote.producto.nombre if lote.producto else "",
                "almacen_nombre": lote.almacen.nombre if lote.almacen else "",
                "fecha_vencimiento": fecha_vencimiento,
                "estado": estado,
                "dias_restantes": dias_restantes,
                "cantidad": lote.cantidad
            })

    return resultado


def notificar_lotes_por_vencer(dias_alerta=3, lotes=None, usuarios=None):
    """
    Crea notificaciones para lotes por vencer/vencidos
    solo para usuarios con permiso.
    """
    usuarios = usuarios or _usuarios_con_permiso_notificaciones()
    logger.info(
        "Notificaciones vencimiento | dias_alerta=%s | usuarios=%s",
        dias_alerta,
        list(usuarios.values_list("username", flat=True))
    )

    resultados = lotes_por_vencer(dias_alerta=dias_alerta, lotes=lotes)
    total = 0

    for lote_info in resultados:
        titulo = "⚠️ Lote vencido" if lote_info["estado"] == "vencido" else "⚠️ Lote por vencer"
        for usuario in usuarios:
            existe_notificacion = Notificacion.objects.filter(
                titulo=titulo,
                usuario_id=usuario.id,
                mensaje__icontains=f"LOTE:{lote_info['id']}"
            ).exists()
            if existe_notificacion:
                continue
            Notificacion.objects.create(
                tipo=Notificacion.TIPO_MENSAJE,
                titulo=titulo,
                mensaje=(
                    f"LOTE:{lote_info['id']}\n"
                    f"Producto: {lote_info['producto_nombre']}\n"
                    f"Almacén: {lote_info['almacen_nombre']}\n"
                    f"Fecha de vencimiento: {lote_info['fecha_vencimiento']}\n"
                    f"Días restantes: {lote_info['dias_restantes']}\n"
                    f"Cantidad: {lote_info['cantidad']}\n\n"
                    "Por favor, revisa el inventario."
                ),
                usuario_id=usuario.id
            )
            logger.info(
                "Notificación creada | usuario=%s | lote=%s | estado=%s | dias_restantes=%s",
                usuario.username,
                lote_info["id"],
                lote_info["estado"],
                lote_info["dias_restantes"]
            )
            total += 1

    logger.info("Notificaciones vencimiento creadas: %s", total)
    return total


# Backwards-compat (legacy product-based calls)
def productos_por_vencer(dias_alerta=3, productos=None):
    lotes = None
    if productos is not None:
        lotes = LoteInventario.objects.filter(
            producto__in=productos,
            fecha_vencimiento__isnull=False,
            status_model=LoteInventario.STATUS_MODEL_ACTIVE,
            cantidad__gt=0
        ).select_related('producto', 'almacen')
    return lotes_por_vencer(dias_alerta=dias_alerta, lotes=lotes)


def notificar_productos_por_vencer(dias_alerta=3, productos=None, usuarios=None, dias=None):
    # Soporta parámetro legacy "dias"
    if dias is not None:
        dias_alerta = dias
    lotes = None
    if productos is not None:
        lotes = LoteInventario.objects.filter(
            producto__in=productos,
            fecha_vencimiento__isnull=False,
            status_model=LoteInventario.STATUS_MODEL_ACTIVE,
            cantidad__gt=0
        ).select_related('producto', 'almacen')
    return notificar_lotes_por_vencer(dias_alerta=dias_alerta, lotes=lotes, usuarios=usuarios)
