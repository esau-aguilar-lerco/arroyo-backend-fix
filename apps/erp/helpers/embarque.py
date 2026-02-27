from apps.inventario.models import MovimientoInventario, ProductosMovimiento, LoteInventario, EmbarqueReparto, ProductoEmbarque, LoteProductoEmbarque
from apps.erp.models import Venta, VentaDetalle
from django.db.models import Sum, Prefetch
from django.db import transaction
from decimal import Decimal, ROUND_HALF_UP

QTY_3 = Decimal("0.001")

def _dqty(value):
    if value is None or value == "":
        return Decimal("0.000")
    if isinstance(value, Decimal):
        d = value
    else:
        d = Decimal(str(value))
    return d.quantize(QTY_3, rounding=ROUND_HALF_UP)

def crear_movimiento_inventario_almacen_embarque(ruta=None, pedidos=None, productos_tara=None, usuario=None, almacen_origen=None):
    embarque_abierto = (
        EmbarqueReparto.objects
        .select_for_update()
        .filter(
            ruta=ruta,
            status_model=EmbarqueReparto.STATUS_MODEL_ACTIVE,
            fase__in=EmbarqueReparto.fases_programado_compat(),
        )
        .order_by('-id')
        .first()
    )
    if embarque_abierto:
        raise ValueError(
            f"La ruta {ruta.codigo if ruta else ''} ya tiene un embarque programado "
            f"(ID {embarque_abierto.id}, fase {embarque_abierto.fase})."
        )

    #almacen_help_cedis = Almacen.objects.filter(tipo=Almacen.TIPO_HELP_CEDIS).first()
    almacen_pedidos = ruta.almacen_embarque
    almacen_tara = ruta.almacen_embarque.pertence  # Almacén de tara asociado al almacén de embarque de la ruta
    
    response_lotes = buscar_lotes_para_embarque_fifo(productos_tara=productos_tara, pedidos=pedidos, almacen=almacen_origen)
    productos_tara = response_lotes.get('productos_tara', [])
    pedidos = response_lotes.get('pedidos', [])
    
    productos_tara = _validar_lotes_producto(productos_tara, almacen_origen, vacio_permitido=True)
    pedidos = _validar_lotes_producto_pedido(pedidos, almacen_origen)
    
    # ---------------------------------------------
    # MOVIMIENTOS PEDIDOS
    # ---------------------------------------------
    # Importante:
    # buscar_lotes_para_embarque_fifo() asigna lotes priorizando PEDIDOS y después TARA.
    # Para evitar inconsistencias de "lote sin inventario" debemos ejecutar en el mismo orden.
    productos_sin_ventas = obtener_productos_sin_venta(pedidos=pedidos)
    model_mov_salida_pedidos = _crear_movimiento_tara(
        almacen=almacen_origen,
        almacen_destino=almacen_pedidos,
        productos_entrada=productos_sin_ventas,
        nota=f"EMBARQUE-RUTA-VENTA",
        usuario=usuario,
        tipo="SALIDA"
    )
    productos_movidos_ped = mover_lotes(productos_a_mover=productos_sin_ventas, alamcen_destino=almacen_pedidos, usuario=usuario)
    pedidos = _asignar_lotes_movidos_a_pedidos(pedidos, productos_movidos_ped)
    
    model_mov_entrada_pedidos = _crear_movimiento_tara(
        almacen=almacen_pedidos,
        productos_entrada=productos_movidos_ped,
        nota=f"EMBARQUE-RUTA-VENTA",
        usuario=usuario,
        tipo="ENTRADA"
    )
    # ---------------------------------------------

    # ---------------------------------------------
    # MOVIMIENTOS TARA
    # ---------------------------------------------
    model_mov_salida = _crear_movimiento_tara(
        almacen=almacen_origen,
        almacen_destino=almacen_tara,
        productos_entrada=productos_tara,
        nota=f"TARA EMBARQUE RUTA {ruta.nombre}",
        usuario=usuario
    )
    productos_movidos = mover_lotes(productos_a_mover=productos_tara, alamcen_destino=almacen_tara, usuario=usuario)
    model_mov_entrada = _crear_movimiento_tara(
        almacen=almacen_tara,
        productos_entrada=productos_movidos,
        nota=f"TARA EMBARQUE RUTA {ruta.nombre}",
        usuario=usuario,
        tipo="ENTRADA"
    )
    # ---------------------------------------------
    
    
    #**********************************************
    #prcesar venta 
    ventas_models = [] 
    for pedido in pedidos:
        venta = pedido.get('venta')
        ventas_models.append(venta)
        productos = pedido.get('productos', [])
        len_productos = len(productos)
        sum_cargados_completo = 0
        
        detalles_venta = venta.detalles.all()
        detalles_venta_len = detalles_venta.count()
        for i, detalle in enumerate(detalles_venta):
            producto_encontrado = False
            for producto_pedido in productos:
                if detalle.producto.id == producto_pedido.get('producto').id:
                    producto_encontrado = True
                    sum_cargados_completo += 1
                    detalle.cantidad_logistica = producto_pedido.get('cantidad')
                    if detalle.cantidad == producto_pedido.get('cantidad'):
                        #marcamos como cargado el detalle
                        if not detalle.is_cargado:
                            #detalle.is_cargado = True
                            detalle.updated_by = usuario
                            
                            print(f"✅ [EMBARQUE] Producto {detalle.producto.nombre} (ID: {detalle.producto.id}) cargado correctamente en el embarque para la venta ID {venta.id}")
                    detalle.save()
                    break
            if not producto_encontrado:
                print(f"❌ [EMBARQUE] Producto {detalle.producto.nombre} (ID: {detalle.producto.id}) NO fue cargado en el embarque para la venta ID {venta.id}")
    
        if sum_cargados_completo == detalles_venta_len:
            venta.is_total_cargado = True
            venta.updated_by = usuario
            venta.save()
            #print(f"✅ [EMBARQUE] La venta ID {venta.id} ha sido completamente cargada en el embarque.")
    

    #REALIZAR EL REGISTRO
    
    models_embarque_reparto = EmbarqueReparto.objects.create(
        ruta=ruta,
        encargado=ruta.asignado,
        movimiento_inventario_pedidos_entrada=model_mov_entrada_pedidos,
        movimiento_inventario_pedidos_salida=model_mov_salida_pedidos,
        movimiento_inventario_tara_entrada=model_mov_entrada,
        movimiento_inventario_tara_salida=model_mov_salida,
        created_by=usuario
    )
    for venta in ventas_models:
        models_embarque_reparto.ventas.add(venta)
    
    
    #--------------------------------------
    #PRODUCTOS Y LOTES 
    # TARA 
    for producto_data in productos_tara:
        producto = producto_data.get('producto')
        cantidad = _dqty(producto_data.get('cantidad'))
        lotes = producto_data.get('lotes', [])

        # Precio unitario promedio (ponderado por lote)
        total_costo = Decimal('0.00')
        total_cantidad = Decimal('0.00')
        for lote_data in lotes:
            lote = lote_data.get('lote')
            cantidad_lote = Decimal(str(lote_data.get('cantidad')))
            total_cantidad += cantidad_lote
            total_costo += cantidad_lote * lote.costo_unitario
        precio_unitario = (total_costo / total_cantidad) if total_cantidad > 0 else Decimal('0.00')
        
        producto_embarque = ProductoEmbarque.objects.create(
            embarque=models_embarque_reparto,
            tipo=ProductoEmbarque.TARA,
            producto=producto,
            cantidad=cantidad,
            precio_unitario=precio_unitario,
            created_by=usuario
        )
        for lote_data in lotes:
            lote = lote_data.get('lote')
            cantidad_lote = _dqty(lote_data.get('cantidad'))
            # Asociar el lote al producto_embarque
            models_lote_embarque = LoteProductoEmbarque.objects.create(
                producto_embarque=producto_embarque,
                lote=lote,
                cantidad=cantidad_lote,
                created_by=usuario
            )
    # PEDIDOS
    for pedido in pedidos:
        venta = pedido.get('venta')
        productos = pedido.get('productos', [])
        
        for producto_data in productos:
            producto = producto_data.get('producto')
            cantidad = Decimal(producto_data.get('cantidad'))
            lotes = producto_data.get('lotes', [])
            
            venta_detalle = VentaDetalle.objects.filter(venta=venta, producto=producto).first()
            
            producto_embarque = ProductoEmbarque.objects.create(
                embarque=models_embarque_reparto,
                tipo=ProductoEmbarque.PEDIDO,
                preventa=venta,
                precio_unitario=venta_detalle.precio_unitario if venta_detalle else Decimal('0.00'),
                producto=producto,
                cantidad=cantidad,
                created_by=usuario
            )
            for lote_data in lotes:
                lote = lote_data.get('lote')
                cantidad_lote = _dqty(lote_data.get('cantidad'))
                # Asociar el lote al producto_embarque
                models_lote_embarque = LoteProductoEmbarque.objects.create(
                    producto_embarque=producto_embarque,
                    lote=lote,
                    cantidad=cantidad_lote,
                    created_by=usuario
                )
    
    
    
    return models_embarque_reparto


