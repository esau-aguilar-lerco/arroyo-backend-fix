from apps.erp.models import Almacen,Venta, VentaDetalle,Rutas
from apps.inventario.models import EmbarqueReparto, LoteInventario, MovimientoInventario, ProductosMovimiento
from decimal import Decimal


def registrar_entrega_productos(venta: Venta, productos_entregados: list):
    detalles_venta = VentaDetalle.objects.filter(venta=venta)
    ruta = venta.ruta
    almacen_pedido = ruta.almacen_embarque
    alamcen_tara_abierta = ruta.almacen
    
    # Buscar el embarque que contiene esta venta y está en fase REPARTO
    try:
        embarque = EmbarqueReparto.objects.get(
            ventas=venta,
            #fase=EmbarqueReparto.FASE_REPARTO
        )
    except EmbarqueReparto.DoesNotExist:
        raise ValueError(f"No se encontró un embarque en reparto para la venta {venta.codigo}.")
    except EmbarqueReparto.MultipleObjectsReturned:
        # Si hay múltiples, tomar el más reciente
        embarque = EmbarqueReparto.objects.filter(
            ventas=venta,
            #fase=EmbarqueReparto.FASE_REPARTO
        ).order_by('-created_at').first()
    #print("🚧 Función registrar_entrega_productos en desarrollo...")
    #print(embarque)    
    #raise ValueError("Función en desarrollo, no implementada completamente.")

    movimiento_model = embarque.movimiento_inventario_pedidos_entrada
    #productos_movimiento = movimiento_model.productosMovimiento.all()
    #print("🚧 Función registrar_entrega_productos en desarrollo...")
    #print(productos_movimiento)
    #raise NotImplementedError("Función en desarrollo, no implementada completamente.")
    for item in productos_entregados:
        producto_model = item['producto']
        cantidad = float(item['cantidad'])
        productos_entregados = []
        
        try:
            detalle = detalles_venta.get(producto=producto_model)
            if cantidad > detalle.cantidad:
                raise ValueError(f"La cantidad entregada para el producto {producto_model.nombre} excede la cantidad en la venta.")
            elif cantidad < float(detalle.cantidad):
                pass 
                ##mover productos a tara abierta del almacen de pedidos
                #lotes_a_usar = _buscar_lotes(
                #    producto=producto_model,
                #    almacen=almacen_pedido,
                #    cantidad_pendiente=cantidad
                #)
                #lotes_descontados = _descontar_lotes(lotes_a_usar)
                #dif = float(detalle.cantidad) - cantidad
                #
                #for lote_item in lotes_descontados:
                #    if dif == float(lote_item.cantidad):
                #        #Mover lote completo a tara abierta
                #        movimiento_salida = _crear_movimiento_traspaso(
                #            lotes=[lote_item],
                #            almacen_origen=almacen_pedido,
                #            almacen_destino=alamcen_tara_abierta,
                #            user=venta.created_by,
                #            venta=venta
                #        )
                #        
                #        lote_item.almacen = alamcen_tara_abierta
                #        lote_item.save()
                        
                
            if cantidad == detalle.cantidad:
                #Proceder con la entrega normal
                
            
                lotes_a_usar = _buscar_lotes(
                    producto=producto_model,
                    almacen=almacen_pedido,
                    cantidad_pendiente=cantidad
                )
                lotes_descontados = _descontar_lotes(lotes_a_usar)
                movimiento_salida = _crear_movimiento(
                    lotes=lotes_a_usar,
                    almacen=almacen_pedido,
                    user=venta.created_by,
                    venta=venta
                )
            
                detalle.is_entregado = True
            
            detalle.cantidad_entregada = cantidad
            detalle.save()
            
            
        except VentaDetalle.DoesNotExist:
            raise ValueError(f"El producto {producto_model.nombre} no pertenece a la venta {venta.codigo}.")
    
    #TRAER LOS PRODUCTOS NO ENTREGADOS 
    if detalles_venta.filter(is_entregado=False).exists():
        venta.is_entregado = False
        venta.save()
    else:
        venta.is_entregado = True
        venta.ya_terminada = True
        venta.save()
    return venta
    


def _buscar_lotes(producto, almacen, cantidad_pendiente):
    """
    Busca lotes por producto que sumados den la cantidad pendiente.
    Primero intenta encontrar un lote que cubra la cantidad completa,
    si no existe, usa FIFO combinando lotes.
    """
    
    
    cantidad_pendiente = float(cantidad_pendiente)
    
    # Primero buscar un lote que tenga la cantidad exacta o mayor (preferir exacto)
    lote_completo = LoteInventario.objects.filter(
        producto=producto,
        almacen=almacen,
        cantidad__gte=cantidad_pendiente,
        status_model=LoteInventario.STATUS_MODEL_ACTIVE
    ).order_by('cantidad', 'created_at').first()  # Ordenar por cantidad para preferir el más cercano
    
    if lote_completo:
        # Encontramos un lote que cubre todo
        return [{
            'lote': lote_completo,
            'cantidad': cantidad_pendiente
        }]
    
    # Si no hay un lote completo, usar FIFO combinando lotes
    lotes_models = LoteInventario.objects.filter(
        producto=producto,
        almacen=almacen,
        cantidad__gt=0,
        status_model=LoteInventario.STATUS_MODEL_ACTIVE
    ).order_by('created_at')
    
    lotes_a_usar = []
    cantidad_restante = cantidad_pendiente
    
    for lote in lotes_models:
        if cantidad_restante <= 0:
            break
            
        cantidad_lote = float(lote.cantidad)
        if cantidad_lote >= cantidad_restante:
            # Este lote cubre todo lo que falta
            lotes_a_usar.append({
                'lote': lote,
                'cantidad': cantidad_restante
            })
            cantidad_restante = 0
        else:
            # Usar todo el lote y seguir buscando
            lotes_a_usar.append({
                'lote': lote,
                'cantidad': cantidad_lote
            })
            cantidad_restante -= cantidad_lote
    
    if cantidad_restante > 0:
        raise ValueError(f"No hay suficiente stock del producto {producto.nombre}. Faltan {cantidad_restante} unidades.")
    
    return lotes_a_usar


