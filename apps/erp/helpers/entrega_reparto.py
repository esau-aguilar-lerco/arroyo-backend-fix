from decimal import Decimal

from django.db import models
from django.db.models import Sum

from apps.base.models import BaseModel
from apps.erp.models import Venta, VentaDetalle, incidencia, IncidenciaLote, Rutas
from apps.inventario.models import (
    EmbarqueReparto,
    LoteInventario,
    MovimientoInventario,
    ProductoEmbarque,
    ProductosMovimiento,
)


def _to_decimal(value):
    if value is None or value == "":
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def registrar_entrega_productos(venta: Venta, productos_entregados: list, usuario=None, observaciones=None):
    """
    Registra entrega en ruta, valida responsable, genera movimientos de inventario
    y levanta incidencia cuando existen devoluciones/observaciones.
    """
    if not venta.ruta:
        raise ValueError(f"La venta {venta.codigo} no tiene ruta asignada.")

    ruta = venta.ruta
    usuario_en_ruta = True
    if usuario and not usuario.is_superuser and not usuario.is_staff:
        usuario_en_ruta = Rutas.objects.filter(
            id=ruta.id,
            asignado=usuario,
            status_model=BaseModel.STATUS_MODEL_ACTIVE,
        ).exists()
        if not usuario_en_ruta:
            raise ValueError("Solo un usuario asignado a esta ruta puede confirmar entregas.")

    almacen_pedido = ruta.almacen_embarque
    almacen_tara_abierta = ruta.almacen

    if not almacen_pedido:
        raise ValueError("La ruta no tiene almacén de pedidos (embarque) configurado.")

    embarque = _resolver_embarque_para_venta(venta)
    if not embarque:
        raise ValueError(f"No se encontró un embarque relacionado para la venta {venta.codigo}.")

    detalles_venta = {
        detalle.producto_id: detalle
        for detalle in VentaDetalle.objects.select_related('producto').filter(venta=venta)
    }

    if not detalles_venta:
        raise ValueError("La venta no tiene productos para entregar.")

    observaciones_globales = (observaciones or '').strip()
    incidencia_lotes_payload = []
    incidencia_lineas = []
    productos_procesados = 0

    for item in productos_entregados:
        producto = item['producto']
        detalle = detalles_venta.get(producto.id)
        if not detalle:
            raise ValueError(f"El producto {producto.nombre} no pertenece a la venta {venta.codigo}.")
        producto_embarques = list(
            embarque.productos
            .filter(
                preventa=venta,
                producto=producto,
                tipo=ProductoEmbarque.PEDIDO,
                status_model=BaseModel.STATUS_MODEL_ACTIVE,
            )
            .order_by('id')
        )
        if not producto_embarques:
            # Fallback defensivo: buscar líneas activas en cualquier embarque activo
            # de la venta por si el vínculo de "latest" no corresponde al reparto actual.
            producto_embarques = list(
                ProductoEmbarque.objects
                .filter(
                    embarque__ventas=venta,
                    embarque__status_model=BaseModel.STATUS_MODEL_ACTIVE,
                    embarque__fase__in=[EmbarqueReparto.FASE_REPARTO] + EmbarqueReparto.fases_programado_compat(),
                    preventa=venta,
                    producto=producto,
                    tipo=ProductoEmbarque.PEDIDO,
                    status_model=BaseModel.STATUS_MODEL_ACTIVE,
                )
                .select_related('embarque')
                .order_by('-embarque_id', 'id')
            )

        # En este flujo la app envía la cantidad entregada acumulada por producto.
        # Para evitar salidas duplicadas, sólo se mueve el delta pendiente.
        cantidad_entregada_actual = _to_decimal(detalle.cantidad_entregada)
        cantidad_entregada = _to_decimal(item.get('cantidad_entregada', item.get('cantidad')))
        cantidad_devolucion = _to_decimal(item.get('devolucion', 0))
        observacion_item = (item.get('observacion') or '').strip()

        if cantidad_devolucion > 0 and not (observacion_item or observaciones_globales):
            raise ValueError(
                f"Debes indicar observación/motivo para devolución del producto {producto.nombre}."
            )

        if cantidad_entregada < 0 or cantidad_devolucion < 0:
            raise ValueError(f"Las cantidades no pueden ser negativas para {producto.nombre}.")

        if cantidad_entregada < cantidad_entregada_actual:
            raise ValueError(
                f"La cantidad entregada para {producto.nombre} no puede ser menor "
                f"a la ya registrada ({cantidad_entregada_actual})."
            )

        if (cantidad_entregada + cantidad_devolucion) > detalle.cantidad:
            raise ValueError(
                f"La suma entregada + devolución para {producto.nombre} excede la cantidad del pedido."
            )

        cantidad_entrega_delta = cantidad_entregada - cantidad_entregada_actual

        # salida por entrega al cliente
        if cantidad_entrega_delta > 0:
            if producto_embarques:
                lotes_entrega = _buscar_lotes_asignados_embarque(
                    producto_embarques=producto_embarques,
                    venta=venta,
                    cantidad_pendiente=cantidad_entrega_delta,
                )
            else:
                lotes_entrega = _buscar_lotes(
                    producto=producto,
                    almacen=almacen_pedido,
                    cantidad_pendiente=cantidad_entrega_delta,
                )
            _crear_movimiento(
                lotes=lotes_entrega,
                almacen=almacen_pedido,
                user=usuario or venta.created_by,
                venta=venta,
            )

        # devolución: traspaso desde almacén de pedidos a almacén de tara de ruta
        if cantidad_devolucion > 0:
            if not almacen_tara_abierta:
                raise ValueError("La ruta no tiene almacén de tara abierta configurado para devoluciones.")

            lotes_devolucion = _buscar_lotes(
                producto=producto,
                almacen=almacen_pedido,
                cantidad_pendiente=cantidad_devolucion,
            )
            _crear_movimiento_traspaso(
                lotes=lotes_devolucion,
                almacen_origen=almacen_pedido,
                almacen_destino=almacen_tara_abierta,
                user=usuario or venta.created_by,
                venta=venta,
            )
            for lote_item in lotes_devolucion:
                incidencia_lotes_payload.append({
                    'lote': lote_item['lote'],
                    'cantidad': lote_item['cantidad'],
                    'nota': observacion_item or observaciones_globales or f"Devolución de venta {venta.codigo}",
                })

        detalle.cantidad_entregada = cantidad_entregada
        # Un detalle se considera atendido cuando lo entregado + devuelto cubre lo solicitado.
        detalle.is_entregado = (
            detalle.is_entregado or
            ((cantidad_entregada + cantidad_devolucion) >= detalle.cantidad)
        )
        detalle.save(update_fields=['cantidad_entregada', 'is_entregado'])
        if producto_embarques:
            restante_entregado = cantidad_entregada
            for producto_embarque in producto_embarques:
                cantidad_linea = _to_decimal(producto_embarque.cantidad)
                entregado_linea = min(cantidad_linea, max(restante_entregado, Decimal('0')))
                producto_embarque.cantidad_entregada = entregado_linea
                producto_embarque.save(update_fields=['cantidad_entregada', 'updated_at'])
                restante_entregado -= entregado_linea

        if cantidad_devolucion > 0 or observacion_item:
            incidencia_lineas.append(
                f"Producto {producto.codigo or producto.id} - entregada={cantidad_entregada}, "
                f"devolucion={cantidad_devolucion}, obs={observacion_item or 'N/A'}"
            )

        productos_procesados += 1

    venta.is_entregado = not venta.detalles.filter(is_entregado=False).exists()
    if venta.is_entregado:
        venta.ya_terminada = True
    venta.save(update_fields=['is_entregado', 'ya_terminada'])

    incidencia_model = None
    if incidencia_lotes_payload or observaciones_globales:
        descripcion = observaciones_globales or incidencia.DEFAULT_DESCRIPCION
        if incidencia_lineas:
            descripcion = f"{descripcion}\n" + "\n".join(incidencia_lineas)

        incidencia_model = incidencia.objects.create(
            descripcion=descripcion,
            created_by=usuario or venta.created_by,
        )
        for lote_item in incidencia_lotes_payload:
            IncidenciaLote.objects.create(
                incidencia=incidencia_model,
                lote=lote_item['lote'],
                cantidad=lote_item['cantidad'],
                nota=lote_item.get('nota') or f"Devolución de venta {venta.codigo}",
                created_by=usuario or venta.created_by,
            )

    return {
        'venta': venta,
        'incidencia': incidencia_model,
        'productos_procesados': productos_procesados,
    }