def _validar_lotes_producto(productos_entrada, almacen_origen,vacio_permitido=False):

    if len(productos_entrada) == 0 and not vacio_permitido:
        raise ValueError("Debe proporcionar al menos un producto para la transformación.")
    
    #return productos_entrada
    
    for producto_data in productos_entrada:
        
        producto = producto_data.get('producto')
        cantidad = _dqty(producto_data.get('cantidad'))
        if not producto_data['completo']:
            raise ValueError("producto %s no tiene lotes suficientes para cubrir la cantidad solicitada de %s"%(producto.nombre,cantidad))
        #lotes = producto_data.get('lotes', [])
        #suma_lotes = sum([float(lote.get('cantidad')) for lote in lotes])
        #if suma_lotes != cantidad:
        #    raise ValueError(f"La suma de las cantidades de los lotes ({suma_lotes}) no coincide con la cantidad total del producto ({cantidad}) para el producto  {producto.nombre}.")
        
        
    return productos_entrada


def _validar_lotes_producto_pedido(pedidos = [], almacen_origen=None):
    if len(pedidos) == 0:
        raise ValueError("Debe proporcionar al menos un pedido para la validación.")

    for pedido in pedidos:
        venta = pedido.get('venta')
        if pedido['completo'] == False:
            raise ValueError("El almacen %s no cuenta con la cantidad de lotes suficientes para cubrir la cantidad solicitada del pedido de la venta con folio %s"%(almacen_origen.nombre, venta.codigo))
        
        # Validar también cada producto del pedido
        for producto_data in pedido.get('productos', []):
            if not producto_data.get('completo', False):
                producto = producto_data.get('producto')
                producto_nombre = producto.nombre if hasattr(producto, 'nombre') else f"ID {producto}"
                raise ValueError(
                    f"El producto {producto_nombre} no tiene lotes suficientes. "
                    f"Solicitado: {producto_data.get('cantidad')}, "
                    f"Cubierto: {producto_data.get('cantidad_cubierta', 0)}, "
                    f"Faltante: {producto_data.get('cantidad_faltante', 0)}"
                )
    
    return pedidos


