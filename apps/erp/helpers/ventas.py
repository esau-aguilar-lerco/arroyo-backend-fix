from apps.erp.models import Venta, VentaDetalle
from apps.inventario.models import LoteInventario, MovimientoInventario, ProductosMovimiento, Almacen,ProductosSolicitud
from decimal import Decimal
from django.db.models import Sum, F
from django.db import transaction

def main_crearmovomientos_venta(model_venta=None, data_detalles=None, user=None):
    almacen = model_venta.almacen
    almacen_destino = help_buscar_almacen_destino(model_venta=model_venta)

    # Agrupar productos
    items_productos = []
    for detalle in data_detalles:
        producto = detalle.get('producto')
        cantidad = detalle.get('cantidad', 0)
        precio_unitario = detalle.get('precio_unitario', 0)

        if producto:
            existente = next(
                (item for item in items_productos if item['producto_id'] == producto.id),
                None
            )
            if existente:
                existente['cantidad'] += cantidad
            else:
                items_productos.append({
                    'producto_id': producto.id,
                    'cantidad': cantidad,
                    'precio_unitario': precio_unitario,
                })

    FASE = model_venta.fase
    productos_sin_stock = []
    productos_con_stock = []

    # Validar stock
    for item in items_productos:
        producto = item['producto_id']
        cantidad_requerida = item['cantidad']

        cantidad_producto = LoteInventario.objects.filter(
            producto_id=producto,
            cantidad__gt=0,
            almacen=almacen
        ).aggregate(total_stock=Sum('cantidad'))

        stock_disponible = cantidad_producto['total_stock'] or 0
        diferencia = float(stock_disponible) - float(cantidad_requerida)

        if diferencia >= 0:
            productos_con_stock.append(item)
        else:
            productos_sin_stock.append({
                'producto_id': producto,
                'cantidad_requerida': cantidad_requerida,
                'cantidad_disponible': stock_disponible,
                'faltante': abs(diferencia)
            })

    # 🚫 PREVENTA: NO tocar inventario
    if FASE == Venta.FASE_PRE_VENTA:
        if productos_sin_stock:
            model_venta.falta_inventario = True
            model_venta.save(update_fields=['falta_inventario'])

            for producto in productos_sin_stock:
                ProductosSolicitud.objects.create(
                    producto_id=producto['producto_id'],
                    cantidad=producto['faltante'],
                    almacen_id=almacen.id,
                    motivo=ProductosSolicitud.MOTIVO_PREVENTA,
                    created_by_id=user.id if user else None
                )
        return  # ⬅️ salida temprana

    # ✅ SOLO COMANDA / TERMINADA afectan inventario
    if productos_con_stock:
        lotes_afectados, lotes_completos_cero = afectar_lotes_inventario_venta_f_expressions(
            dict_productos=productos_con_stock,
            almacen=almacen,
            user_id=user.id if user else None,
            fase=FASE
        )

        crear_movimiento_inventario_venta(
            venta_id=model_venta.id,
            lotes_ids_en_0=lotes_completos_cero,
            lotes_afectados=lotes_afectados,
            user_id=user.id if user else None,
            fase=FASE,
            almacen_destino_id=almacen_destino.id if almacen_destino else None,
            almacen_origen_id=almacen.id
        )

       
            
        

