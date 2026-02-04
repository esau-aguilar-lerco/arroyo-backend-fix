from apps.inventario.models import MovimientoInventario, ProductosMovimiento
from django.db.models import Sum,Q
from django.db import transaction


def listar_movimientos(almacen_origen=None,almacen_destino=None,tipo=None,movimiento=None,fase=None):
    """
    Función para listar movimientos de entrada de inventario para un almacén específico
    """
    base_query = MovimientoInventario.objects.all()
    if almacen_origen:
        base_query = base_query.filter(almacen=almacen_origen)
    if almacen_destino:
        base_query = base_query.filter(almacen_destino=almacen_destino)
    if tipo:
        base_query = base_query.filter(tipo=tipo)
    if movimiento:
        base_query = base_query.filter(movimiento=movimiento)
    if fase:
        base_query = base_query.filter(fase=fase)
    
    return base_query.order_by('-created_at')