def mover_lotes(productos_a_mover = [],alamcen_destino=None,usuario=None):
    lotes_afectados = []
    lote_main = None
    productos_new = []
    
    # Diccionario para trackear cuánto se ha movido de cada lote
    lotes_movidos = {}  # {lote_id: cantidad_ya_movida}
    
    for producto_data in productos_a_mover:
        dictionario_lote = {}
        producto = producto_data.get('producto')
        cantidad = _dqty(producto_data.get('cantidad'))
        
        dictionario_lote['producto'] = producto
        dictionario_lote['cantidad'] = _dqty(cantidad)
        dictionario_lote['lotes'] = []
        
        lotes = producto_data.get('lotes', [])
        for lote_data in lotes:
            lote = lote_data.get('lote')
            cantidad_lote = _dqty(lote_data.get('cantidad'))
            if cantidad_lote <= 0:
                continue
            
            # Recargar el lote de la DB para obtener la cantidad actualizada
            lote.refresh_from_db()
            cantidad_actual = _dqty(lote.cantidad)
            if cantidad_actual <= 0:
                raise ValueError(
                    f"El lote {lote.id} ya no tiene inventario disponible al momento de cargar el embarque."
                )

            # Si el lote cambió de cantidad entre la reserva inicial y el movimiento,
            # es más seguro abortar para no dejar asignaciones inconsistentes.
            if cantidad_lote > (cantidad_actual + QTY_3):
                raise ValueError(
                    f"El lote {lote.id} cambió de disponibilidad durante la carga. "
                    f"Disponible: {cantidad_actual}, requerido: {cantidad_lote}"
                )

            if cantidad_lote >= cantidad_actual:
                # El lote se mueve completo (o lo que queda)
                lote.almacen = alamcen_destino
                lote.save()
                lote_main = lote
                lotes_afectados.append(lote)
                cantidad_movida = _dqty(cantidad_actual)
            else:
                # Crear un nuevo lote con la cantidad a mover
                nuevo_lote = LoteInventario.objects.create(
                    lote_herencia=lote,
                    producto=lote.producto,
                    almacen=alamcen_destino,
                    cantidad=cantidad_lote,
                    costo_unitario=lote.costo_unitario,
                    fecha_ingreso=lote.fecha_ingreso,
                    fecha_vencimiento=lote.fecha_vencimiento,
                    created_by=usuario
                )
                # Actualizar el lote original restando la cantidad movida 
                cant_temp = _dqty(cantidad_actual - cantidad_lote)
                lote.cantidad = cant_temp
                lote.save()
                lote_main = nuevo_lote
                lotes_afectados.append(nuevo_lote)
                cantidad_movida = _dqty(cantidad_lote)
            
            dictionario_lote['lotes'].append({'lote': lote_main, 'cantidad': cantidad_movida})
        productos_new.append(dictionario_lote)
    return productos_new


