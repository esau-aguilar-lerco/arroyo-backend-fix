from django.db.models.signals import post_save, pre_save, post_migrate
from django.dispatch import receiver
from apps.erp.models import Almacen, Rutas

"""
====================================================================
                CREACION DE ALMACEN VIRTUAL PARA RUTAS
====================================================================
"""
@receiver(post_save, sender=Rutas)
def crear_almacenes_virtual_ruta(sender, instance, created, **kwargs):
    if created:  
        try:
            from apps.erp.models import Empresa
            from apps.erp.models import Caja
            empresa_default = Empresa.objects.filter(status_model='ACTIVE').first()
            
            if not empresa_default:
                #print("[SIGNAL ERROR] No se encontró una empresa activa")
                return
            
            # Crear Almacén virtual
            nuevo_almacen = Almacen.objects.create(
                nombre=f"RUTA {instance.nombre} (TARA ABIERTA)",
                tipo=Almacen.TIPO_RUTA,
                empresa=empresa_default,
                encargado=instance.asignado,  
            )

            alamcen_embarque = Almacen.objects.create(
                pertence=nuevo_almacen,
                nombre=f"PEDIDOS {instance.nombre}",
                tipo=Almacen.TIPO_EMBARQUE,
                empresa=empresa_default,
                encargado=instance.asignado,  
            )
            
            instance.asignado.almacen = nuevo_almacen
            instance.asignado.save(update_fields=['almacen'])
            
            # Asignar el almacén recién creado a la ruta
            Rutas.objects.filter(pk=instance.pk).update(almacen=nuevo_almacen, almacen_embarque=alamcen_embarque)
            
            #crear una caja para la ruta 
            caja_ruta = Caja.objects.create(
                nombre=f"CAJA RUTA {instance.nombre}",
                tipo=Caja.RUTA,
                ruta=instance
            )
            
        except Exception as e:
            print(f"[SIGNAL ERROR] Error al crear almacén virtual para ruta {instance.codigo}: {str(e)}")
            import traceback
            traceback.print_exc()

    else:
        if instance.status_model == Rutas.STATUS_MODEL_DELETE:
            instance.almacen.status_model = Almacen.STATUS_MODEL_DELETE
            instance.almacen.save(update_fields=['status_model'])
            # Log del error pero no interrumpir la creación de la ruta

@receiver(post_save, sender=Almacen)
def crear_almacen_virtual(sender, instance, created, **kwargs):
    if created and instance.tipo == Almacen.TIPO_FIJO:
        try:
            nuevo_almacen_virtual = Almacen.objects.create(
                nombre=f"VIRTUAL {instance.nombre}",
                tipo=Almacen.TIPO_VIRTUAL,
                empresa=instance.empresa,
                encargado=instance.encargado,
                pertence=instance
            )
            nuevo_almacen_traspaso = Almacen.objects.create(
                nombre=f"TRASPASO {instance.nombre}",
                tipo=Almacen.TIPO_TRASPASO,
                empresa=instance.empresa,
                encargado=instance.encargado,
                pertence=instance
            )
            
        except Exception as e:
            print(f"[SIGNAL ERROR] Error al crear almacén virtual para el almacén {instance.codigo}: {str(e)}")
            import traceback
            traceback.print_exc()


@receiver(post_migrate)
def crear_almacenes_help_cedis(sender, **kwargs):
    print("[ERP post_migrate] Ejecutando tareas post-migrate...")
    # Ejemplos:
    # - Crear almacén virtual de ayuda para cedis y rutas en preventas
    from apps.erp.models import Almacen
    from django.db import transaction

    with transaction.atomic():
        if not Almacen.objects.filter(tipo=Almacen.TIPO_HELP_CEDIS).exists():
            Almacen.objects.create(
                nombre="ALMACÉN HELP CEDIS",
                codigo=None,  # se autogenera en save()
                tipo=Almacen.TIPO_HELP_CEDIS,
                is_cedis=False,
            )
        if not Almacen.objects.filter(tipo=Almacen.TIPO_INSIDENCIAS).exists():
            Almacen.objects.create(
                nombre="ALMACÉN INSIDENCIAS",
                codigo=None,  # se autogenera en save()
                tipo=Almacen.TIPO_INSIDENCIAS,
                is_cedis=False,
            )

    #print("[ERP post_migrate] Listo.")


# Crear almacenes virtuales despues de migrar todas las tablas
@receiver(post_migrate)
def crear_almacenes_virtuales(sender, **kwargs):
    almacenes = Almacen.objects.filter(tipo=Almacen.TIPO_FIJO, status_model='ACTIVE').exclude(tipo=Almacen.TIPO_HELP_CEDIS)
    for almacen in almacenes:
        Almacen.objects.get_or_create(
            nombre=f"VIRTUAL {almacen.nombre}",
            tipo=Almacen.TIPO_VIRTUAL,
            empresa=almacen.empresa,
            encargado=almacen.encargado,
            pertence=almacen
        )
        Almacen.objects.get_or_create(
            nombre=f"TRASPASO {almacen.nombre}",
            tipo=Almacen.TIPO_TRASPASO,
            empresa=almacen.empresa,
            encargado=almacen.encargado,
            pertence=almacen
        )

@receiver(post_migrate)
def crear_embarque_almacen_ruta(sender, **kwargs):
    rutas_sin_almacen_embarque = Rutas.objects.filter(almacen_embarque__isnull=True)
    for ruta in rutas_sin_almacen_embarque:
        try:
            from apps.erp.models import Empresa
            empresa_default = Empresa.objects.filter(status_model='ACTIVE').first()
            
            if not empresa_default:
                print("[SIGNAL ERROR] No se encontró una empresa activa")
                return
            
            # Crear Almacén de Embarque
            nuevo_almacen_embarque = Almacen.objects.create(
                nombre=f"EMBARQUE {ruta.nombre}",
                tipo=Almacen.TIPO_EMBARQUE,
                empresa=empresa_default,
                encargado=ruta.asignado,  
            )
            
            # Asignar el almacén recién creado a la ruta
            Rutas.objects.filter(pk=ruta.pk).update(almacen_embarque=nuevo_almacen_embarque)
            print(f"[SIGNAL] Creado almacén de embarque para la ruta {ruta.nombre}")
            
        except Exception as e:
            print(f"[SIGNAL ERROR] Error al crear almacén de embarque para ruta {ruta.codigo}: {str(e)}")
            import traceback
            traceback.print_exc()