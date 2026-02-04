from .data.info import CATEGORIAS_PRODUCTOS


from ..models import Categoria
from django.db.models.signals import post_migrate
#signal para despues de migrara

from django.dispatch import receiver


@receiver(post_migrate)
def crear_categoria(sender, **kwargs):
    
    
    for nombre in CATEGORIAS_PRODUCTOS:
        categoria, created = Categoria.objects.get_or_create(
            nombre=nombre
        )
        if created:
            print(f"Categoría  '{nombre}' creada automáticamente.")
            
        else:
            pass
            #print(f"Categoría de Cliente '{nombre}' ya existe.")