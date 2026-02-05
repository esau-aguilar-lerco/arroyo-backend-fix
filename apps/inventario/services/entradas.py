from django.db import transaction, DatabaseError
from django.utils import timezone
from datetime import timedelta 
from decimal import Decimal

from apps.erp.models import Compra, CompraDetalle, OrdenCompra, Almacen,Insidencia, InsidenciaLote
from apps.inventario.models import LoteInventario, MovimientoInventario, ProductosMovimiento


class AbastecimientoService:
    """
    Servicio para manejar la lógica de abastecimiento de inventario
    """
    @staticmethod
    def _crear_lote_incidencia(producto, cantidad, user):
        """
        Crea un lote de inventario para la incidencia
        """
        almacen = Almacen.objects.filter(tipo = Almacen.TIPO_INSIDENCIAS).first()
        lote = LoteInventario.objects.create(
            producto=producto,
            almacen=almacen,
            cantidad=cantidad,
            costo_unitario=Decimal('0.00'),
            fecha_ingreso=timezone.now(),
            created_by=user,
            #updated_by=user
        )

        return lote
    
    @staticmethod
    def _crear_insidencia(productos_incidencias, compra, user):
        """
        Crea una insidencia para los productos con diferencias en la entrada
        """
        #from apps.erp.models import 

        if not productos_incidencias:
            return None

        insidencia = Insidencia.objects.create(
            descripcion=f"Incidencia generada por diferencias en la entrada de la compra {compra.codigo}",
            resuelta=False,
            created_by=user,
            #updated_by=user
        )

        for item in productos_incidencias:
            lote = AbastecimientoService._crear_lote_incidencia(
                producto=item['producto'],
                cantidad=item['cantidad'],
                user=user
            )
            
            InsidenciaLote.objects.create(
                insidencia=insidencia,
                lote=lote,  # No hay lote asociado en este caso
                #producto=item['producto'],
                cantidad=item['cantidad'],
                atendida=False,
                created_by=user,
                updated_by=user
            )

        return insidencia
    
    @staticmethod
    def validar_compra(compra_id, *, lock=False, nowait=False):
        qs = Compra.objects.filter(id=compra_id, status_model=Compra.STATUS_MODEL_ACTIVE)
        if lock: # LOCK
            qs = qs.select_for_update(nowait=nowait)
        try:
            compra = qs.get()
        except Compra.DoesNotExist:
            raise ValueError(f"Compra con ID {compra_id} no encontrada")

        if compra.estado != Compra.EN_CAMINO:
            raise ValueError(f"La compra debe estar en estado '{Compra.EN_CAMINO}'. Estado actual: {compra.estado}")

        return compra

    @staticmethod
    def obtener_almacen_destino(compra):
        """
        Obtiene el almacén destino desde la compra o la orden de compra
        """
        try:
            compra = Compra.objects.get(
                id=compra.id,
                status_model=Compra.STATUS_MODEL_ACTIVE
            )
            almacen_destino = compra.almacen_destino
        except Compra.DoesNotExist:
            compra = None
            almacen_destino = getattr(compra, 'almacen_destino', None)
            if not almacen_destino:
                raise ValueError("No se pudo determinar el almacén destino para el abastecimiento")
        
        if not almacen_destino:
            raise ValueError("El almacén destino no está definido en la compra")
        
        return compra, almacen_destino

    @staticmethod
    def generar_referencia(compra, referencia_custom=None):
        """
        Genera una referencia automática para el abastecimiento
        """
        if referencia_custom:
            return referencia_custom

        return f"ABAST-{compra.codigo}-{timezone.now().strftime('%Y%m%d%H%M%S%f')}" #microsegundos

    @staticmethod
    def crear_movimiento_principal(almacen_destino, referencia, nota, user):
        """
        Crea el movimiento principal de entrada por abastecimiento
        """
        return MovimientoInventario.objects.create(
            almacen=almacen_destino,
            almacen_destino=almacen_destino,
            tipo=MovimientoInventario.TIPO_ENTRADA,
            movimiento=MovimientoInventario.ENTRADA_ABASTECIMIENTO,
            cantidad=Decimal('0.00'),  # Se actualizará después
            costo_unitario=Decimal('0.00'),  # Se actualizará después
            referencia=referencia,
            nota=nota,
            fase=MovimientoInventario.FASE_TERMINADA,
            created_by=user,
            #updated_by=user
        )

    @staticmethod
    def procesar_items_abastecimiento(items, movimiento_principal, almacen_destino, compra_id, user):
        """
        Procesa cada item del abastecimiento creando lotes y productos_movimiento
        """
        lotes_creados = []
        productos_abastecidos = []
        costo_total_abastecimiento = Decimal('0.00')
        
        for item in items:
            ubicacion_rack = item.get('ubicacion_rack', None)

            if ubicacion_rack is None and almacen_destino.is_cedis:
                raise ValueError(f"El almacén destino es de tipo CEDIS, se requiere especificar la ubicación del rack para el producto ID {item['producto'].id}")
            #FIJAMOS QUE SI EL ALMACEN NO ES CEDIS, LA UBICACION RACK SEA NONE
            if not almacen_destino.is_cedis:
                ubicacion_rack = None
                
                
            costo_producto_compra = CompraDetalle.objects.filter(
                compra_id=compra_id,
                producto=item['producto']
            ).first()
            costo_unitario = Decimal('0.00')
            if costo_producto_compra:
                costo_unitario = costo_producto_compra.precio_unitario
            
            item['costo_unitario'] = costo_unitario

            producto = item['producto']
            cantidad = item['cantidad']
            #costo_unitario = item['costo_unitario']
            
            costo_total_item = cantidad * costo_unitario
            
            # Crear el lote de inventario
             # Calcular fecha de vencimiento
            fecha_vencimiento = None
            horas = producto.horas_caducidad if producto.horas_caducidad else 0
        #if  1 == 1:# producto.horas_caducidad is not None and producto.horas_caducidad > 0:
            fecha_vencimiento = timezone.now() + timedelta(hours= horas) #if producto.horas_caducidad else None
        
            lote = LoteInventario.objects.create(
                producto=producto,
                almacen=almacen_destino,
                ubicacion=ubicacion_rack,
                cantidad=0,
                costo_unitario=costo_unitario,
                fecha_ingreso=timezone.now(),
                #fecha_vencimiento=fecha_vencimiento,
                created_by=user,
                updated_by=user
            )
            
            # Crear el detalle del producto en el movimiento
            ProductosMovimiento.objects.create(
                movimiento=movimiento_principal,
                producto=producto,
                lote=lote,
                cantidad=cantidad,
                costo_unitario=costo_unitario,
                costo_total=costo_total_item,
                created_by=user,
                #updated_by=user
            )
            
            lotes_creados.append(lote)
            costo_total_abastecimiento += costo_total_item
            
            productos_abastecidos.append({
                "producto": {
                    "id": producto.id,
                    "nombre": producto.nombre,
                    "codigo": producto.codigo or "Sin código"
                },
                "lote_id": lote.id,
                "cantidad": float(cantidad),
                "costo_unitario": float(costo_unitario),
                "costo_total": float(costo_total_item),
                "ubicacion": str(lote.ubicacion) if lote.ubicacion else "Sin asignar"
            })
        
        return lotes_creados, productos_abastecidos, costo_total_abastecimiento

    @staticmethod
    def actualizar_movimiento_principal(movimiento_principal, items, costo_total_abastecimiento):
        """
        Actualiza el movimiento principal con los totales calculados
        """
        cantidad_total = sum(item['cantidad'] for item in items)
        costo_promedio = costo_total_abastecimiento / cantidad_total if cantidad_total > 0 else Decimal('0.00')
        
        movimiento_principal.cantidad = cantidad_total
        movimiento_principal.costo_unitario = costo_promedio
        movimiento_principal.save(update_fields=['cantidad', 'costo_unitario'])

    @staticmethod
    def actualizar_estados(compra, user):
        """
        Actualiza los estados de compra y orden de compra
        """
        if compra:
            compra.estado = Compra.FINALIZADA  # Estado que indica que ya está en almacén
            compra.updated_by = user
            compra.save(update_fields=['estado', 'updated_by'])
        
        orden_compra = compra.orden_compra if compra else None
        if orden_compra:
            orden_compra.estado = OrdenCompra.FINALIZADA
            orden_compra.updated_by = user
            orden_compra.save(update_fields=['estado', 'updated_by'])

    @staticmethod
    def construir_respuesta(movimiento_principal, compra, almacen_destino, 
                          items, costo_total_abastecimiento, productos_abastecidos, 
                          lotes_creados, referencia, nota, user):
        """
        Construye la respuesta final del abastecimiento
        """
        cantidad_total = sum(item['cantidad'] for item in items)
        costo_promedio = costo_total_abastecimiento / cantidad_total if cantidad_total > 0 else Decimal('0.00')
        
        return {
            "movimiento_principal": {
                "id": movimiento_principal.id,
                "referencia": movimiento_principal.referencia,
                "tipo": movimiento_principal.tipo,
                "movimiento": movimiento_principal.movimiento,
                "fase": movimiento_principal.fase
            },
           
            "compra": {
                "id": compra.id if compra else None,
                "codigo": compra.codigo if compra else None,
                "estado_actual": compra.estado if compra else None
            } if compra else None,
            "almacen_destino": {
                "id": almacen_destino.id,
                "nombre": almacen_destino.nombre,
                "tipo": almacen_destino.tipo
            },
            "resumen": {
                "total_items": len(items),
                "cantidad_total": float(cantidad_total),
                "costo_total": float(costo_total_abastecimiento),
                "costo_promedio": float(costo_promedio),
                "lotes_creados": len(lotes_creados)
            },
            "productos_abastecidos": productos_abastecidos,
            "metadatos": {
                "referencia": referencia,
                "nota": nota,
                "fecha_proceso": timezone.now().isoformat(),
                "procesado_por": {
                    "id": user.id,
                    "username": user.username
                }
            }
        }
    @staticmethod
    def procesar_entrada(cls,items, compra_id):
        existe_diferencia = False
        productos_incidencias = []
        for producto_item in items:
            detalle = CompraDetalle.objects.filter(
                compra_id=compra_id,
                producto=producto_item['producto']
            ).first()
            
            if not detalle:
                #PRODUCTO ADICIONAL
                existe_diferencia = True
                compra_detalle = CompraDetalle(
                    compra_id=compra_id,
                    producto=producto_item['producto'],
                    cantidad=producto_item['cantidad'],
                    precio_unitario=producto_item['costo_unitario'],
                    existe_diferencia=False,
                    es_producto_nuevo=True,
                    cantidad_entrada=producto_item['cantidad']
                )
                compra_detalle.save()
            else:
                if detalle.cantidad != producto_item['cantidad'] :
                    diferencia = detalle.cantidad - producto_item['cantidad']
                    productos_incidencias.append({
                        "producto": producto_item['producto'],
                        "cantidad": diferencia
                    })
                    #existe_diferencia = True
                    detalle.existe_diferencia = True
                detalle.cantidad_entrada = producto_item['cantidad']
                
                detalle.save(update_fields=['existe_diferencia', 'cantidad_entrada'])

        compra = Compra.objects.get(id=compra_id)
        compra.existe_diferencia = existe_diferencia
        
        cls._crear_insidencia(productos_incidencias, compra, compra.created_by)
        
        
        
        
        compra.save(update_fields=['existe_diferencia'])
    
    @classmethod
    def procesar_abastecimiento_completo(cls, validated_data, user):
        compra_id = validated_data['compra']
        items = validated_data['items']
        referencia_custom = validated_data.get('referencia', '')
        nota = validated_data.get('nota', '')

        with transaction.atomic():
            # Lock a la compra
            try:
                compra = cls.validar_compra(compra_id, lock=True, nowait=True)
            except DatabaseError:                
                raise ValueError("Compra en proceso de abastecimiento, intenta de nuevo")

            compra, almacen_destino = cls.obtener_almacen_destino(compra)
            referencia = cls.generar_referencia(compra, referencia_custom)

            movimiento_principal = cls.crear_movimiento_principal(almacen_destino, referencia, nota, user)

            lotes_creados, productos_abastecidos, costo_total = cls.procesar_items_abastecimiento(
                items, movimiento_principal, almacen_destino, compra.id, user
            )
            #Línea sospechosa
            # cls.procesar_entrada(cls, items, compra_id)

            cls.actualizar_movimiento_principal(movimiento_principal, items, costo_total)
            cls.actualizar_estados(compra, user)

            return cls.construir_respuesta(
                movimiento_principal, compra, almacen_destino,
                items, costo_total, productos_abastecidos,
                lotes_creados, referencia, nota, user
            )