def _crear_movimiento(lotes, almacen,user,venta):
    cantidad_total = sum([item['cantidad'] for item in lotes])
    total_movimiento = 0
    data = {
        'almacen': almacen,
        #'almacen_destino_id': almacen_destino_id,
        'tipo': MovimientoInventario.TIPO_SALIDA,
        'movimiento': MovimientoInventario.SALIDA_VENTA,
        'costo_unitario': total_movimiento,
        "cantidad": Decimal(cantidad_total),
        'referencia': f"VENTA-{venta.id}",
        'fase': MovimientoInventario.FASE_TERMINADA,
        'created_by': user
    }
    data['movimiento'] = MovimientoInventario.SALIDA_VENTA
    movimiento = MovimientoInventario.objects.create(**data)
    #help_actualizar_lotes(lotes_afectados,lotes_ids_en_0,almacen_destino_id,user_id)
    #CREAMOS LOS PRODUCTOS MOVIMIENTO, 
    for item in lotes:
        data_mov = {
            'movimiento_id': movimiento.id,
            'producto_id': item['lote'].producto.id,
            'lote_id': item['lote'].id,
            'cantidad': Decimal(item['cantidad']),
            'costo_unitario': item['lote'].costo_unitario,
            'costo_total': Decimal(item['cantidad']) * item['lote'].costo_unitario,
            'created_by': user
        }
        #Movimiento de salida
        ProductosMovimiento.objects.create(**data_mov)
        
    return movimiento



def _crear_movimiento_traspaso(lotes, almacen_origen, almacen_destino, user, venta):
    cantidad_total = sum([item['cantidad'] for item in lotes])
    total_movimiento = 0
    #Movimiento de salida
    data_salida = {
        'almacen': almacen_origen,
        'tipo': MovimientoInventario.TIPO_SALIDA,
        'movimiento': MovimientoInventario.SALIDA_TRASPASO,
        'costo_unitario': total_movimiento,
        "cantidad": Decimal(cantidad_total),
        'referencia': f"TRASPASO-SALIDA-RETORNO-TARA-{venta.id}",
        'fase': MovimientoInventario.FASE_TERMINADA,
        'created_by': user
    }
    movimiento_salida = MovimientoInventario.objects.create(**data_salida)
    
    #Movimiento de entrada
    data_entrada = {
        'almacen': almacen_destino,
        'tipo': MovimientoInventario.TIPO_ENTRADA,
        'movimiento': MovimientoInventario.ENTRADA_TRASPASO,
        'costo_unitario': total_movimiento,
        "cantidad": Decimal(cantidad_total),
        'referencia': f"TRASPASO-ENTRADA-RETORNO-TARA-{venta.id}",
        'fase': MovimientoInventario.FASE_TERMINADA,
        'created_by': user
    }
    movimiento_entrada = MovimientoInventario.objects.create(**data_entrada)
    
    #CREAMOS LOS PRODUCTOS MOVIMIENTO, 
    for item in lotes:
        data_mov_salida = {
            'movimiento_id': movimiento_salida.id,
            'producto_id': item['lote'].producto.id,
            'lote_id': item['lote'].id,
            'cantidad': Decimal(item['cantidad']),
            'costo_unitario': item['lote'].costo_unitario,
            'costo_total': Decimal(item['cantidad']) * item['lote'].costo_unitario,
            'created_by': user
        }
        #Movimiento de salida
        ProductosMovimiento.objects.create(**data_mov_salida)
        
        data_mov_entrada = {
            'movimiento_id': movimiento_entrada.id,
            'producto_id': item['lote'].producto.id,
            'lote_id': item['lote'].id,
            'cantidad': Decimal(item['cantidad']),
            'costo_unitario': item['lote'].costo_unitario,
            'costo_total': Decimal(item['cantidad']) * item['lote'].costo_unitario,
            'created_by': user
        }
        #Movimiento de entrada
        ProductosMovimiento.objects.create(**data_mov_entrada)
def _descontar_lotes(lotes):
    for item in lotes:
        lote = item['lote']
        cantidad = float(item['cantidad'])
        descuento = float(lote.cantidad) - cantidad
        lote.cantidad = Decimal(descuento)
        lote.save()
        item['lote'] = lote
        
    return lotes