def _asignar_lotes_movidos_a_pedidos(pedidos, productos_movidos):
    """
    Reemplaza los lotes reservados por los lotes realmente movidos al almacén de pedidos.
    Evita que ProductoEmbarque/LoteProductoEmbarque apunten a lotes del almacén origen.
    """
    pedidos = pedidos or []
    productos_movidos = productos_movidos or []
    total_lineas = sum(len(pedido.get('productos', [])) for pedido in pedidos)

    if total_lineas != len(productos_movidos):
        raise ValueError(
            "Inconsistencia interna: número de líneas movidas no coincide con productos del pedido."
        )

    idx = 0
    for pedido in pedidos:
        for producto_data in pedido.get('productos', []):
            moved = productos_movidos[idx]
            idx += 1

            producto_pedido = producto_data.get('producto')
            producto_moved = moved.get('producto')
            id_pedido = producto_pedido.id if hasattr(producto_pedido, 'id') else producto_pedido
            id_moved = producto_moved.id if hasattr(producto_moved, 'id') else producto_moved

            if id_pedido != id_moved:
                raise ValueError(
                    "Inconsistencia interna: el orden de productos movidos no coincide con el pedido."
                )

            lotes_reales = moved.get('lotes', [])
            if not lotes_reales:
                raise ValueError(
                    f"No se pudieron mover lotes para el producto {getattr(producto_pedido, 'nombre', id_pedido)}."
                )

            cantidad_solicitada = _dqty(producto_data.get('cantidad'))
            cantidad_movida = _dqty(sum(_dqty(lote.get('cantidad')) for lote in lotes_reales))
            if cantidad_movida + QTY_3 < cantidad_solicitada:
                raise ValueError(
                    f"No se pudo mover la cantidad completa del producto "
                    f"{getattr(producto_pedido, 'nombre', id_pedido)}. "
                    f"Solicitado: {cantidad_solicitada}, movido: {cantidad_movida}."
                )

            # Guardamos los lotes reales (ya en almacén destino) y normalizamos cantidad.
            producto_data['lotes'] = lotes_reales
            producto_data['cantidad'] = cantidad_solicitada

    return pedidos


def obtener_productos_sin_venta(pedidos=[]):
    productos_sin_ventas = []
    
    for pedido in pedidos:
        venta = pedido.get('venta')
        productos = pedido.get('productos', [])
        for producto_item in productos:
            productos_sin_ventas.append(producto_item)

        #print (f"Procesando pedido para la venta ID {productos}")
        
        
    return productos_sin_ventas

  
        
def _crear_movimiento_tara(almacen=None,almacen_destino=None, productos_entrada=[], nota="", usuario=None,tipo="SALIDA"):
    with transaction.atomic():
        cant_productos = 0# sum([float(producto_data.get('cantidad')) for producto_data in productos_entrada])
        movimiento = MovimientoInventario.objects.create(
            almacen=almacen,
            almacen_destino=almacen_destino,
            tipo=MovimientoInventario.TIPO_SALIDA if tipo=="SALIDA" else MovimientoInventario.TIPO_ENTRADA,
            movimiento=MovimientoInventario.SALIDA_EMBARQUE if tipo=="SALIDA" else MovimientoInventario.ENTRADA_EMBARQUE,    
            nota=nota,
            fase=MovimientoInventario.FASE_TERMINADA,
            created_by=usuario,
            cantidad=cant_productos,
            #referencia=referencia
        )
        
        for producto_data in productos_entrada:
            #print (f"  Producto para movimiento de tara: {producto_data}")
            producto = producto_data.get('producto')
            #cantidad_total = Decimal(producto_data.get('cantidad'))
            lotes = producto_data.get('lotes', [])
            
            for lote_data in lotes:
                lote = lote_data.get('lote')
                cantidad_lote = _dqty(lote_data.get('cantidad'))
                
                producto_movimiento = ProductosMovimiento.objects.create(
                    movimiento=movimiento,
                    producto=producto,
                    lote=lote,
                    cantidad=cantidad_lote,
                    costo_unitario=lote.costo_unitario
                )
                
                # Actualizar el inventario del lote
                #lote.cantidad -= cantidad_lote
                #lote.save()
        
        return movimiento



