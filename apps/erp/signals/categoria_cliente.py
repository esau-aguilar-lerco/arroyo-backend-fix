from ..models import CategoriaCliente
from django.db.models.signals import post_migrate
#signal para despues de migrara

from django.dispatch import receiver


@receiver(post_migrate)
def crear_categoria_cliente(sender, **kwargs):
    LIST = [
        ('BRONCE', 1, 4999),
        ('PLATA', 5000, 49999),
        ('ORO', 50000, 149999),
        ('PLATINO', 150000, 499999),
        ('DIAMANTE', 300000, 500000),
    ]
    
    for nombre, limite_inferior, limite_superior in LIST:
        categoria, created = CategoriaCliente.objects.get_or_create(
            nombre=nombre
        )
        if created:
            categoria.limite_credito_min = limite_inferior
            categoria.limite_credito_max = limite_superior
            categoria.save()
            print(f"Categoría de Cliente '{nombre}' creada automáticamente.")
        else:
            pass
            #print(f"Categoría de Cliente '{nombre}' ya existe.")