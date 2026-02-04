from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.pagination import LimitOffsetPagination
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from apps.inventario.serializers.trasnsformaciones.transformacio_serializer import (
    TransformacionCreateSerializer,
    TransformacionListSerializer,
    TransformacionDetailSerializer
)

from apps.inventario.models import Transformacion

class TransformacionViewSet(viewsets.ViewSet):
    """
    ViewSet para manejar las transformaciones de inventario.
    Permite crear movimientos de transformación y merma.
    """
    pagination_class = LimitOffsetPagination

    @extend_schema(
        request=TransformacionCreateSerializer,
        responses={
            201: OpenApiResponse(description="Transformación creada exitosamente."),
            400: OpenApiResponse(description="Error en los datos proporcionados."),
        },
        description="Crear una nueva transformación o merma en el inventario."
    )
    def create(self, request):
        """
        Crear una nueva transformación o merma en el inventario.
        """
        #pasar este contexto al serializer
        serializer = TransformacionCreateSerializer(data=request.data, context={'request': request})
        try:
            if serializer.is_valid(raise_exception=True):
                movimiento = serializer.save()
                return Response(
                    {"detail": "Transformación creada exitosamente.", "movimiento_id":movimiento.id},
                    status=status.HTTP_201_CREATED
                )
        except Exception as e:
            return Response(
                {"detail": str(e), "error_code": "ERROR_TRANSFORMACION"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
    @extend_schema(
        parameters=[
            OpenApiParameter(name='almacen_id', description='Filtrar por ID del almacén', required=False, type=int),
            OpenApiParameter(name='almacen_nombre', description='Filtrar por nombre del almacén (búsqueda parcial)', required=False, type=str),
            OpenApiParameter(name='tipo', description='Filtrar por tipo de transformación (TRANSFORMACION o MERMA)', required=False, type=str),
        ],
        responses={200: TransformacionListSerializer(many=True)},
        description="Listar todas las transformaciones con paginación y filtros."
    )
    def list(self, request):
        
        almacen_user = request.user.almacen
        if almacen_user:
            queryset = Transformacion.objects.filter(almacen=almacen_user).select_related('almacen', 'created_by').order_by('-created_at')
        else:
        
            queryset = Transformacion.objects.all().select_related('almacen', 'created_by').order_by('-created_at')
        
        # Filtros
        almacen_id = request.query_params.get('almacen_id', None)
        almacen_nombre = request.query_params.get('almacen_nombre', None)
        tipo = request.query_params.get('tipo', None)
        
        if almacen_id:
            queryset = queryset.filter(almacen_id=almacen_id)
        
        if almacen_nombre:
            queryset = queryset.filter(almacen__nombre__icontains=almacen_nombre)
        
        if tipo:
            queryset = queryset.filter(tipo=tipo)
        
        # Paginación
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = TransformacionListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = TransformacionListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        responses={
            200: TransformacionDetailSerializer,
            404: OpenApiResponse(description="Transformación no encontrada.")
        },
        description="Obtener el detalle completo de una transformación con sus movimientos y productos."
    )
    def retrieve(self, request, pk=None):
        """
        Obtener el detalle completo de una transformación.
        Incluye los movimientos de salida (productos transformados) y entrada (productos nuevos).
        """
        try:
            # Optimized query with select_related and prefetch_related
            transformacion = Transformacion.objects.select_related(
                'almacen',
                'created_by',
                'movimiento_salida',
                'movimiento_entrada'
            ).prefetch_related(
                'movimiento_salida__productosMovimiento__producto__unidad_sat',
                'movimiento_salida__productosMovimiento__lote',
                'movimiento_entrada__productosMovimiento__producto__unidad_sat',
                'movimiento_entrada__productosMovimiento__lote'
            ).get(pk=pk)
            
            serializer = TransformacionDetailSerializer(transformacion)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Transformacion.DoesNotExist:
            return Response(
                {"detail": "Transformación no encontrada.", "error_code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"detail": str(e), "error_code": "ERROR_RETRIEVE_TRANSFORMACION"},
                status=status.HTTP_400_BAD_REQUEST
            )    
    