def buscar_lotes_para_embarque_fifo(pedidos=None, productos_tara=None, almacen=None):
    """
    Busca lotes siguiendo el principio UEPS/LIFO (Últimas Entradas, Primeras Salidas).
    Los lotes más recientes se usan primero. Los lotes usados no se repiten entre pedidos.
    
    Args:
        pedidos: Lista de pedidos con estructura:
            [
                {
                    "venta": <modelo Venta o ID>,
                    "productos": [
                        {"producto": <modelo Producto o ID>, "cantidad": 100}
                    ]
                }
            ]
        productos_tara: Lista de productos de tara abierta:
            [
                {"producto": <modelo Producto o ID>, "cantidad": 50}
            ]
        almacen: Modelo del almacén donde buscar los lotes
    
    Returns:
        {
            "pedidos": [
                {
                    "venta": <modelo o ID>,
                    "productos": [
                        {
                            "producto": <modelo o ID>,
                            "cantidad": 100,
                            "cantidad_cubierta": 100,
                            "cantidad_faltante": 0,
                            "completo": True,
                            "lotes": [
                                {"lote_id": 1, "cantidad": 80},
                                {"lote_id": 2, "cantidad": 20}
                            ]
                        }
                    ],
                    "completo": True
                }
            ],
            "productos_tara": [
                {
                    "producto": <modelo o ID>,
                    "cantidad": 50,
                    "cantidad_cubierta": 50,
                    "cantidad_faltante": 0,
                    "completo": True,
                    "lotes": [
                        {"lote_id": 3, "cantidad": 50}
                    ]
                }
            ],
            "resumen": {
                "pedidos_completos": 2,
                "pedidos_incompletos": 0,
                "productos_tara_completos": 1,
                "productos_tara_incompletos": 0
            }
        }
    """
    from apps.inventario.models import LoteInventario
    from decimal import Decimal
    
    if pedidos is None:
        pedidos = []
    if productos_tara is None:
        productos_tara = []
    
    # Diccionario para trackear cantidad disponible de cada lote (evitar reusar lotes)
    # {lote_id: cantidad_disponible}
    lotes_disponibilidad = {}
    
    def obtener_producto_id(producto):
        """Obtiene el ID del producto ya sea modelo o entero"""
        if hasattr(producto, 'id'):
            return producto.id
        return producto
    
    def obtener_lotes_fifo(producto_id):
        """
        Obtiene los lotes ordenados por UEPS/LIFO (fecha_ingreso descendente).
        Retorna queryset de lotes activos con cantidad > 0
        """
        return LoteInventario.objects.filter(
            producto_id=producto_id,
            almacen=almacen,
            status_model='ACTIVE',
            cantidad__gt=0
        ).order_by('-fecha_ingreso', '-id')  # UEPS: primero los más recientes
    
    def asignar_lotes_a_producto(producto, cantidad_solicitada):
        """
        Asigna lotes a un producto siguiendo UEPS/LIFO.
        Retorna dict con lotes asignados y estado de completitud.
        """
        producto_id = obtener_producto_id(producto)
        cantidad_solicitada = _dqty(cantidad_solicitada)
        cantidad_restante = cantidad_solicitada
        lotes_asignados = []
        
        # Obtener lotes UEPS para este producto
        lotes = obtener_lotes_fifo(producto_id)
        
        for lote in lotes:
            if cantidad_restante <= 0:
                break
            
            # Verificar disponibilidad del lote (puede estar parcialmente usado)
            if lote.id not in lotes_disponibilidad:
                lotes_disponibilidad[lote.id] = _dqty(lote.cantidad)
            
            disponible = lotes_disponibilidad[lote.id]
            
            if disponible <= 0:
                continue
            
            # Calcular cantidad a usar de este lote
            cantidad_usar = min(disponible, cantidad_restante)
            
            # Registrar asignación
            lotes_asignados.append({
                'lote': lote,
                'cantidad': _dqty(cantidad_usar)
            })
            
            # Actualizar disponibilidad y cantidad restante
            lotes_disponibilidad[lote.id] -= cantidad_usar
            cantidad_restante -= cantidad_usar
        
        cantidad_cubierta = cantidad_solicitada - cantidad_restante
        
        return {
            'producto': producto,
            'cantidad': _dqty(cantidad_solicitada),
            'cantidad_cubierta': _dqty(cantidad_cubierta),
            'cantidad_faltante': _dqty(cantidad_restante),
            'completo': cantidad_restante <= 0,
            'lotes': lotes_asignados
        }
    
    # ========================================
    # PROCESAR PEDIDOS
    # ========================================
    resultado_pedidos = []
    pedidos_completos = 0
    pedidos_incompletos = 0
    
    for pedido in pedidos:
        venta = pedido.get('venta')
        productos = pedido.get('productos', [])
        
        productos_procesados = []
        pedido_completo = True
        
        for prod_data in productos:
            producto = prod_data.get('producto')
            cantidad = prod_data.get('cantidad', 0)
            
            resultado_producto = asignar_lotes_a_producto(producto, cantidad)
            productos_procesados.append(resultado_producto)
            
            if not resultado_producto['completo']:
                pedido_completo = False
        
        resultado_pedidos.append({
            'venta': venta,
            'productos': productos_procesados,
            'completo': pedido_completo
        })
        
        if pedido_completo:
            pedidos_completos += 1
        else:
            pedidos_incompletos += 1
    
    # ========================================
    # PROCESAR PRODUCTOS TARA
    # ========================================
    resultado_tara = []
    tara_completos = 0
    tara_incompletos = 0
    
    for prod_tara in productos_tara:
        producto = prod_tara.get('producto')
        cantidad = prod_tara.get('cantidad', 0)
        
        resultado_producto = asignar_lotes_a_producto(producto, cantidad)
        resultado_tara.append(resultado_producto)
        
        if resultado_producto['completo']:
            tara_completos += 1
        else:
            tara_incompletos += 1
    
    # ========================================
    # RESULTADO FINAL
    # ========================================
    return {
        'pedidos': resultado_pedidos,
        'productos_tara': resultado_tara,
        'resumen': {
            'pedidos_completos': pedidos_completos,
            'pedidos_incompletos': pedidos_incompletos,
            'productos_tara_completos': tara_completos,
            'productos_tara_incompletos': tara_incompletos,
            'total_pedidos': len(pedidos),
            'total_productos_tara': len(productos_tara)
        }
    }




