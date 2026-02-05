from apps.inventario.models import MovimientoInventario, ProductosMovimiento, LoteInventario, Transformacion
#from apps.erp.models import Producto, Almacen
from django.db import transaction
from django.db.models import Sum
from decimal import Decimal



def crear_movimiento_transformacion(almacen=None, tipo=None, productos_entrada=[],productos_salida=[], nota="", usuario=None):
    #validar aalamcen existe
    if not almacen:
        raise ValueError("El almacén es obligatorio para crear un movimiento de transformación.")
    
    if tipo is None:
        raise ValueError("El tipo de movimiento debe ser 'TRANSFORMACION' o 'MERMA'.")
    
    if len(nota) > 150 or len(nota) == 0:
        raise ValueError("La nota debe tener entre 1 y 150 caracteres.")
    nota = nota.strip()
    _validar_lotes_producto(productos_entrada, almacen, tipo)
    
    if tipo == Transformacion.TIPO_MERMA:
        #retoenamos tupla
        mov = _crear_movimiento_salida(
            almacen=almacen,
            productos_entrada=productos_entrada,
            nota=nota,
            usuario=usuario,
            tipo=Transformacion.TIPO_MERMA
        )
        
        model_trans = crear_transformacion_registro(
            almacen=almacen,
            tipo=Transformacion.TIPO_MERMA,
            movimiento_salida=mov,
            movimiento_entrada=None,
            nota=nota,
            usuario=usuario
        )
        
        return model_trans
        
    elif tipo == Transformacion.TIPO_TRANSFORMACION:
        mov_salida = _crear_movimiento_salida(
            almacen=almacen,
            productos_entrada=productos_entrada,
            nota=nota,
            usuario=usuario,
            tipo=Transformacion.TIPO_TRANSFORMACION
        )
        mov_entrada = _crear_movimiento_entrada(
            almacen=almacen,
            productos_salida=productos_salida,
            nota=nota,
            usuario=usuario,
            referencia=f"ENTRADA-TRANS-{mov_salida.id}"
        )
        
        
        mov_entrada.referencia = f"SALIDA-TRANS-{mov_salida.id}"
        mov_entrada.save()
        mov_salida.referencia = f"ENTRADA-TRANS-{mov_entrada.id}"
        mov_salida.save()
        
        model_trans = crear_transformacion_registro(
            almacen=almacen,
            tipo=Transformacion.TIPO_TRANSFORMACION,
            movimiento_salida=mov_salida,
            movimiento_entrada=mov_entrada,
            nota=nota,
            usuario=usuario
        )
        
        return model_trans
    else:
        pass
    
def crear_lote_transformacion(almacen=None, producto=None, cantidad=Decimal('0.00'), costo_unitario=Decimal('0.00'), usuario=None):
    cost_unitario = costo_unitario if costo_unitario and costo_unitario > 0 else Decimal(producto.precio_base)
    return LoteInventario.objects.create(
        almacen=almacen,
        producto=producto,
        cantidad=cantidad,
        costo_unitario=cost_unitario,
        created_by=usuario,
        referencia="Lote creado por transformación"
    )
    
def crear_transformacion_registro(almacen=None, tipo=None, movimiento_salida=None, movimiento_entrada=None, nota="", usuario=None):
    #from apps.inventario.models import Transformacion
    transformacion = Transformacion.objects.create(
        tipo=tipo,
        almacen=almacen,
        referencia=f"TRANS-{movimiento_salida.id}-{movimiento_entrada.id if movimiento_entrada else 'N/A'}",
        nota=nota,
        movimiento_salida=movimiento_salida,
        movimiento_entrada=movimiento_entrada,
        created_by=usuario
    )
    return transformacion

def _crear_movimiento_entrada(almacen=None, productos_salida=[], nota="", usuario=None, referencia=""):
    
    with transaction.atomic():
        cant_productos = sum([float(producto_data.get('cantidad')) for producto_data in productos_salida])
        movimiento = MovimientoInventario.objects.create(
            almacen=almacen,
            tipo=MovimientoInventario.TIPO_ENTRADA ,
            movimiento=MovimientoInventario.ENTRADA_TRANSFORMACION,
            nota=nota,
            fase=MovimientoInventario.FASE_TERMINADA,
            created_by=usuario,
            cantidad=cant_productos,
            #referencia=referencia
        )
        for producto_data in productos_salida:
            producto = producto_data.get('producto')
            cantidad = float(producto_data.get('cantidad'))
            lote = crear_lote_transformacion(
                almacen=almacen,
                producto=producto,
                cantidad=Decimal(cantidad),
                costo_unitario=None,
                usuario=usuario
            )
            producto_movimiento = ProductosMovimiento.objects.create(
                movimiento=movimiento,
                producto=producto,
                lote=lote,
                cantidad=Decimal(cantidad),
                costo_unitario=lote.costo_unitario
            )
            
        return movimiento
        
        
        