def _buscar_lotes(producto, almacen, cantidad_pendiente):
    cantidad_pendiente = float(cantidad_pendiente)

    lote_completo = LoteInventario.objects.filter(
        producto=producto,
        almacen=almacen,
        cantidad__gte=cantidad_pendiente,
        status_model=LoteInventario.STATUS_MODEL_ACTIVE,
    ).order_by('cantidad', 'created_at').first()

    if lote_completo:
        return [{'lote': lote_completo, 'cantidad': Decimal(str(cantidad_pendiente))}]

    lotes_models = LoteInventario.objects.filter(
        producto=producto,
        almacen=almacen,
        cantidad__gt=0,
        status_model=LoteInventario.STATUS_MODEL_ACTIVE,
    ).order_by('created_at')

    lotes_a_usar = []
    cantidad_restante = cantidad_pendiente

    for lote in lotes_models:
        if cantidad_restante <= 0:
            break

        cantidad_lote = float(lote.cantidad)
        if cantidad_lote >= cantidad_restante:
            lotes_a_usar.append({'lote': lote, 'cantidad': Decimal(str(cantidad_restante))})
            cantidad_restante = 0
        else:
            lotes_a_usar.append({'lote': lote, 'cantidad': Decimal(str(cantidad_lote))})
            cantidad_restante -= cantidad_lote

    if cantidad_restante > 0:
        raise ValueError(
            f"No hay suficiente stock del producto {producto.nombre}. Faltan {cantidad_restante} unidades."
        )

    return lotes_a_usar