def buscar_lotes_para_embarque(preventas_embarque=None,almacen=None):
    """
    Función auxiliar para buscar lotes que coincidan con la cantidad solicitada.
    Primero busca lotes con cantidad exacta, luego busca lotes parciales si no encuentra exactos.

    Args:
        preventas_embarque: [
            {
                "preventa": 187,
                "productos": [
                    {
                        "id": 168,
                        "cantidad": 10
                    }
                ]
            }
        ]
    
    Returns:
        {
            venta_id: {
                "lotes_encontrados": [],
                "lotes_completos": [],
                "lotes_parciales": []
            },
            venta_id: {
                "lotes_encontrados": [],
                "lotes_completos": [],
                "lotes_parciales": []
            }
        }
    """
    # Diccionario principal agrupado por venta_id
    resultado_por_venta = {}
    
    # Lista global para evitar duplicados entre todas las ventas
    lotes_usados = []


    for preventa in preventas_embarque:
        model_preventa = preventa.get('preventa')
        venta_id = model_preventa.id 
        # Inicializar estructura para esta venta si no existe
        if venta_id not in resultado_por_venta:
            resultado_por_venta[venta_id] = {
                "lotes_encontrados": [],
                "lotes_completos": [],
                "lotes_parciales": []
            }
        
        for j, detalle in enumerate(preventa.get('productos', [])):
            producto = detalle.get('id')  # este id trae el model completo del producto
            cantidad = detalle.get('cantidad')
            
            detalle_venta_producto = model_preventa.detalles.filter(producto=producto).first()
            if not detalle_venta_producto:
                raise ValueError(f"El producto {producto.nombre} no se encuentra en la preventa con ID {model_preventa.codigo}.")
            elif detalle_venta_producto.cantidad != cantidad:
                raise ValueError(f"""La cantidad del producto {producto.nombre} no coincide con la cantidad solicitada en la preventa {model_preventa.codigo}.
                                 Cantidad en preventa: {detalle_venta_producto.cantidad}, Cantidad solicitada: {cantidad}""")
        
            # BUSCAMOS LOS LOTES QUE COINCIDAN CON LA CANTIDAD SOLICITADA
            lote_exacto = LoteInventario.objects.filter(
                producto=producto,
                cantidad=cantidad,
                almacen=almacen,
                status_model='ACTIVE',
            ).exclude(id__in=lotes_usados).order_by('id').values_list('id','cantidad').first()

            if lote_exacto:
                lote_data = {
                    'id': lote_exacto[0],
                    'producto': producto.id,
                    'cantidad': lote_exacto[1]
                }
                resultado_por_venta[venta_id]["lotes_encontrados"].append(lote_data)
                resultado_por_venta[venta_id]["lotes_completos"].append({
                    'id': lote_exacto[0], 
                    'cantidad': lote_exacto[1],
                    'producto': producto.id
                })
                lotes_usados.append(lote_exacto[0])
                continue
                
            # Si no hay lotes exactos, buscar lotes parciales
            cantidad_restante = cantidad
            lotes_parciales = LoteInventario.objects.filter(
                producto=producto,
                cantidad__lte=cantidad_restante,
                almacen=almacen,
                status_model='ACTIVE'
            ).exclude(id__in=lotes_usados).order_by('id')

            
            for k, lote in enumerate(lotes_parciales):
                if cantidad_restante <= 0:
                    break
                    
                cantidad_usar = min(lote.cantidad, cantidad_restante)
                lote_data = {
                    'id': lote.id,
                    'producto': producto.id,
                    'cantidad': cantidad_usar
                }
                resultado_por_venta[venta_id]["lotes_encontrados"].append(lote_data)
                resultado_por_venta[venta_id]["lotes_parciales"].append({
                    'id': lote.id, 
                    'cantidad': cantidad_usar,
                    'producto': producto.id
                })
                lotes_usados.append(lote.id)
                cantidad_restante -= cantidad_usar
                    
        

    return resultado_por_venta








