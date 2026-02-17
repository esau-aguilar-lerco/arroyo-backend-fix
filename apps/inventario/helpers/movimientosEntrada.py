from decimal import Decimal, ROUND_HALF_UP

from apps.inventario.models import MovimientoInventario, ProductosMovimiento, LoteInventario
from apps.erp.models import incidencia as IncidenciaModel, IncidenciaLote, Almacen
from django.db import transaction


def create_movimiento_entrada(model_movimiento,productos_con_lote, user=None,ref_base="MOV-TRASP-VIT"):
    if model_movimiento.fase == MovimientoInventario.FASE_TERMINADA:
        raise ValueError("Este movimiento ya fue procesado")
    model_movimento_vir = MovimientoInventario.objects.filter(referencia=f'{ref_base}-{model_movimiento.id}').first()
    almacen_destino = model_movimiento.almacen_destino
    # Compatibilidad:
    # - Flujos antiguos ya descontaban surtidor al aprobar (tenían productosMovimiento en salida)
    # - Flujos nuevos difieren el descuento hasta esta recepción (salida sin productosMovimiento)
    deducir_surtidor_en_recepcion = (
        model_movimento_vir is not None
        and model_movimiento.movimiento == MovimientoInventario.SALIDA_TRASPASO
        and not model_movimiento.productosMovimiento.exists()
    )

    with transaction.atomic():
        model_movimiento.fase = MovimientoInventario.FASE_TERMINADA
        model_movimiento.updated_by = user
        model_movimiento.save()
        
        if model_movimento_vir is not None:
            model_movimento_vir.fase = MovimientoInventario.FASE_TERMINADA
            model_movimento_vir.updated_by = user
            model_movimento_vir.save()
            
        movimiento_entrada = MovimientoInventario.objects.filter(
        referencia=f'MOV-ENTRADA-{model_movimiento.id}'
        ).first()

        if movimiento_entrada is None:
            movimiento_entrada = MovimientoInventario.objects.create(
                almacen=model_movimiento.almacen_destino,
                almacen_destino=almacen_destino,
                tipo=MovimientoInventario.TIPO_ENTRADA,
                movimiento=MovimientoInventario.ENTRADA_TRASPASO,
                cantidad=0,
                referencia=f'MOV-ENTRADA-{model_movimiento.id}',
                created_by=user,
                nota=f"Entrada por traspaso desde {model_movimiento.almacen.nombre}",
                fase=MovimientoInventario.FASE_TERMINADA,
            )

        count_cantidad = Decimal("0.00")
        
        lotes_incidencias = []
        for detalle in productos_con_lote:
            producto = detalle['producto']
            lotes = detalle['lotes']
            
            for lote_data in lotes:
                lote_origen = lote_data['lote']
                cantidad = lote_data['cantidad']
                if not isinstance(cantidad, Decimal):
                    cantidad = Decimal(str(cantidad))
                cantidad = cantidad.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)

                # En traspasos usar el lote del almacén virtual para no tocar CEDIS
                lote = lote_origen
                if model_movimento_vir is not None:
                    # Si el frontend ya envió un lote virtual, usarlo directo.
                    if lote_origen.almacen_id == model_movimento_vir.almacen_destino_id:
                        lote = lote_origen
                    else:
                        ref_virtual = f"TRASP-{model_movimiento.id}-ORIG-{lote_origen.id}"
                        lote_virtual = LoteInventario.objects.filter(
                            almacen=model_movimento_vir.almacen_destino,
                            referencia=ref_virtual
                        ).first()
                        if lote_virtual:
                            lote = lote_virtual
                        else:
                            # Fallback para traspasos antiguos sin referencia
                            lote_virtual = LoteInventario.objects.filter(
                                almacen=model_movimento_vir.almacen_destino,
                                producto=producto,
                                cantidad__gt=0
                            ).order_by('fecha_ingreso').first()
                            if lote_virtual:
                                lote = lote_virtual

                cantidad_enviada = lote.cantidad
                if not isinstance(cantidad_enviada, Decimal):
                    cantidad_enviada = Decimal(str(cantidad_enviada))
                cantidad_enviada = cantidad_enviada.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)

                if deducir_surtidor_en_recepcion:
                    lote_origen_real = lote.lote_herencia
                    if lote_origen_real is None:
                        raise ValueError(
                            f"El lote virtual {lote.id} no tiene lote de origen para descontar en surtidor."
                        )
                    # Descontar lo enviado (no lo recibido), para que cualquier diferencia
                    # quede como incidencia y no permanezca en el surtidor.
                    ProductosMovimiento.objects.create(
                        movimiento=model_movimiento,
                        producto=producto,
                        lote=lote_origen_real,
                        cantidad=cantidad_enviada,
                        costo_unitario=lote_origen_real.costo_unitario,
                        costo_total=cantidad_enviada * lote_origen_real.costo_unitario,
                        created_by=user
                    )

                # Validar que la cantidad solicitada no exceda el lote disponible
                if cantidad_enviada < cantidad:
                    raise ValueError(
                        f"Cantidad solicitada ({cantidad}) excede disponible ({cantidad_enviada}) "
                        f"en lote {lote.id} para producto {producto.nombre}."
                    )

                # Si se recibe menos de lo enviado, lo restante va a incidencias
                diferencia = (cantidad_enviada - cantidad).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
                if diferencia > 0:
                    lotes_incidencias.append({
                        'producto': producto,
                        'cantidad': diferencia,
                        'costo_unitario': lote.costo_unitario,
                        'referencia_lote': lote,
                    })

                # Mover el lote al almacén destino.
                # Resetear cantidad a 0 para que el ProductosMovimiento (ENTRADA) la sume una sola vez.
                lote.almacen = almacen_destino
                lote.updated_by = user
                lote.cantidad = 0
                count_cantidad += cantidad
                lote.save()
                
                item_vir, created = ProductosMovimiento.objects.get_or_create(
                movimiento=movimiento_entrada,
                producto=producto,
                lote_id=lote.id,
                defaults={
                    "cantidad": cantidad,
                    "costo_unitario": lote.costo_unitario,
                    "costo_total": cantidad * lote.costo_unitario,
                    "created_by": user
                    }
                )

                if not created:
                    item_vir.cantidad += cantidad
                    if not isinstance(item_vir.cantidad, Decimal):
                        item_vir.cantidad = Decimal(str(item_vir.cantidad))
                    if not isinstance(item_vir.costo_unitario, Decimal):
                        item_vir.costo_unitario = Decimal(str(item_vir.costo_unitario))
                    item_vir.costo_total = item_vir.cantidad * item_vir.costo_unitario
                    item_vir.save()

                
        # Crear incidencia si hay lotes con diferencias
        print(lotes_incidencias)
        if lotes_incidencias:
            ALMACEN_incidencia = Almacen.objects.filter(tipo=Almacen.TIPO_INCIDENCIAS).first()
            _crear_incidencia(
                productos_incidencias=lotes_incidencias,
                almacen=ALMACEN_incidencia,
                movimiento=model_movimiento,
                user=user
            )
                
                # Aquí también podrías actualizar el inventario del producto si es necesario
        
        
        movimiento_entrada.cantidad = count_cantidad
        movimiento_entrada.save()
        
        return movimiento_entrada
    
    
