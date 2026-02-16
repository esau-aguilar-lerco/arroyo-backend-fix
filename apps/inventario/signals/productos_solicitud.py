from apps.inventario.models import ProductosSolicitud, SolicitudTraspaso
from apps.erp.models import Notificacion
from apps.usuarios.models import Usuario
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=ProductosSolicitud, dispatch_uid='inventario_productos_solicitud_guardado')
def productos_solicitud_guardado(sender, instance, created, **kwargs):
    if created:
        #buscae el usuario que tenga el permiso de compras o orden de compra create o el grupo de compras
        usuario_compras = Usuario.objects.filter(
            is_active=True
        ).filter(
            Q(groups__name__in=['Compras']) | Q(user_permissions__codename='can_create_orden_compra') | Q(user_permissions__codename='can_create_orden_compra')
        ).first()
        if not usuario_compras:
            # Si no hay usuario con permisos, se puede manejar la lógica correspondiente
            user_id = 1 
        else:
            user_id = usuario_compras.id
        
        Notificacion.objects.create(
            tipo=Notificacion.TIPO_MENSAJE,
            titulo="¡Nueva Solicitud de Producto!",
            mensaje=(
            f"Se ha solicitado el producto '{instance.producto.nombre}' "
            f"(Cantidad: {instance.cantidad}). Por {instance.created_by.full_name()}.\n"
            f"📦 Almacén: {instance.almacen.nombre}\n"
            "Por favor, revisa y gestiona la solicitud en el sistema."
            ),
            usuario_id=user_id
        )
        
@receiver(post_save, sender=SolicitudTraspaso, dispatch_uid='inventario_solicitud_traspaso_guardado')
def solicitud_traspaso_guardado(sender, instance, created, **kwargs):
    if created:
        encargado = instance.almacen_surtidor.encargado
        Notificacion.objects.create(
            tipo=Notificacion.TIPO_MENSAJE,
            titulo="¡Nueva Solicitud de Traspaso!",
            mensaje=(
            f"Se ha creado una solicitud de traspaso desde el almacén "
            f"'{instance.almacen_surtidor.nombre}' al almacén '{instance.almacen_solicitante.nombre}'.\n"
            f"Por favor, revisa y gestiona la solicitud en el sistema."
            ),
            usuario_id=encargado.id if encargado else 1
        )
    else:
        if instance.estado == SolicitudTraspaso.APROBADO:
            encargado_destino = instance.almacen_solicitante.encargado
            encargado_origen = instance.created_by
            mensaje = (
                f"Solicitud #{instance.id} aprobada. "
                f"Traspaso desde '{instance.almacen_surtidor.nombre}' "
                f"al almacén '{instance.almacen_solicitante.nombre}'.\n"
                f"Por favor, prepara la recepción de los productos en el sistema."
            )
            usuario_id = encargado_destino.id if encargado_destino else 1

            # Evita duplicados por múltiples saves sobre la misma solicitud aprobada.
            ya_existe = Notificacion.objects.filter(
                tipo=Notificacion.TIPO_MENSAJE,
                titulo="¡Solicitud de Traspaso Aprobada!",
                mensaje=mensaje,
                usuario_id=usuario_id,
                status_model=Notificacion.STATUS_MODEL_ACTIVE
            ).exists()

            if not ya_existe:
                Notificacion.objects.create(
                    tipo=Notificacion.TIPO_MENSAJE,
                    titulo="¡Solicitud de Traspaso Aprobada!",
                    mensaje=mensaje,
                    usuario_id=usuario_id
                )
        elif instance.estado == SolicitudTraspaso.RECHAZADO:
            #crear la solicitud a cedis 
            from apps.inventario.models import Almacen
            from apps.inventario.models import SolicitudTraspasoDetalle
            cedis = Almacen.objects.filter(is_cedis=True).first()
            model = SolicitudTraspaso.objects.create(
                #referencia=f"TRASPASO-CEDIS-{instance.id}",
                almacen_solicitante=instance.almacen_solicitante,
                almacen_surtidor_id=cedis.id if cedis else 1,  # Asumiendo que el ID 1 es el de CEDIS
                estado=SolicitudTraspaso.PENDIENTE,
                created_by=instance.created_by
            )
            productos_detalle = instance.detalles.all()
            for producto in productos_detalle:
                SolicitudTraspasoDetalle.objects.create(
                    solicitud=model,
                    producto=producto.producto,
                    cantidad=producto.cantidad,
                )
            encargado_origen = instance.created_by
            Notificacion.objects.create(
                tipo=Notificacion.TIPO_MENSAJE,
                titulo="¡Solicitud de Traspaso Rechazada!",
                mensaje=(
                f"La solicitud de traspaso desde el almacén "
                f"'{instance.almacen_surtidor.nombre}' al almacén '{instance.almacen_solicitante.nombre}' ha sido rechazada.\n"
                f"Por favor, revisa los detalles en el sistema."
                ),
                usuario_id=encargado_origen.id if encargado_origen else 1
            )
            
            #Notificacion.objects.create(
            #    tipo=Notificacion.TIPO_MENSAJE,
            #    titulo="¡Solicitud de Traspaso a CEDIS!",
            #    mensaje=(
            #    f"La solicitud de traspaso desde el almacén "
            #    f"'{instance.almacen_surtidor.nombre}' al almacén '{instance.almacen_solicitante.nombre}' ha sido enviada a CEDIS.\n"
            #    f"Por favor, revisa los detalles en el sistema."
            #    ),
            #    usuario_id=encargado_origen.id if encargado_origen else 1
            #)
            