def identificar_preventas_cargadas_completamente_actualizar_(lotes_encontrados_por_venta,usuario=None):
    for venta_id in lotes_encontrados_por_venta.keys():
        #agupamos los producto y su cantidad total por producto
        productos_cantidad = {}
        for lote in lotes_encontrados_por_venta[venta_id]['lotes_encontrados']:
            producto_id = lote['producto']
            cantidad = lote['cantidad']
            if producto_id in productos_cantidad:
                productos_cantidad[producto_id] += cantidad
            else:
                productos_cantidad[producto_id] = cantidad
        #OBTENER LOS PRODUCTOS QUE se faltan cargarán en el embarque
        # ✅ OBTENER LOS DETALLES DE LA VENTA EN UNA SOLA CONSULTA
        venta = Venta.objects.filter(id=venta_id).prefetch_related(
            Prefetch('detalles',
                queryset=VentaDetalle.objects.exclude(producto_id__in=productos_cantidad.keys())
                                            .select_related('producto')
            )
        ).first()   

        detalles = venta.detalles.all()
        #SI no EXISTEN PRODUCTOS POR CARGAR 
        for de in detalles:
            print(f"❌ FALTA CARGAR PRODUCTO: {de.producto.nombre} - Cantidad: {de.cantidad}")
        if not detalles:
            #modifcamos la venta como cargada completamente
            print(f"✅ La venta ID {venta_id} ha sido completamente cargada en el embarque.")
            venta.is_total_cargado = True
            venta.updated_by = usuario
            
            venta.save()
            
        #print(f"🔍 Verificando venta ID {venta_id} - detalles faltantes: {detalles}")


def identificar_preventas_cargadas_completamente_actualizar(lotes_encontrados_por_venta, usuario=None):
    for venta_id in lotes_encontrados_por_venta.keys():
        # Agrupamos los productos y su cantidad total por producto
        productos_cantidad = {}
        for lote in lotes_encontrados_por_venta[venta_id]['lotes_encontrados']:
            producto_id = lote['producto']
            cantidad = lote['cantidad']
            if producto_id in productos_cantidad:
                productos_cantidad[producto_id] += cantidad
            else:
                productos_cantidad[producto_id] = cantidad
       
        
        # OBTENER LA VENTA Y VERIFICAR SU ESTADO ANTES DE CUALQUIER CAMBIO
        venta = Venta.objects.get(id=venta_id)
        
        
        # VERIFICAR TODOS LOS DETALLES DE LA VENTA
        todos_los_detalles = venta.detalles.all()
       
        for i, detalle in enumerate(todos_los_detalles):
            print(f"   Detalle {i+1}: Producto {detalle.producto.nombre} (ID: {detalle.producto.id}) - Cantidad: {detalle.cantidad} - is_cargado: {detalle.is_cargado}")
        
        # OBTENER LOS PRODUCTOS QUE FALTAN POR CARGAR EN EL EMBARQUE
        detalles_faltantes = VentaDetalle.objects.filter(
            venta_id=venta_id
        ).exclude(producto_id__in=productos_cantidad.keys())
        
        print(f"🚨 [EMBARQUE] Detalles que faltan por cargar: {detalles_faltantes.count()}")
        
        for detalle in detalles_faltantes:
            print(f"❌ FALTA CARGAR PRODUCTO: {detalle.producto.nombre} (ID: {detalle.producto.id}) - Cantidad: {detalle.cantidad}")
        
        if not detalles_faltantes.exists():
            # Modificamos la venta como cargada completamente
            venta.is_total_cargado = True
            venta.updated_by = usuario
            venta.save()
        else:
            print(f"⚠️ [EMBARQUE] La venta ID {venta_id} AÚN tiene productos pendientes por cargar")

