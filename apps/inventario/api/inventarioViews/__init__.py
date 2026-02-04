"""
Módulo de vistas para consultas de inventario.
Contiene APIs optimizadas para consultar stock en almacenes.
"""

from .inventarioAlmacenViews import (
    InventarioAlmacenView,
    InventarioTodosAlmacenesView
)

__all__ = [
    'InventarioAlmacenView',
    'InventarioTodosAlmacenesView',
]
