from apps.inventario.models import EmbarqueReparto
from apps.erp.models import CajaApertura, Caja
from apps.usuarios.models import Usuario
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=EmbarqueReparto)
def iniciar_reparto(sender, instance, created, **kwargs):  
    # Evitar bucle infinito: si ya tiene apertura_caja asignada, no hacer nada
    if instance.fase == EmbarqueReparto.FASE_REPARTO and not instance.apertura_caja:
        caja_model = Caja.objects.filter(ruta=instance.ruta, status_model=Caja.STATUS_MODEL_ACTIVE).first()
        
        # Verificar si ya tiene una apertura de caja abierta
        apertura_caja = CajaApertura.objects.filter(
            is_abierta=True,
            caja=caja_model,
            usuario=instance.encargado
        ).first()
        
        if apertura_caja:
            # Usar update() para evitar disparar el signal nuevamente
            EmbarqueReparto.objects.filter(pk=instance.pk).update(apertura_caja=apertura_caja)
            print(f"El embarque {instance.id} ya tiene una apertura de caja asignada: {apertura_caja}")
            return apertura_caja
        
        # Crear una nueva apertura de caja para el usuario y la ruta del embarque
        print(f"Caja encontrada para la ruta {instance.ruta}: {caja_model}")
        if caja_model is None:
            print("No existe una caja asignada a la ruta del embarque.")
            raise Exception("No existe una caja asignada a la ruta del embarque.")
        
        nueva_apertura = CajaApertura.objects.create(
            caja=caja_model,
            usuario=instance.encargado,
            monto_inicial=0.0,
            is_abierta=True,
            created_by=instance.created_by
        )
        print(f"Nueva apertura de caja creada para el embarque {instance.id}: {nueva_apertura}")
        
        # Usar update() para evitar disparar el signal nuevamente
        EmbarqueReparto.objects.filter(pk=instance.pk).update(apertura_caja=nueva_apertura)
        return nueva_apertura