def crear_lote_incidencia(almacen,producto,  cantidad, costo_unitario,  user=None,referencia = None):
    """
    Crea un nuevo lote para una incidencia
    """
    lote = LoteInventario.objects.create(
        referencia=referencia,
        producto=producto,
        almacen=almacen,
        cantidad=cantidad,
        costo_unitario=costo_unitario,
        #fecha_vencimiento=fecha_vencimiento,
        created_by=user
    )
    return lote

def _crear_incidencia(productos_incidencias, almacen, movimiento, user):
        """
        Crea una incidencia para los productos con diferencias en la entrada
        """
        #from apps.erp.models import 

        if not productos_incidencias:
            return None

        incidencia_obj = IncidenciaModel.objects.create(
            descripcion=IncidenciaModel.DEFAULT_DESCRIPCION,
            resuelta=False,
            created_by=user,
            #updated_by=user
        )

        for item in productos_incidencias:
            lote = crear_lote_incidencia(
                producto=item['producto'],
                cantidad=item['cantidad'],
                costo_unitario=item['costo_unitario'],
                almacen=almacen,
                referencia=item['referencia_lote'],
                user=user
            )
            
            IncidenciaLote.objects.create(
                incidencia=incidencia_obj,
                lote=lote,  # No hay lote asociado en este caso
                #producto=item['producto'],
                cantidad=item['cantidad'],
                atendida=False,
                created_by=user,
                updated_by=user
            )

        return incidencia_obj