@transaction.atomic  
def afectar_lotes_inventario_venta_f_expressions(dict_productos=None, almacen=None, user_id=None,fase =Venta.FASE_PRE_VENTA):
    """
    Versión con F() expressions - actualiza directamente en DB sin cargar en memoria
    """
    if not dict_productos:
        return [], []
        
    lotes_afectados = []
    lotes_completos_cero = []
    
    for item in dict_productos:
        producto_id = item['producto_id']
        cantidad_requerida = Decimal(str(item['cantidad']))
        cantidad_restante = cantidad_requerida
        
        # Obtener lotes ordenados por FIFO con select_for_update para evitar condiciones de carrera
        lotes = (LoteInventario.objects
                .select_for_update()
                .filter(producto_id=producto_id, cantidad__gt=0, almacen=almacen)
                .order_by('fecha_ingreso'))
        
        for lote in lotes:
            if cantidad_restante <= 0:
                break
                
            # Obtener cantidad actual del lote
            cantidad_disponible = lote.cantidad
            
            if cantidad_disponible <= 0:
                continue
                
            # Calcular cuánto tomar
            cantidad_a_tomar = min(cantidad_restante, cantidad_disponible)
            #print(f"cantidad_a_tomar: {cantidad_a_tomar} de lote {lote.id} (disponible: {cantidad_disponible})")
            nueva_cantidad = cantidad_disponible - cantidad_a_tomar
            #print(f"nueva_cantidad: {nueva_cantidad}")
            
            # Verificar si el lote quedará en cero
            if nueva_cantidad == 0 :#and fase == Venta.FASE_PRE_VENTA:
                # Para lotes que quedan en cero: moverlos al almacén HELP sin afectar cantidad
                lote.status_model = LoteInventario.STATUS_MODEL_ACTIVE
                lote.updated_by_id = user_id
                lote.cantidad = lote.cantidad - cantidad_a_tomar  # Esto dejará la cantidad en 0
                lote.save(update_fields=['status_model', 'updated_by_id', 'cantidad'])
                lotes_completos_cero.append(lote.id)
                #print(f"[LOTE CERO] Lote {lote.id}: se moverá completo al HELP CEDIS")
            else:
                #pass
                #print("ENTRO A REDUCIR CANTIDAD")
                # Para lotes que NO quedan en cero: reducir cantidad normalmente
                filas_actualizadas = LoteInventario.objects.filter(
                    id=lote.id,
                    cantidad__gte=cantidad_a_tomar  # Verificar que aún tenga suficiente
                ).update(
                    cantidad=F('cantidad') - cantidad_a_tomar,
                    updated_by_id=user_id
                )
            
                if filas_actualizadas == 0:
                    print(f"[ERROR] Lote {lote.id}: no se pudo actualizar (posible concurrencia)")
                    continue
                    
                #print(f"[LOTE PARCIAL] Lote {lote.id}: -{cantidad_a_tomar}, queda: {nueva_cantidad}")
            
            # Registrar el lote afectado
            lotes_afectados.append({
                'lote_id': lote.id,
                'cantidad_tomar': cantidad_a_tomar,
                'producto_id': producto_id,
                'precio_unitario': item['precio_unitario']
            })
            
            cantidad_restante -= cantidad_a_tomar
        
        # Verificar si se pudo cubrir toda la cantidad requerida
        if cantidad_restante > 0:
            print(f"[ADVERTENCIA] Producto {producto_id}: faltan {cantidad_restante} unidades")
    #print(f"[HELP VENTAS] Lotes afectados: {lotes_afectados}")
    #print(f"[HELP VENTAS] Lotes completos en cero: {lotes_completos_cero}")
    return lotes_afectados, lotes_completos_cero


