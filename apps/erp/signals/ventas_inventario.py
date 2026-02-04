from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from apps.erp.models import Venta, VentaDetalle, VentaDetalleLote
from apps.inventario.models import MovimientoInventario, ProductosMovimiento, LoteInventario, Almacen
from django.db import transaction

"""
====================================================================
        SIGNALS PARA CONTROL DE INVENTARIO EN VENTAS
====================================================================
"""
#SIGNAL DE VENTA ANTES DE GUARDAR UNA VENTA Y SI ES CREACION 
@receiver(pre_save, sender=Venta)
def validar_venta_pre_guardado(sender, instance, **kwargs):
    """
    Valida y prepara la venta antes de guardarla
    """
    if not instance:
        return

    # Solo procesar si es una creación de preventa
    if instance.pk is None and instance.fase == Venta.FASE_VENTA_COMANDA:
        # Creación de preventa
        instance.created_by = instance.vendedor
    elif instance.pk is None :
        # Creación de venta normal
        instance.vendedor = instance.created_by

@receiver(post_save, sender=Venta)
def actualizar_detalles_cargados(sender, instance, **kwargs):
    """
    Actualiza el estado de carga de todos los detalles cuando una preventa es totalmente cargada
    """
    # Validaciones básicas
    if not instance:
        return
        
    # Solo procesar si la venta está totalmente cargada y fue preventa
    if not (instance.is_total_cargado and instance.was_preventa):
        return
    
    print(f"[VENTA SIGNAL] Actualizando detalles para venta {instance.codigo} (ID: {instance.id})")
    
    try:
        ## 🔍 DEBUGGING: Veamos el estado actual de los detalles
        #total_detalles = instance.detalles.count()
        #detalles_false = instance.detalles.filter(is_cargado=False).count()
        #detalles_true = instance.detalles.filter(is_cargado=True).count()
        #
        #print(f"[VENTA SIGNAL DEBUG] Estado de detalles:")
        #print(f"  - Total detalles: {total_detalles}")
        #print(f"  - Con is_cargado=False: {detalles_false}")
        #print(f"  - Con is_cargado=True: {detalles_true}")
        
        # ✅ OPTIMIZACIÓN: Update masivo en una sola consulta
        # Solo actualizar detalles que NO estén marcados como cargados
        detalles_actualizados = instance.detalles.filter(is_cargado=False).update(is_cargado=True)
        
        if detalles_actualizados > 0:
            print(f"[VENTA SIGNAL] ✅ {detalles_actualizados} detalles marcados como cargados para venta {instance.codigo}")
        else:
            print(f"[VENTA SIGNAL] ⚠️ No se encontraron detalles con is_cargado=False para actualizar en venta {instance.codigo}")
            
    except Exception as e:
        print(f"[VENTA SIGNAL ERROR] ❌ Error al actualizar detalles: {str(e)}")
        # No re-lanzar la excepción para evitar que falle el guardado de la venta


@receiver(post_save, sender=Venta)
def cancelar_venta(sender, instance, **kwargs):
    print(f"[VENTA SIGNAL] Procesando cancelación para venta {instance.codigo} (ID: {instance.id})")
    # Verifica si la instancia existe
    if not instance:
        #print("[VENTA SIGNAL] Instancia de venta no encontrada.")
        return
    # Solo procesa si la venta fue cancelada
    if instance.fase == Venta.FASE_CANCELADA:
        ref = f"VENTA-{instance.id}"
        
        movimiento = MovimientoInventario.objects.filter(
            referencia=ref, 
            movimiento=MovimientoInventario.SALIDA_VENTA
        ).select_related(
            'almacen'
        ).prefetch_related(
            'productosMovimiento__producto',
            'productosMovimiento__lote'
        ).first()
        
        #print(f"[VENTA SIGNAL] Cancelando inventario para venta {instance.codigo} (ID: {instance.id})")
        cantidad_productos = 0
        
        if movimiento:
            for prod_mov in movimiento.productosMovimiento.all():
                lote = prod_mov.lote
                almacen = movimiento.almacen
                #print(f"Regresando {prod_mov.cantidad} del producto {prod_mov.producto.nombre} al almacen {almacen.nombre}")
                # Si el lote existe, regresa la cantidad al lote
                if lote:
                    lote.cantidad += prod_mov.cantidad
                    cantidad_productos += prod_mov.cantidad
                    lote.save()
                
        #Creamos los movimientos de entrada por cancelacion de venta
        with transaction.atomic():
            nuevo_movimiento = MovimientoInventario.objects.create(
                almacen=movimiento.almacen,
                cantidad=movimiento.cantidad,
                costo_unitario=movimiento.costo_unitario,
                tipo =MovimientoInventario.TIPO_ENTRADA,
                movimiento=MovimientoInventario.ENTRADA_VENTA,
                referencia=ref,
                fase=MovimientoInventario.FASE_TERMINADA,
                created_by=instance.updated_by
            )
            
            for prod_mov in movimiento.productosMovimiento.all():
                ProductosMovimiento.objects.create(
                    movimiento=nuevo_movimiento,
                    producto=prod_mov.producto,
                    lote=prod_mov.lote,
                    cantidad=prod_mov.cantidad,
                    costo_unitario=prod_mov.costo_unitario,
                    costo_total=prod_mov.costo_total,
                    created_by=instance.updated_by
                )