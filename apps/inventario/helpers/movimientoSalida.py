from decimal import Decimal 
from apps.erp.models import Almacen
from ..models import LoteInventario, MovimientoInventario, ProductosMovimiento
from django.db import transaction

#============================= IMPORTANTE: MOVIMIENTOS DE INVENTARIO ==========================
#                                     MOVIMENTO PRONCIPAL
#============================= MOVIMIENTOS DE INVENTARIO ==========================
def movimento_inventario(detalle_lotes=[], almacen_salida=None, almacen_destino=None, movimiento=MovimientoInventario.TIPO_SALIDA, sub_movimiento=MovimientoInventario.SALIDA_TRASPASO, nota="", user=None):
    """
    Función para manejar movimientos de inventario con corrección en la deducción de lotes
    """

    # Calcular cantidad total usando sum de Django para mejor precisión
    cantidad_total_productos = sum(Decimal(str(lote['cantidad'])) for lote in detalle_lotes)
 
    
    fase = MovimientoInventario.FASE_PROCESO if sub_movimiento == MovimientoInventario.SALIDA_TRASPASO else MovimientoInventario.FASE_TERMINADA
    almacen_destino = almacen_destino if sub_movimiento == MovimientoInventario.SALIDA_TRASPASO else None
    status = MovimientoInventario.STATUS_MODEL_ACTIVE if sub_movimiento == MovimientoInventario.SALIDA_TRASPASO else MovimientoInventario.STATUS_MODEL_INACTIVE
    ALMACEN_TRASPASO = Almacen.objects.filter(tipo=Almacen.TIPO_TRASPASO,pertence=almacen_salida).first()
    # Usar transacción para garantizar consistencia
    with transaction.atomic():
        model = MovimientoInventario.objects.create(
            almacen=almacen_salida,
            almacen_destino=almacen_destino,
            cantidad=cantidad_total_productos,
            tipo=movimiento,
            movimiento=sub_movimiento,
            nota=nota,
            detalle_nota=f'ENTRADA AL ALMACEN {almacen_destino.nombre} DE {almacen_salida.nombre}',
            created_by=user,
            referencia=f'MOV-{sub_movimiento}-ORI-ALM-{almacen_salida.id}-DEST-ALM-{almacen_destino.id}' if almacen_destino else f'MOV-{sub_movimiento}-ORI-ALM-{almacen_salida.id}',
            fase=fase,
            status_model=status
        )
        mov_virtual =MovimientoInventario.objects.create(
            almacen=almacen_salida,
            almacen_destino=ALMACEN_TRASPASO,
            cantidad=cantidad_total_productos,
            tipo=MovimientoInventario.TIPO_ENTRADA,
            movimiento=MovimientoInventario.ENTRADA_TRASPASO_VIRTUAL,
            nota=f"Entrada por traspaso desde {almacen_salida.nombre}",
            referencia=f'MOV-TRASP-VIT-{model.id}',
            created_by=user,
            fase=MovimientoInventario.FASE_TERMINADA,
            #status_model=MovimientoInventario.STATUS_MODEL_INACTIVE
        )

     
        # CREAR PRODUCTOS MOVIMIENTO
        for detalle in detalle_lotes:
            model_producto = detalle['producto']
            #print(f"Procesando detalle: {detalle}")
            
            for lotes_data in detalle['lotes']:
                #print(f"Lote data: {lotes_data}")
                cantidad_lote_tomar = Decimal(str(lotes_data['cantidad']))
                
                model_lote = actualiza_lote_salida(
                    lotes_data['lote'], 
                    cantidad_lote_tomar, 
                    user_id=user.id if user else None
                )
                #Prod mov main salida
                item = ProductosMovimiento.objects.create(
                    movimiento=model,
                    producto=model_producto,
                    cantidad=cantidad_lote_tomar,  # Usar cantidad del lote
                    lote_id=model_lote.id,
                    costo_unitario=model_lote.costo_unitario,
                    costo_total=lotes_data['cantidad'] * model_lote.costo_unitario,
                    created_by=user
                )
                
                #duplica el model lote tal cual con todos sus campos
                lote_new = LoteInventario(
                    producto=model_lote.producto,
                    almacen=ALMACEN_TRASPASO,
                    ubicacion=None,  # Siempre null para almacenes virtuales
                    cantidad=cantidad_lote_tomar,
                    costo_unitario=model_lote.costo_unitario,
                    fecha_ingreso=model_lote.fecha_ingreso,  # Mantener fecha de ingreso original
                    fecha_vencimiento=model_lote.fecha_vencimiento,
                    created_by=user
                )
                # Asignar created_at manualmente antes de guardar
                lote_new.created_at = model_lote.created_at
                lote_new.save()
                #Prod mov vir salida
                item_vir = ProductosMovimiento.objects.create(
                    movimiento=mov_virtual,
                    producto=model_producto,
                    cantidad=cantidad_lote_tomar,  # Usar cantidad del lote
                    lote_id=lote_new.id,
                    costo_unitario=lote_new.costo_unitario,
                    costo_total=cantidad_lote_tomar * lote_new.costo_unitario,
                    created_by=user
                )
                
    return model


def actualiza_lote_salida(lote, cantidad, user_id=None):
    """
    Actualiza la cantidad de un lote de inventario.
    """
    lote_id = lote.id
    cantidad = Decimal(str(cantidad))  # Asegurar que sea Decimal
    
    
    if lote.cantidad < cantidad:
        raise ValueError(f"El lote {lote_id} no tiene suficiente cantidad. Disponible: {lote.cantidad}, Requerido: {cantidad}")
    
    lote.cantidad -= cantidad
        
    if user_id:
        lote.updated_by_id = user_id
    
    lote.save()
    #print(f"Lote {lote_id} actualizado. Nueva cantidad: {lote.cantidad}")
    return lote


    """
    Obtiene un resumen de los lotes disponibles para un producto
    """
    filtros = {
        'producto_id': producto_id,
        'cantidad__gt': 0,
        'status_model': LoteInventario.STATUS_MODEL_ACTIVE
    }
    
    if almacen_id:
        filtros['almacen_id'] = almacen_id
    
    lotes = LoteInventario.objects.filter(**filtros).order_by('fecha_ingreso')
    
    return [
        {
            'lote_id': lote.id,
            'cantidad': lote.cantidad,
            'costo_unitario': lote.costo_unitario,
            'fecha_ingreso': lote.fecha_ingreso,
            'almacen': lote.almacen.nombre if lote.almacen else 'Sin almacén'
        }
        for lote in lotes
    ]