@transaction.atomic
def crear_movimiento_inventario_venta(venta_id=None,lotes_ids_en_0 = None, lotes_afectados=None, user_id=None, fase=Venta.FASE_PRE_VENTA,almacen_destino_id=None,almacen_origen_id=None):
    """
    Crea registros de movimiento de inventario al registrar una venta.
    """
    total_movimiento = sum([item['cantidad_tomar'] * item['precio_unitario'] for item in lotes_afectados])
    cantidad_total = sum([item['cantidad_tomar'] for item in lotes_afectados])
    data = {
        'almacen_id': almacen_origen_id,
        'almacen_destino_id': almacen_destino_id,
        'tipo': MovimientoInventario.TIPO_SALIDA,
        'movimiento': MovimientoInventario.SALIDA_TRASPASO_VIRTUAL,
        'costo_unitario': total_movimiento,
        "cantidad": cantidad_total,
        'referencia': f"VENTA-{venta_id}",
        'fase': MovimientoInventario.FASE_TERMINADA,
        'created_by_id': user_id
    }
    print(f"[HELP VENTAS] Creando movimiento de inventario para venta {venta_id} con fase {fase}")
    #print(f"[HELP VENTAS] Creando movimiento de inventario para venta {venta_id} con fase {fase}")
    match fase:
        #SI ES PREVENTA, ESTA SE VA AL ALMACEN HELP CEDIS
        case Venta.FASE_PRE_VENTA :
            #print(f"[HELP VENTAS] Creando movimiento de inventario para preventa/venta-comanda {venta_id}")
            #creamos el movimiento de salida del almacen origen
            #movimiento = MovimientoInventario.objects.create(**data)
            #creamos el movimiento de entrada al almacen help cedis
            data['tipo'] = MovimientoInventario.TIPO_ENTRADA
            data['movimiento'] = MovimientoInventario.ENTRADA_TRASPASO_VIRTUAL
            movimiento_entrada = MovimientoInventario.objects.create(**data)
            help_actualizar_lotes(lotes_afectados,lotes_ids_en_0,almacen_destino_id,user_id)
            #CREAMOS LOS PRODUCTOS MOVIMIENTO, 
            for item in lotes_afectados:
                data_mov = {
                    'movimiento_id': movimiento_entrada.id,
                    'producto_id': item['producto_id'],
                    'lote_id': item['lote_id'],
                    'cantidad': item['cantidad_tomar'],
                    'costo_unitario': item['precio_unitario'],
                    'costo_total': item['cantidad_tomar'] * item['precio_unitario'],
                    'created_by_id': user_id
                }
                #Movimiento de salida
                #ProductosMovimiento.objects.create(**data_mov)
                data_mov['movimiento_id'] = movimiento_entrada.id
                #Movimiento de entrada
                ProductosMovimiento.objects.create(**data_mov)
        
                
        case Venta.FASE_TERMINADA:
            #SI ES TERMINADA, SOLO CREAMOS EL MOVIMIENTO DE SALIDA
            print(f"[HELP VENTAS] Creando movimiento de inventario para venta terminada {venta_id}")
            data['almacen_destino_id'] = None
            data['movimiento'] = MovimientoInventario.SALIDA_VENTA
            movimiento = MovimientoInventario.objects.create(**data)
            #help_actualizar_lotes(lotes_afectados,lotes_ids_en_0,almacen_destino_id,user_id)
            #CREAMOS LOS PRODUCTOS MOVIMIENTO, 
            for item in lotes_afectados:
                data_mov = {
                    'movimiento_id': movimiento.id,
                    'producto_id': item['producto_id'],
                    'lote_id': item['lote_id'],
                    'cantidad': item['cantidad_tomar'],
                    'costo_unitario': item['precio_unitario'],
                    'costo_total': item['cantidad_tomar'] * item['precio_unitario'],
                    'created_by_id': user_id
                }
                #Movimiento de salida
                ProductosMovimiento.objects.create(**data_mov)
            pass
        case Venta.FASE_VENTA_COMANDA:
            data['almacen_destino_id'] = None
            data['movimiento'] = MovimientoInventario.SALIDA_VENTA
            movimiento = MovimientoInventario.objects.create(**data)
            #help_actualizar_lotes(lotes_afectados,lotes_ids_en_0,almacen_destino_id,user_id)
            #CREAMOS LOS PRODUCTOS MOVIMIENTO, 
            for item in lotes_afectados:
                data_mov = {
                    'movimiento_id': movimiento.id,
                    'producto_id': item['producto_id'],
                    'lote_id': item['lote_id'],
                    'cantidad': item['cantidad_tomar'],
                    'costo_unitario': item['precio_unitario'],
                    'costo_total': item['cantidad_tomar'] * item['precio_unitario'],
                    'created_by_id': user_id
                }
                #Movimiento de salida
                ProductosMovimiento.objects.create(**data_mov)
                
        case _:
            pass
    

def help_actualizar_lotes(lotes_afectados,lotes_ids_en_0,almacen_destino_id,user_id):
    '''
    Función auxiliar para actualizar los lotes en el almacén. crear nuevo o moverlo de ubicación.
    '''
    
    #CREAMOS LOS PRODUCTOS MOVIMIENTO, 
    for item in lotes_afectados:
        if item['lote_id'] not in lotes_ids_en_0:
            lote_con_stok = LoteInventario.objects.filter(id=item['lote_id'])
            new_lote = lote_con_stok.first()
            #ACTUALIZAMOS EL LOTE QUE NO SE FUE EN 0, ALMACEN HELP CEDIS
            new_lote.pk = None  # Esto crea una copia
            new_lote.almacen_id = almacen_destino_id
            new_lote.cantidad = item['cantidad_tomar']
            new_lote.updated_by_id = user_id
            new_lote.ubicacion = None
            new_lote.status_model = LoteInventario.STATUS_MODEL_ACTIVE
            new_lote.save()
    #ACTUALIZAMOS LOS LOTES QUE SE FUERON EN 0, A ACTIVE EN EL ALMACEN HELP CEDIS
    LoteInventario.objects.filter(id__in=lotes_ids_en_0).update(status_model=LoteInventario.STATUS_MODEL_ACTIVE, almacen_id=almacen_destino_id, ubicacion=None, updated_by_id=user_id)
    

def help_buscar_almacen_destino(model_venta=None):
    """
    Función auxiliar para obtener el almacén HELP CEDIS asociado a la venta.
    """
    if model_venta is None:
        return None
    if model_venta.fase == Venta.FASE_PRE_VENTA and model_venta.ruta and model_venta.ruta.almacen_embarque:
        return model_venta.ruta.almacen_embarque

    elif model_venta.fase == Venta.FASE_VENTA_COMANDA:
        return model_venta.almacen.almacenes_pertence.first()
    else:
        return None