def crear_movimiento_inventario_almacen_embarque_ruta(ruta=None, lotes_list_movimiento=None, productos_tara=None, usuario=None):
    almacen_ruta = ruta.almacen
    almacen_ruta_embarque = ruta.almacen_embarque

    for venta in lotes_list_movimiento.keys():
        lotes = lotes_list_movimiento[venta]['lotes_encontrados']
        cantidad_total = sum([lote['cantidad'] for lote in lotes])
        movimiento_salida = MovimientoInventario.objects.create(
                almacen=almacen_ruta_embarque,
                almacen_destino=almacen_ruta,  # Almacén destino es el almacén de la ruta
                tipo=MovimientoInventario.TIPO_SALIDA,
                movimiento=MovimientoInventario.SALIDA_EMBARQUE,
                cantidad=cantidad_total,
                referencia=f"Embarque a Ruta {ruta.nombre} - Venta {venta}".upper(),
                fase=MovimientoInventario.FASE_TERMINADA,
                created_by=usuario,
        )
        movimiento_entrada = MovimientoInventario.objects.create(
                almacen=almacen_ruta_embarque,
                almacen_destino=almacen_ruta,  # Almacén destino es el almacén de la ruta
                tipo=MovimientoInventario.TIPO_ENTRADA,
                movimiento=MovimientoInventario.ENTRADA_EMBARQUE,
                cantidad=cantidad_total,
                referencia=f"Entrada a Ruta {ruta.nombre} - Venta {venta}".upper(),
                fase=MovimientoInventario.FASE_TERMINADA,
                created_by=usuario,
        )
        for lote in lotes:
            lote_model = LoteInventario.objects.filter(id=lote['id']).first()
            lote_model.almacen = almacen_ruta
            lote_model.save()
            
            ProductosMovimiento.objects.create(
                movimiento=movimiento_salida,
                lote_id=lote['id'],
                producto_id=lote['producto'],
                cantidad=lote['cantidad'],
            )
            ProductosMovimiento.objects.create(
                movimiento=movimiento_entrada,
                lote_id=lote['id'],
                producto_id=lote['producto'],
                cantidad=lote['cantidad'],
            )
       

def crear_embarque_ruta(ruta=None, preventas_embarque=None, productos_tara=None, usuario=None):
    # Buscar embarque vigente en fase programado (incluye valor legacy CARGA).
    embarque = (
        EmbarqueReparto.objects.filter(
            ruta=ruta,
            fase__in=EmbarqueReparto.fases_programado_compat(),
        )
        .order_by('-id')
        .first()
    )

    if not embarque:
        embarque = EmbarqueReparto.objects.create(
            ruta=ruta,
            fase=EmbarqueReparto.FASE_PROGRAMADO,
            created_by=usuario,
        )
    elif embarque.fase == EmbarqueReparto.FASE_CARGA_LEGACY:
        embarque.fase = EmbarqueReparto.FASE_PROGRAMADO
        embarque.save(update_fields=['fase', 'updated_at'])
    
    #cuunt_preventas = len(preventas_embarque)
    
    for preventa in preventas_embarque:
        model_preventa = preventa.get('preventa')
        venta_id = model_preventa.id 
        for j, detalle in enumerate(preventa.get('productos', [])):
            producto = detalle.get('id')  # este id trae el model completo del producto
            cantidad = detalle.get('cantidad')
            producto_embarque = ProductoEmbarque.objects.create(
                embarque=embarque,
                preventa=model_preventa,
                producto=producto,
                cantidad=cantidad,
                created_by=usuario
            )
            
       
    return {}
