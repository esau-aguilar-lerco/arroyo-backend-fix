import pandas as pd
from django.db.models.signals import post_migrate
from django.dispatch import receiver
import time
from django.conf import settings
import chardet

from .models import Estado, Municipio, CodigoPostal, Colonia

@receiver(post_migrate)
def insertar_datos_iniciales(sender, **kwargs):
    try:
        if settings.APPLY_LOAD_SEPOMEX:
            # Iniciar el temporizador
            start_time = time.time()
            path = r'catalogos/CPdescarga.txt'
            #df = pd.read_csv(path, delimiter="|",encoding="latin1")
            with open(path, "rb") as f:
                result = chardet.detect(f.read(10000))  # Analiza los primeros 10,000 bytes
                print("Encoding detectado:", result["encoding"])
            df = pd.read_csv(path, delimiter="|", encoding=result["encoding"])
            columnas_a_convertir = ['d_asenta','D_mnpio','d_estado']
            df[columnas_a_convertir] = df[columnas_a_convertir].apply(lambda x: x.str.strip().str.upper())
            
                # Insertar Estados
            for _, row in df[['d_estado', 'c_estado']].drop_duplicates().iterrows():
                estado, created = Estado.objects.get_or_create(
                    id=row['c_estado'],
                    nombre=row['d_estado'],
                    clave=row['c_estado']
                )
            print(f"Tiempo de ejecución: {time.time() - start_time} segundos para estados")

            # Insertar Municipios
            for _, row in df[['D_mnpio', 'c_estado']].drop_duplicates().iterrows():
                estado = Estado.objects.get(id=row['c_estado'])  # Obtener el estado

                # Buscar municipios con el mismo nombre y estado
                municipios = Municipio.objects.filter(nombre=row['D_mnpio'], estado=estado)

                if municipios.exists():
                    municipio = municipios.first()  # Obtener el primer municipio si existe
                    print(f"El municipio {row['D_mnpio']} ya existe en la base de datos.")
                else:
                    municipio = Municipio.objects.create(  # Crear el municipio si no existe
                        nombre=row['D_mnpio'],
                        estado=estado
                    )
            print(f"Tiempo de ejecución: {time.time() - start_time} segundos para municipios")

            ## Insertar Códigos Postales 
            for _, row in df[['d_codigo', 'd_zona']].drop_duplicates().iterrows():
                codigo_postal, created = CodigoPostal.objects.get_or_create(
                codigo_postal=row['d_codigo'],
                defaults={'zona': row['d_zona']}  # Solo se inserta la zona si el registro es nuevo
            )
            print(f"Tiempo de ejecución: {time.time() - start_time} segundos para códigos postales")

            # Insertar Colonias
            for _, row in df[['d_asenta', 'd_tipo_asenta', 'd_codigo', 'D_mnpio','c_estado']].drop_duplicates().iterrows():
                # Buscar el municipio correspondiente
                municipio = Municipio.objects.filter(nombre=row['D_mnpio'],estado=row['c_estado']).first()  # Usamos filter() en lugar de get()
                if not municipio:
                    # Si no existe el municipio, puedes decidir si lo creas aquí
                    municipio = Municipio.objects.create(
                        nombre=row['D_mnpio'],
                        estado=Estado.objects.get(nombre=row['d_estado'])  # Suponiendo que también debes obtener el estado
                    )

                # Buscar o crear el código postal
                codigo_postal = CodigoPostal.objects.get(codigo_postal=row['d_codigo'])
                # Crear o obtener la colonia
                colonia, created = Colonia.objects.get_or_create(
                    d_asenta=row['d_asenta'],
                    tipo_asentamiento=row['d_tipo_asenta'],
                    municipio=municipio,
                    codigo_postal=codigo_postal
                )
            #print(f"Tiempo de ejecución: {hours} horas, {minutes} minutos, {seconds} segundos")

            end_time = time.time()
            elapsed_time = end_time - start_time

            # Imprimir el tiempo que tardó
            # Convertir el tiempo en horas, minutos y segundos
            hours = int(elapsed_time // 3600)
            minutes = int((elapsed_time % 3600) // 60)
            seconds = int(elapsed_time % 60)

            # Imprimir el tiempo en formato HH:MM:SS
            print(f"Tiempo de ejecución: {hours} horas, {minutes} minutos, {seconds} segundos")
        else:
            print("No se aplicó la carga de datos inicial. Cambia la Variable APPLY_LOAD_SEPOMEX a True")
    except Exception as e:
        print(f"Ups! ocurrio un Error -> {e}")
    
    exit()