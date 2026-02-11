from django.db import migrations


def normalize_transferencia(apps, schema_editor):
    MetodoPago = apps.get_model('contabilidad', 'MetodoPago')

    # Corrige typo histórico
    MetodoPago.objects.filter(nombre__iexact='TRANFERENCIA').update(nombre='TRANSFERENCIA')

    # Asegura existencia del método correcto
    metodo, created = MetodoPago.objects.get_or_create(
        nombre='TRANSFERENCIA',
        defaults={
            'tipo': 'TRANSFERENCIA',
            'is_credito': False,
            'activo': True,
        },
    )

    # Homologa tipo en registros existentes
    if not created and (metodo.tipo or '').upper() != 'TRANSFERENCIA':
        metodo.tipo = 'TRANSFERENCIA'
        metodo.save(update_fields=['tipo'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('contabilidad', '0006_condicionpago'),
    ]

    operations = [
        migrations.RunPython(normalize_transferencia, noop_reverse),
    ]
