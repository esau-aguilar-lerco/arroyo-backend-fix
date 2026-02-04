"""
Serializers para solicitudes de traspaso entre almacenes.
"""

from .traspasoSolicitudSerializer import (
    SolicitudTraspasoDetalleSerializer,
    SolicitudTraspasoListSerializer,
    SolicitudTraspasoDetailSerializer,
    SolicitudTraspasoCreateUpdateSerializer,
    AprobarRechazarSolicitudSerializer
)

__all__ = [
    'SolicitudTraspasoDetalleSerializer',
    'SolicitudTraspasoListSerializer',
    'SolicitudTraspasoDetailSerializer',
    'SolicitudTraspasoCreateUpdateSerializer',
    'AprobarRechazarSolicitudSerializer',
]