def _crear_movimiento_salida(almacen=None, productos_entrada=[], nota="", usuario=None, tipo=Transformacion.TIPO_MERMA, referencia=""):
    with transaction.atomic():
        cant_productos = sum([float(producto_data.get('cantidad')) for producto_data in productos_entrada])
        movimiento = MovimientoInventario.objects.create(
            almacen=almacen,
            tipo=MovimientoInventario.TIPO_SALIDA ,
            movimiento=MovimientoInventario.SALIDA_MERMA if tipo==Transformacion.TIPO_MERMA else MovimientoInventario.SALIDA_TRANSFORMACION,
            nota=nota,
            fase=MovimientoInventario.FASE_TERMINADA,
            created_by=usuario,
            cantidad=cant_productos,
            referencia=referencia
        )
        
        for producto_data in productos_entrada:
            producto = producto_data.get('producto')
            #cantidad_total = Decimal(producto_data.get('cantidad'))
            lotes = producto_data.get('lotes', [])
            if not lotes:
                lotes = _asignar_lotes_fifo(
                    producto=producto,
                    cantidad_total=producto_data.get('cantidad'),
                    almacen=almacen
                )
                producto_data['lotes'] = lotes
            
            for lote_data in lotes:
                lote = lote_data.get('lote')
                cantidad_lote = Decimal(lote_data.get('cantidad'))
                
                producto_movimiento = ProductosMovimiento.objects.create(
                    movimiento=movimiento,
                    producto=producto,
                    lote=lote,
                    cantidad=cantidad_lote,
                    costo_unitario=lote.costo_unitario
                )
        
        return movimiento
    
#=============================================
#         VALIDAR LOTES
#==============================================   
def _validar_lotes_producto(productos_entrada = [], almacen=None, tipo=None):
    if len(productos_entrada) == 0:
        raise ValueError("Debe proporcionar al menos un producto para la transformación.")
    
    for producto_data in productos_entrada:
        
        producto = producto_data.get('producto')
        cantidad = Decimal(str(producto_data.get('cantidad')))
        lotes = producto_data.get('lotes', [])
        if tipo == Transformacion.TIPO_MERMA and not lotes:
            total_stock = (LoteInventario.objects.filter(
                producto=producto,
                almacen=almacen,
                cantidad__gt=0,
                status_model=LoteInventario.STATUS_MODEL_ACTIVE
            ).aggregate(total=Sum('cantidad'))['total'] or Decimal('0.00'))
            if total_stock < cantidad:
                raise ValueError(
                    f"No hay suficiente inventario para merma del producto {producto.nombre}. "
                    f"Disponible: {total_stock}, requerido: {cantidad}."
                )
            continue

        suma_lotes = sum([Decimal(str(lote.get('cantidad'))) for lote in lotes])
        if suma_lotes != cantidad:
            raise ValueError(
                f"La suma de las cantidades de los lotes ({suma_lotes}) no coincide con la "
                f"cantidad total del producto ({cantidad}) para el producto {producto.nombre}."
            )
        
        for lote_data in lotes:
            if almacen.id != lote_data.get('lote').almacen.id:
                raise ValueError(f"El lote {lote_data.get('lote').id} no pertenece al almacén {almacen.nombre}.")
            lote = lote_data.get('lote')
            cantidad_lote = Decimal(str(lote_data.get('cantidad')))
            if cantidad_lote <= 0:
                raise ValueError(f"La cantidad del lote debe ser mayor a 0 para el lote {lote.id} del producto {producto.nombre}.")


def _asignar_lotes_fifo(producto=None, cantidad_total=None, almacen=None):
    cantidad_total = Decimal(str(cantidad_total))
    lotes_qs = (LoteInventario.objects
                .filter(
                    producto=producto,
                    almacen=almacen,
                    cantidad__gt=0,
                    status_model=LoteInventario.STATUS_MODEL_ACTIVE
                )
                .order_by('fecha_ingreso'))

    restante = cantidad_total
    lotes = []

    for lote in lotes_qs:
        if restante <= 0:
            break
        tomar = lote.cantidad if lote.cantidad <= restante else restante
        lotes.append({'lote': lote, 'cantidad': tomar})
        restante -= tomar

    if restante > 0:
        raise ValueError(
            f"No hay suficiente inventario para merma del producto {producto.nombre}. "
            f"Faltante: {restante}."
        )

    return lotes