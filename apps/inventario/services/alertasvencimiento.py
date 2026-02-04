from datetime import date, timedelta
from django.db.models import Q
from apps.inventario.models import Producto
from apps.erp.models import Notificacion
from apps.usuarios.models import Usuario


def evaluar_vencimiento(fecha_vencimiento, dias_alerta=3):
    dias_restantes = (fecha_vencimiento - date.today()).days

    if dias_restantes < 0:
        return "vencido", dias_restantes

    if dias_restantes <= dias_alerta:
        return "por_vencer", dias_restantes

    return "vigente", dias_restantes


def productos_por_vencer(dias_alerta=3):
    productos = Producto.objects.exclude(horas_caducidad=None)

    resultado = []

    # 🔔 usuario que recibirá la notificación (MISMO PATRÓN QUE YA USAS)
    usuario_compras = Usuario.objects.filter(
        is_active=True
    ).filter(
        Q(groups__name__in=['Compras']) |
        Q(user_permissions__codename='can_create_orden_compra')
    ).first()

    user_id = usuario_compras.id if usuario_compras else 1

    for producto in productos:
        fecha_vencimiento = (
            producto.created_at + timedelta(hours=producto.horas_caducidad)
        ).date()

        estado, dias_restantes = evaluar_vencimiento(
            fecha_vencimiento, dias_alerta
        )

        if estado != "vigente":
            # 📌 evitar notificaciones duplicadas
            existe_notificacion = Notificacion.objects.filter(
                titulo="⚠️ Producto por vencer",
                usuario_id=user_id,
                mensaje__icontains=f"ID:{producto.id}"
            ).exists()

            if estado == "por_vencer" and not existe_notificacion:
                Notificacion.objects.create(
                    tipo=Notificacion.TIPO_MENSAJE,
                    titulo="⚠️ Producto por vencer",
                    mensaje=(
                        f"ID:{producto.id}\n"
                        f"Producto: {producto.nombre}\n"
                        f"Fecha de vencimiento: {fecha_vencimiento}\n"
                        f"Días restantes: {dias_restantes}\n\n"
                        "Por favor, revisa el inventario."
                    ),
                    usuario_id=user_id
                )

            resultado.append({
                "id": producto.id,
                "nombre": producto.nombre,
                "fecha_vencimiento": fecha_vencimiento,
                "estado": estado,
                "dias_restantes": dias_restantes,
            })

    return resultado
