from django.db.models.signals import post_migrate
from django.dispatch import receiver
from apps.contabilidad.models import CondicionPago, MetodoPago, UnidadSat, RegimenFiscal

from .data.datos import REGIMENES_FISCALES, METODOS_PAGO, UNIDADES_SAT


@receiver(post_migrate)
def crear_condiciones_pago(sender, **kwargs):
    """Signal para crear las condiciones de pago por defecto"""
    CondicionPago.objects.get_or_create(nombre=CondicionPago.CONDICION_CONTADO)
    CondicionPago.objects.get_or_create(nombre=CondicionPago.CONDICION_CREDITO)
    print("[CONTABILIDAD post_migrate] Condiciones de pago creadas o ya existentes.")


#@receiver(post_migrate)
def cargar_metodos_pago(sender, **kwargs):
    """
    Signal para cargar los métodos de pago
    Se ejecuta después de cada migración
    """
    contador_creados = 0
    contador_existentes = 0
    
    for metodo_data in METODOS_PAGO:
        metodo, created = MetodoPago.objects.get_or_create(
            nombre=metodo_data['nombre'],
            defaults={
                'tipo': metodo_data['tipo'],
                'is_credito': metodo_data['is_credito'],
                'activo': True
            }
        )
        
        if created:
            contador_creados += 1
        else:
            # Actualizar si cambió algo
            actualizado = False
            if metodo.tipo != metodo_data['tipo']:
                metodo.tipo = metodo_data['tipo']
                actualizado = True
            if metodo.is_credito != metodo_data['is_credito']:
                metodo.is_credito = metodo_data['is_credito']
                actualizado = True
            
            if actualizado:
                metodo.save()
                print(f"  ↻ Método de pago {metodo.nombre} actualizado")
            contador_existentes += 1
    
    print(f"[CONTABILIDAD post_migrate] Métodos de pago: {contador_creados} creados, {contador_existentes} ya existentes.")


#@receiver(post_migrate)
def cargar_regimenes_fiscales(sender, **kwargs):
    """
    Signal para cargar los regímenes fiscales del SAT
    Se ejecuta después de cada migración
    """
    
    contador_creados = 0
    contador_existentes = 0
    
    for regimen_data in REGIMENES_FISCALES:
        regimen, created = RegimenFiscal.objects.get_or_create(
            codigo=regimen_data['codigo'],
            defaults={'nombre': regimen_data['nombre']}
        )
        
        if created:
            contador_creados += 1
        else:
            # Actualizar el nombre si cambió
            if regimen.nombre != regimen_data['nombre']:
                regimen.nombre = regimen_data['nombre']
                regimen.save()
                print(f"  ↻ Régimen {regimen.codigo} actualizado")
            contador_existentes += 1
    
    print(f"[CONTABILIDAD post_migrate] Regímenes fiscales: {contador_creados} creados, {contador_existentes} ya existentes.")


#@receiver(post_migrate)
def cargar_unidades_sat(sender, **kwargs):
    """
    Signal para cargar las unidades SAT
    Se ejecuta después de cada migración
    """
    
    contador_creados = 0
    contador_existentes = 0
    
    for unidad_data in UNIDADES_SAT:
        unidad, created = UnidadSat.objects.get_or_create(
            clave=unidad_data['clave'],
            defaults={'nombre': unidad_data['nombre']}
        )
        
        if created:
            contador_creados += 1
        else:
            # Actualizar el nombre si cambió
            if unidad.nombre != unidad_data['nombre']:
                unidad.nombre = unidad_data['nombre']
                unidad.save()
                print(f"  ↻ Unidad SAT {unidad.clave} actualizada")
            contador_existentes += 1
    
    print(f"[CONTABILIDAD post_migrate] Unidades SAT: {contador_creados} creadas, {contador_existentes} ya existentes.")

"""
@receiver(post_migrate)
def crear_empresa_por_defecto(sender, **kwargs):
   
    # Importar aquí para evitar problemas de importación circular
    from apps.erp.models import Empresa
    
    # Verificar si ya existe alguna empresa
    if Empresa.objects.exists():
        print("[ERP post_migrate] Ya existe al menos una empresa registrada.")
        return
    
    # Obtener el régimen fiscal 601 (más común para empresas)
    try:
        regimen_601 = RegimenFiscal.objects.get(codigo='601')
    except RegimenFiscal.DoesNotExist:
        regimen_601 = None
        print("[ERP post_migrate] ⚠️ Advertencia: No se encontró el régimen fiscal 601")
    
    # Crear empresa por defecto
    empresa = Empresa.objects.create(
        nombre="PESCADOS Y MARISCOS ARROYO",
        rfc="XXXXXXX",
        telefono="",
        email="",
        cuenta_clave="",
        regimen_fiscal=regimen_601,
        direccion_fiscal=""
    )
    
    print(f"[ERP post_migrate] ✓ Empresa por defecto creada: {empresa.nombre} (ID: {empresa.id})")
    print("  ⚠️ Importante: Actualiza los datos de la empresa desde el panel de administración.")
    
"""