def _buscar_lotes_asignados_embarque(producto_embarques, venta, cantidad_pendiente):
    """
    Entrega sólo desde lotes asignados a ese producto en el embarque/venta.
    Evita que una venta consuma lotes asignados a otra.
    """
    cantidad_restante = _to_decimal(cantidad_pendiente)
    producto_embarques = list(producto_embarques or [])
    if not producto_embarques:
        raise ValueError("No se encontraron líneas de embarque para aplicar la entrega.")

    producto = producto_embarques[0].producto
    lotes_asignados = {}
    for producto_embarque in producto_embarques:
        for lp in producto_embarque.lotes.all():
            lotes_asignados[lp.lote_id] = lotes_asignados.get(lp.lote_id, Decimal('0')) + _to_decimal(lp.cantidad)

    lotes_asignados_ids = list(lotes_asignados.keys())

    if not lotes_asignados_ids:
        return _buscar_lotes(
            producto=producto,
            almacen=venta.ruta.almacen_embarque,
            cantidad_pendiente=cantidad_restante,
        )

    lotes_map = {
        lote.id: lote
        for lote in LoteInventario.objects.filter(
            id__in=lotes_asignados_ids,
            status_model=BaseModel.STATUS_MODEL_ACTIVE,
        )
    }

    entregado_por_lote = {
        row['lote_id']: _to_decimal(row['total'] or 0)
        for row in (
            ProductosMovimiento.objects
            .filter(
                movimiento__referencia=f"VENTA-{venta.id}",
                movimiento__movimiento=MovimientoInventario.SALIDA_VENTA,
                movimiento__status_model=BaseModel.STATUS_MODEL_ACTIVE,
                status_model=BaseModel.STATUS_MODEL_ACTIVE,
                producto_id=producto.id,
                lote_id__in=lotes_asignados_ids,
            )
            .values('lote_id')
            .annotate(total=Sum('cantidad'))
        )
    }

    lotes_a_usar = []
    for lote_id in sorted(lotes_asignados_ids):
        if cantidad_restante <= 0:
            break

        lote = lotes_map.get(lote_id)
        if not lote:
            continue

        cantidad_asignada = _to_decimal(lotes_asignados.get(lote_id, 0))
        cantidad_ya_entregada_lote = entregado_por_lote.get(lote_id, Decimal('0'))
        cupo_lote = cantidad_asignada - cantidad_ya_entregada_lote
        if cupo_lote <= 0:
            continue

        disponible_real_lote = _to_decimal(lote.cantidad)
        cantidad_usar = min(cantidad_restante, cupo_lote, disponible_real_lote)
        if cantidad_usar <= 0:
            continue

        lotes_a_usar.append({'lote': lote, 'cantidad': cantidad_usar})
        cantidad_restante -= cantidad_usar

    if cantidad_restante > 0:
        raise ValueError(
            f"No hay suficiente stock del producto {producto.nombre}. "
            f"Faltan {float(cantidad_restante)} unidades."
        )

    return lotes_a_usar


