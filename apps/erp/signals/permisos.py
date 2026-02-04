from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from apps.erp.models import (Cliente, Empresa, Proveedor, Producto, Almacen,
                             Sucursal,OrdenCompra,Compra,
                             UnidadVehicular, Rutas,
                             Venta,
                             Caja,
                             CajaApertura
                             )

@receiver(post_migrate)
def crear_permisos_personalizados(sender, **kwargs):
    models_str = [
        ('cliente', 'Cliente', Cliente),
        ('empresa', 'Empresa', Empresa),
        ('proveedor', 'Proveedor', Proveedor),
        ('producto', 'Producto', Producto),
        ('almacen', 'Almacen', Almacen),
        ('sucursal', 'Sucursal',Sucursal),
        ('orden_compra', 'Orden de Compra', OrdenCompra),
        ('compra', 'Compra', Compra),
        ('unidad_vehicular', 'Unidad Vehicular', UnidadVehicular),
        ('rutas', 'Rutas', Rutas),
        ('pre_venta', 'Pre Venta', Venta),
        ('venta', 'Venta', Venta),
        ('caja', 'Caja', Caja)
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
                #print(f"Permiso '{name}' ya existe.")
        
        #PARA VISUALIZAR PRECIOS 
        permiso, creacion = Permission.objects.get_or_create(
            codename="can_view_precio",
            name="VER PRECIOS".upper(),
            content_type=ContentType.objects.get_for_model(Producto),
        )
        if creacion:
            
            print(f"Permiso 'VER PRECIOS' creado automáticamente.")
        else:
            pass
        
        #PARA Apertura caja
        permiso, creacion = Permission.objects.get_or_create(
            codename="can_aperturar_caja",
            name="APERTURAR CAJA".upper(),
            content_type=ContentType.objects.get_for_model(CajaApertura),
        )
        permiso, creacion = Permission.objects.get_or_create(
            codename="can_cerrar_caja",
            name="CERRAR CAJA".upper(),
            content_type=ContentType.objects.get_for_model(CajaApertura),
        )
        permiso, creacion = Permission.objects.get_or_create(
            codename="can_ver_apertura_caja",
            name="VER APERTURA CAJA".upper(),
            content_type=ContentType.objects.get_for_model(CajaApertura),
        ) 
            #print(f"Permiso 'VER PRECIOS' ya existe.")
            
        #permiso de DETALLE ALMACEN 
        
        
        