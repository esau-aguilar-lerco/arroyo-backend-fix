from rest_framework import viewsets, mixins, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

# MODELS
from apps.base.models import BaseModel
from ..models import UnidadVehicular

# SERIALIZERS
from ..serializers.unidad_vehicular_serializer import UnidadVehicularSerializer, UnidadVehicularMiniSerializer

# FILTERS
from apps.base.serachFilter import MinimalSearchFilter


class UnidadVehicularViewSet(viewsets.ModelViewSet):
    """
    ViewSet completo para CRUD de unidades vehiculares
    """
    queryset = UnidadVehicular.objects.exclude(status_model=BaseModel.STATUS_MODEL_DELETE).order_by('-created_at')
    serializer_class = UnidadVehicularSerializer
    filter_backends = [MinimalSearchFilter, filters.OrderingFilter]
    search_fields = ['nombre', 'placas', 'marca', 'modelo']
    ordering_fields = ['nombre', 'placas', 'marca', 'modelo', 'anio', 'capacidad_carga', 'created_at']
    ordering = ['-created_at']

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='tipo',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filtrar por tipo de vehículo',
                required=False,
                enum=['CAMIÓN', 'CAMIONETA', 'TRÁILER', 'OTRO']
            ),
            OpenApiParameter(
                name='marca',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filtrar por marca del vehículo',
                required=False,
            ),
            OpenApiParameter(
                name='anio',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Filtrar por año del vehículo',
                required=False,
            ),
            OpenApiParameter(
                name='capacidad_min',
                type=OpenApiTypes.NUMBER,
                location=OpenApiParameter.QUERY,
                description='Filtrar por capacidad mínima en toneladas',
                required=False,
            ),
            OpenApiParameter(
                name='capacidad_max',
                type=OpenApiTypes.NUMBER,
                location=OpenApiParameter.QUERY,
                description='Filtrar por capacidad máxima en toneladas',
                required=False,
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        """Lista todas las unidades vehiculares con filtros avanzados"""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Filtros personalizados
        tipo = request.query_params.get('tipo')
        marca = request.query_params.get('marca')
        anio = request.query_params.get('anio')
        capacidad_min = request.query_params.get('capacidad_min')
        capacidad_max = request.query_params.get('capacidad_max')
        
        if tipo:
            queryset = queryset.filter(tipo=tipo)
        
        if marca:
            queryset = queryset.filter(marca__icontains=marca)
        
        if anio:
            try:
                anio = int(anio)
                queryset = queryset.filter(anio=anio)
            except ValueError:
                pass
        
        if capacidad_min:
            try:
                capacidad_min = float(capacidad_min)
                queryset = queryset.filter(capacidad_carga__gte=capacidad_min)
            except ValueError:
                pass
        
        if capacidad_max:
            try:
                capacidad_max = float(capacidad_max)
                queryset = queryset.filter(capacidad_carga__lte=capacidad_max)
            except ValueError:
                pass
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='tipos-disponibles')
    def tipos_disponibles(self, request):
        """Obtiene los tipos de vehículos disponibles"""
        tipos = [{'value': choice[0], 'label': choice[1]} for choice in UnidadVehicular.TIPO_CHOICES]
        return Response({
            'tipos': tipos,
            'total': len(tipos)
        })

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if self.is_respuesta_404():
            return self.respuesta_404()
        instance.status_model = BaseModel.STATUS_MODEL_DELETE
        instance.save(update_fields=['status_model'])
        return Response({"detail": "Eliminado correctamente."}, status=status.HTTP_200_OK)

  


class UnidadVehicularMiniViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    ViewSet mini para listar unidades vehiculares básicas
    """
    queryset = UnidadVehicular.objects.exclude(status_model=BaseModel.STATUS_MODEL_DELETE).order_by('nombre')
    serializer_class = UnidadVehicularMiniSerializer

    filter_backends = [MinimalSearchFilter]
    search_fields = ['nombre', 'placas', 'marca', 'modelo']
    pagination_class = None

    def get_queryset(self):
        queryset = super().get_queryset()
        tipo = self.request.query_params.get('tipo')
        if tipo:
            queryset = queryset.filter(tipo=tipo)
        return queryset

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='tipo',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filtrar por tipo de vehículo',
                required=False,
                enum=['CAMIÓN', 'CAMIONETA', 'TRÁILER', 'OTRO']
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        """Lista básica de unidades vehiculares"""
        return super().list(request, *args, **kwargs)