def _resolver_embarque_para_venta(venta):
    """
    Prioriza embarque activo en REPARTO de la venta; si no existe, usa PROGRAMADO.
    Como fallback final usa el último embarque asociado.
    """
    fases_programado = EmbarqueReparto.fases_programado_compat()
    prioridad_fase = models.Case(
        models.When(fase=EmbarqueReparto.FASE_REPARTO, then=models.Value(0)),
        models.When(fase__in=fases_programado, then=models.Value(1)),
        default=models.Value(9),
        output_field=models.IntegerField(),
    )

    embarque_activo = (
        EmbarqueReparto.objects
        .filter(
            ventas=venta,
            status_model=BaseModel.STATUS_MODEL_ACTIVE,
        )
        .filter(
            models.Q(fase=EmbarqueReparto.FASE_REPARTO) |
            models.Q(fase__in=fases_programado)
        )
        .prefetch_related('productos__lotes')
        .annotate(_prioridad_fase=prioridad_fase)
        .order_by('_prioridad_fase', '-id')
        .first()
    )
    if embarque_activo:
        return embarque_activo

    return (
        EmbarqueReparto.objects
        .filter(ventas=venta, status_model=BaseModel.STATUS_MODEL_ACTIVE)
        .prefetch_related('productos__lotes')
        .order_by('-created_at', '-id')
        .first()
    )


def _crear_movimiento(lotes, almacen, user, venta):
    cantidad_total = sum([item['cantidad'] for item in lotes], Decimal('0'))
    movimiento = MovimientoInventario.objects.create(
        almacen=almacen,
        tipo=MovimientoInventario.TIPO_SALIDA,
        movimiento=MovimientoInventario.SALIDA_VENTA,
        costo_unitario=0,
        cantidad=cantidad_total,
        referencia=f"VENTA-{venta.id}",
        fase=MovimientoInventario.FASE_TERMINADA,
        created_by=user,
    )
    for item in lotes:
        ProductosMovimiento.objects.create(
            movimiento_id=movimiento.id,
            producto_id=item['lote'].producto.id,
            lote_id=item['lote'].id,
            cantidad=item['cantidad'],
            costo_unitario=item['lote'].costo_unitario,
            costo_total=item['cantidad'] * item['lote'].costo_unitario,
            created_by=user,
        )
    return movimiento


def _crear_movimiento_traspaso(lotes, almacen_origen, almacen_destino, user, venta):
    cantidad_total = sum([item['cantidad'] for item in lotes], Decimal('0'))
    movimiento_salida = MovimientoInventario.objects.create(
        almacen=almacen_origen,
        tipo=MovimientoInventario.TIPO_SALIDA,
        movimiento=MovimientoInventario.SALIDA_TRASPASO,
        costo_unitario=0,
        cantidad=cantidad_total,
        referencia=f"TRASPASO-SALIDA-RETORNO-TARA-{venta.id}",
        fase=MovimientoInventario.FASE_TERMINADA,
        created_by=user,
    )

    movimiento_entrada = MovimientoInventario.objects.create(
        almacen=almacen_destino,
        tipo=MovimientoInventario.TIPO_ENTRADA,
        movimiento=MovimientoInventario.ENTRADA_TRASPASO,
        costo_unitario=0,
        cantidad=cantidad_total,
        referencia=f"TRASPASO-ENTRADA-RETORNO-TARA-{venta.id}",
        fase=MovimientoInventario.FASE_TERMINADA,
        created_by=user,
    )

    for item in lotes:
        ProductosMovimiento.objects.create(
            movimiento_id=movimiento_salida.id,
            producto_id=item['lote'].producto.id,
            lote_id=item['lote'].id,
            cantidad=item['cantidad'],
            costo_unitario=item['lote'].costo_unitario,
            costo_total=item['cantidad'] * item['lote'].costo_unitario,
            created_by=user,
        )
        ProductosMovimiento.objects.create(
            movimiento_id=movimiento_entrada.id,
            producto_id=item['lote'].producto.id,
            lote_id=item['lote'].id,
            cantidad=item['cantidad'],
            costo_unitario=item['lote'].costo_unitario,
            costo_total=item['cantidad'] * item['lote'].costo_unitario,
            created_by=user,
        )

    return movimiento_salida, movimiento_entrada
