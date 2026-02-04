from rest_framework import viewsets,permissions, status, filters
from rest_framework.response import Response


from ..models import RegimenFiscal, UnidadSat, MetodoPago

from apps.contabilidad.serializers.regimenSerializer import RegimenFiscalDetailSerializer
from apps.contabilidad.serializers.unidadSatSerializer import  UnidadSatMiniSerializer
from apps.contabilidad.serializers.metodoPagoSerializaer import MetodoPagoMiniSerializer

class RegimenFiscalViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = RegimenFiscal.objects.all()
    serializer_class = RegimenFiscalDetailSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['nombre','codigo']

    #permission_classes = [permissions.IsAuthenticated]
    pagination_class = None


class UnidadSatViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UnidadSat.objects.all()
    serializer_class = UnidadSatMiniSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['clave','nombre']
    #permission_classes = [permissions.IsAuthenticated]
    pagination_class = None


class MetodoPagoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MetodoPago.objects.exclude(is_credito=True)
    serializer_class = MetodoPagoMiniSerializer
    #permission_classes = [permissions.IsAuthenticated]
    pagination_class = None
    filter_backends = [filters.SearchFilter]
    search_fields = ['nombre']