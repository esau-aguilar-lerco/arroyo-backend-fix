from django.db import migrations, models


def migrar_carga_a_programado(apps, schema_editor):
    EmbarqueReparto = apps.get_model('inventario', 'EmbarqueReparto')
    EmbarqueReparto.objects.filter(fase='CARGA').update(fase='PROGRAMADO')


def migrar_programado_a_carga(apps, schema_editor):
    EmbarqueReparto = apps.get_model('inventario', 'EmbarqueReparto')
    EmbarqueReparto.objects.filter(fase='PROGRAMADO').update(fase='CARGA')


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0036_alter_loteinventario_cantidad_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='embarquereparto',
            name='fase',
            field=models.CharField(
                choices=[
                    ('PROGRAMADO', 'PROGRAMADO'),
                    ('REPARTO', 'REPARTO'),
                    ('TERMINADO', 'TERMINADO'),
                    ('CANCELADO', 'CANCELADO'),
                ],
                default='PROGRAMADO',
                max_length=20,
            ),
        ),
        migrations.RunPython(
            migrar_carga_a_programado,
            reverse_code=migrar_programado_a_carga,
        ),
    ]
