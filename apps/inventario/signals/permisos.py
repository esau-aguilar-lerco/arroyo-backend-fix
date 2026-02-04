from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from apps.inventario.models import (Piso, Zona, Rack, MovimientoInventario, Transformacion,
                                    LoteInventario
                             )

@receiver(post_migrate)
def crear_permisos_inventario(sender, **kwargs):
    #print(" Creando permisos personalizados para apps.inventario...")
    models_str = [
        ('piso', 'Piso', Piso),
        ('zona', 'Zona', Zona),
        ('rack', 'Rack', Rack),
        ('loteInventario', 'Traspaso Temporal', LoteInventario),
        ('movimiento_inventario', 'Movimiento de Inventario', MovimientoInventario),
        ('transformacion', 'Transformación', Transformacion),
    ]
    
    for model_name_permiso, model_name_str, model_class in models_str:
        content_type = ContentType.objects.get_for_model(model_class)
    
        permisos = [
            (  f"can_view_{model_name_permiso}".lower(),         f"Ver {model_name_str}".upper()),
            (f"can_update_{model_name_permiso}".lower(),  f"Actualizar {model_name_str}".upper()),
            (f"can_create_{model_name_permiso}".lower(),       f"Crear {model_name_str}".upper()),
            (f"can_delete_{model_name_permiso}".lower(),    f"Eliminar {model_name_str}".upper()),
        ]
        for codename, name in permisos:
            permiso, created = Permission.objects.get_or_create(
                codename=codename,
                name=name,
                content_type=content_type,
            )
            if created:
                print(f"Permiso '{name}' creado automáticamente.")
            else:
                pass
                print(f"Permiso '{name}' ya existe.")
                
        
        
@receiver(post_migrate)
def crear_permisos_especiales_inventario(sender, **kwargs):
    
    #===============================================
    # PERMISOS ESPECIALES PARA LA CONSTRUCCIÓN DE CEDIS Y CONSULTA DE INVENTARIO
    #===============================================
    permisos_especiales = [
            #PERMISO ENGLOBAR LO SPERMISOS DE PISO, ALAMCEN Y RACK
            #(  f"can_view_detalle_almacen".lower(),         f"Ver Detalle Almacén".upper()),
            (  f"can_view_detalle_cedis",  f"Ver Detalle la estructura de CEDIS"),
            (  f"can_update_detalle_cedis",f"Actualizar Detalle la estructura de CEDIS"),
            (  f"can_create_detalle_cedis",f"Crear Detalle la estructura de CEDIS"),
            (  f"can_delete_detalle_cedis",f"Eliminar Detalle la estructura de CEDIS"),
            (  f"can_consultar_inventario",f"Consultar Inventario"),

        ]
    for codename, name in permisos_especiales:
        permiso, created = Permission.objects.get_or_create(
            codename=codename.lower(),
            name=name.upper(),
            content_type=ContentType.objects.get_for_model(LoteInventario),
        )
        if created:
            print(f"Permiso '{name}' creado automáticamente.")
        else:
            #pass
            print(f"Permiso '{name}' ya existe.")
        
@receiver(post_migrate)
def crear_permisos_inventario_completo(sender, **kwargs):
    #===============================================
    # PERMISOS ESPECIALES PARA MANEJO DE TRASPASOS Y ENTRADAS/SALIDAS DE INVENTARIO
    #===============================================
    perm_traspasos = [
            #MOVIMIENTOS EN COMPRAS ENTRADAS
            (f"can_view_entradas_inventario_compras".lower(),         f"Visualizar compras por entrar".upper()),
            #(f"can_crear_entradas_inventario_compras".lower(),         f"Dar entradas de inventario por compras".upper()),
            (f"can_crear_entradas_inventario_abastecimiento".lower(),         f"Dar entradas de inventario por traspaso".upper()),
            
            #TRASPASOS ENTRE ALMACENES
            (f"can_crear_traspaso".lower(),         f"Crear Traspaso entre Almacenes".upper()),
            (f"can_view_traspaso".lower(),         f"Ver Traspaso entre Almacenes".upper()),
            #solicitud de traspaso
            (f"can_crear_solicitud_traspaso".lower(),         f"Crear Solicitud de Traspaso entre Almacenes".upper()),
            (f"can_view_solicitud_traspaso".lower(),         f"Ver Solicitud de Traspaso entre Almacenes".upper()),
            (f"can_rechazar_solicitud_traspaso".lower(),         f"Rechazar Solicitud de Traspaso entre Almacenes".upper()),
            
            #consultar inventario
            (f"can_consultar_inventario".lower(),         f"Consultar Inventario".upper()),

            #GESTION DE RUTAS
            (f"can_ver_pedidos_embarque".lower(),         f"Ver Pedidos / Embarque".upper()),
            (f"can_cargar_pedidos".lower(),         f"Carga de rutas".upper()),
            
            #(f"can_update_traspaso".lower(),         f"Actualizar Traspaso entre Almacenes".upper()),
            #entradas ENTRE ALMACENES
            #(f"can_crear_entradas_inventario_traspasos".lower(),         f"Crear entradas de inventario por traspasos".upper()),
            #(f"can_view_entradas_inventario_traspasos".lower(),         f"Visualizar entradas de inventario por traspasos".upper()),
            #(f"can_update_entradas_inventario_traspasos".lower(),         f"Actualizar entradas de inventario por traspasos".upper()),

    ]
    for codename, name in perm_traspasos:
            permiso, created = Permission.objects.get_or_create(
                codename=codename,
                name=name,
                content_type=ContentType.objects.get_for_model(MovimientoInventario),
            )
            if created:
                pass
                print(f"Permiso '{name}' creado automáticamente. manuales")
            else:
                pass
                print(f"Permiso '{name}' ya existe.")