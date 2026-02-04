from apps.credito.models import CreditoCliente,CreditoProveedor
from django.contrib.contenttypes.models import ContentType

from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import Permission




@receiver(post_migrate)
def crear_permisos_inventario(sender, **kwargs):
    print("🔄 Creando permisos personalizados para apps.inventario...")
    models_str = [
        ('CreditoCliente', 'Credito del Cliente', CreditoCliente),
        ('CreditoProveedor', 'Credito del Proveedor', CreditoProveedor),
       
    ]
    
    for model_name_permiso, model_name_str, model_class in models_str:
        content_type = ContentType.objects.get_for_model(model_class)
    
        permisos = [
            (  f"can_view_{model_name_permiso}".lower(),         f"Ver {model_name_str}".upper()),
            #(f"can_update_{model_name_permiso}".lower(),  f"Actualizar {model_name_str}".upper()),
            #(f"can_create_{model_name_permiso}".lower(),       f"Crear {model_name_str}".upper()),
            #(f"can_delete_{model_name_permiso}".lower(),    f"Eliminar {model_name_str}".upper()),
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
                
    #permisos de abono al cliente
    content_type_cliente = ContentType.objects.get_for_model(CreditoCliente)
    permiso_abono_cliente, created = Permission.objects.get_or_create(
        codename='can_abonar_creditocliente',
        name='ABONAR CRÉDITO DE CLIENTE',
        content_type=content_type_cliente,
    )
    if created:
        print(f"Permiso 'ABONAR CRÉDITO DE CLIENTE' creado automáticamente.")
    else:
        print(f"Permiso 'ABONAR CRÉDITO DE CLIENTE' ya existe.")    
        
                
    #permisos de abono al proveedor
    content_type_proveedor = ContentType.objects.get_for_model(CreditoProveedor)
    permiso_abono, created = Permission.objects.get_or_create(
        codename='can_abonar_creditoproveedor',
        name='ABONAR CRÉDITO DE PROVEEDOR',
        content_type=content_type_proveedor,
    )
    if created:
        print(f"Permiso 'ABONAR CRÉDITO DE PROVEEDOR' creado automáticamente.")
    else:
        print(f"Permiso 'ABONAR CRÉDITO DE PROVEEDOR' ya existe.")
    
    
    