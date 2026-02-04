from django.db.models import Q, Count
from rest_framework import status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from drf_spectacular.utils import extend_schema, OpenApiParameter, inline_serializer
from rest_framework import serializers

from apps.inventario.models import ProductosSolicitud
from apps.inventario.serializers.productos_solicitud_serializer import (
    ProductosSolicitudSerializer, 
    ProductosSolicitudMiniSerializer
)


class ProductosSolicitudViewSet(ModelViewSet):
    """
    ViewSet para manejar las solicitudes de productos.
    
    Permite:
    - Listar todas las solicitudes con filtros avanzados
    - Crear nuevas solicitudes de productos
    - Obtener detalles de una solicitud específica
    - Actualizar solicitudes existentes
    - Eliminar solicitudes
    - Acciones especiales: cambiar estado, estadísticas
    """
    queryset = ProductosSolicitud.objects.select_related(
        'producto'
    ).all()
    serializer_class = ProductosSolicitudSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['producto__nombre', 'producto__codigo']
    ordering_fields = ['created_at', 'cantidad', 'fase']
    ordering = ['-created_at']

    def get_queryset(self):
        """Aplicar filtros personalizados"""
        queryset = super().get_queryset()
        
        # Filtros personalizados por query params
        fase = self.request.query_params.get('fase')
        if fase:
            queryset = queryset.filter(fase=fase)
                
        producto = self.request.query_params.get('producto')
        if producto:
            try:
                queryset = queryset.filter(producto_id=int(producto))
            except (ValueError, TypeError):
                pass
        
        return queryset

    def get_serializer_class(self):
        """Retorna el serializer apropiado según la acción"""
        if self.action == 'list':
            return ProductosSolicitudMiniSerializer
        return ProductosSolicitudSerializer

    def perform_create(self, serializer):
        """Crear solicitud asignando el usuario creador"""
        serializer.save()

    @extend_schema(
        summary="Listar solicitudes de productos",
        description="Obtiene una lista paginada de todas las solicitudes de productos con filtros avanzados",
        parameters=[
            OpenApiParameter(
                name='fase',
                description='Filtrar por fase de la solicitud',
                enum=['SOLICITUD', 'ATENDIDO', 'CANCELADO'],
                type=str
            ),
            OpenApiParameter(
                name='motivo',
                description='Filtrar por motivo de la solicitud',
                enum=['BAJA EXISTENCIA', 'PREVENTA INCOMPLETA'],
                type=str
            ),
            OpenApiParameter(
                name='almacen',
                description='Filtrar por ID del almacén',
                type=int
            ),
            OpenApiParameter(
                name='producto',
                description='Filtrar por ID del producto solicitado',
                type=int
            ),
            OpenApiParameter(
                name='search',
                description='Buscar en nombre del producto o código',
                type=str
            ),
           
        ],
        responses={
            200: ProductosSolicitudMiniSerializer(many=True),
            400: inline_serializer(
                name='ValidationError',
                fields={'detail': serializers.CharField()}
            )
        },
        tags=['Solicitudes de Productos']
    )
    def list(self, request, *args, **kwargs):
        """Lista todas las solicitudes con filtros y paginación"""
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Crear nueva solicitud de producto",
        description="Crea una nueva solicitud de producto.",
        request=ProductosSolicitudSerializer,
        responses={
            201: ProductosSolicitudSerializer,
            400: inline_serializer(
                name='ValidationError',
                fields={'detail': serializers.CharField()}
            )
        },
        tags=['Solicitudes de Productos']
    )
    def create(self, request, *args, **kwargs):
        """Crea una nueva solicitud de producto"""
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Obtener detalles de solicitud",
        description="Obtiene los detalles completos de una solicitud específica",
        responses={
            200: ProductosSolicitudSerializer,
            404: inline_serializer(
                name='NotFound',
                fields={'detail': serializers.CharField()}
            )
        },
        tags=['Solicitudes de Productos']
    )
    def retrieve(self, request, *args, **kwargs):
        """Obtiene una solicitud específica"""
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Actualizar solicitud completa",
        description="Actualiza todos los campos de una solicitud existente",
        request=ProductosSolicitudSerializer,
        responses={
            200: ProductosSolicitudSerializer,
            400: inline_serializer(
                name='ValidationError',
                fields={'detail': serializers.CharField()}
            ),
            404: inline_serializer(
                name='NotFound',
                fields={'detail': serializers.CharField()}
            )
        },
        tags=['Solicitudes de Productos']
    )
    def update(self, request, *args, **kwargs):
        """Actualiza una solicitud completa"""
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary="Actualizar solicitud parcial",
        description="Actualiza campos específicos de una solicitud existente",
        request=ProductosSolicitudSerializer,
        responses={
            200: ProductosSolicitudSerializer,
            400: inline_serializer(
                name='ValidationError',
                fields={'detail': serializers.CharField()}
            ),
            404: inline_serializer(
                name='NotFound',
                fields={'detail': serializers.CharField()}
            )
        },
        tags=['Solicitudes de Productos']
    )
    def partial_update(self, request, *args, **kwargs):
        """Actualiza parcialmente una solicitud"""
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary="Eliminar solicitud",
        description="Elimina una solicitud de producto del sistema",
        responses={
            204: None,
            404: inline_serializer(
                name='NotFound',
                fields={'detail': serializers.CharField()}
            )
        },
        tags=['Solicitudes de Productos']
    )
    def destroy(self, request, *args, **kwargs):
        """Elimina una solicitud"""
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        summary="Cambiar fase de solicitud",
        description="Cambia la fase de una solicitud específica",
        request=inline_serializer(
            name='CambiarFaseRequest',
            fields={
                'fase': serializers.ChoiceField(
                    choices=['SOLICITUD', 'ATENDIDO', 'CANCELADO'],
                    help_text="Nueva fase para la solicitud"
                ),
                'observaciones': serializers.CharField(
                    required=False, 
                    help_text="Observaciones adicionales sobre el cambio de fase"
                )
            }
        ),
        responses={
            200: ProductosSolicitudSerializer,
            400: inline_serializer(
                name='ValidationError',
                fields={'detail': serializers.CharField()}
            ),
            404: inline_serializer(
                name='NotFound',
                fields={'detail': serializers.CharField()}
            )
        },
        tags=['Solicitudes de Productos']
    )
    @action(detail=True, methods=['patch'])
    def cambiar_fase(self, request, pk=None):
        """Cambia la fase de una solicitud"""
        try:
            solicitud = self.get_object()
            nueva_fase = request.data.get('fase')
            observaciones = request.data.get('observaciones', '')
            
            if not nueva_fase:
                return Response(
                    {'detail': 'El campo fase es requerido'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if nueva_fase not in ['SOLICITUD', 'ATENDIDO', 'CANCELADO']:
                return Response(
                    {'detail': 'Fase no válida'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validar transiciones de fase
            transiciones_validas = {
                'SOLICITUD': ['ATENDIDO', 'CANCELADO'],
                'ATENDIDO': ['CANCELADO'],  # Solo se puede cancelar una vez atendida
                'CANCELADO': ['SOLICITUD']  # Se puede reactivar a solicitud
            }
            
            if nueva_fase not in transiciones_validas.get(solicitud.fase, []):
                return Response(
                    {'detail': f'No se puede cambiar de {solicitud.fase} a {nueva_fase}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Actualizar fase
            solicitud.fase = nueva_fase
            solicitud.save()
            
            serializer = self.get_serializer(solicitud)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'detail': f'Error al cambiar fase: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Cambiar fase de múltiples solicitudes",
        description="Cambia la fase de múltiples solicitudes de forma masiva. Acepta un array de IDs o un array de objetos con ID.",
        request=inline_serializer(
            name='CambiarFaseMasivoRequest',
            fields={
                'solicitudes': serializers.ListField(
                    child=serializers.JSONField(),
                    help_text="Array de IDs (enteros) o objetos con 'id'. Ejemplos: [1, 2, 3] o [{'id': 1}, {'id': 2}]"
                ),
                'fase': serializers.ChoiceField(
                    choices=['SOLICITUD', 'ATENDIDO', 'CANCELADO'],
                    help_text="Nueva fase para todas las solicitudes"
                )
            }
        ),
        responses={
            200: inline_serializer(
                name='CambiarFaseMasivoResponse',
                fields={
                    'exitosas': serializers.IntegerField(help_text="Cantidad de solicitudes actualizadas exitosamente"),
                    'fallidas': serializers.IntegerField(help_text="Cantidad de solicitudes que fallaron"),
                    'detalles': serializers.ListField(
                        child=inline_serializer(
                            name='DetalleResultado',
                            fields={
                                'id': serializers.IntegerField(),
                                'fase': serializers.CharField(),
                                'mensaje': serializers.CharField()
                            }
                        )
                    ),
                    'solicitudes_actualizadas': ProductosSolicitudMiniSerializer(many=True)
                }
            ),
            400: inline_serializer(
                name='ValidationError',
                fields={'detail': serializers.CharField()}
            )
        },
        tags=['Solicitudes de Productos']
    )
    @action(detail=False, methods=['patch'], url_path='cambiar-fase-masivo')
    def cambiar_fase_masivo(self, request):
        """Cambia la fase de múltiples solicitudes de forma masiva"""
        try:
            solicitudes_data = request.data.get('solicitudes', [])
            nueva_fase = request.data.get('fase')
            #observaciones = request.data.get('observaciones', '')
            
            # Validaciones básicas
            if not solicitudes_data:
                return Response(
                    {'detail': 'El campo solicitudes es requerido y no puede estar vacío'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not nueva_fase:
                return Response(
                    {'detail': 'El campo fase es requerido'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if nueva_fase not in ['SOLICITUD', 'ATENDIDO', 'CANCELADO']:
                return Response(
                    {'detail': 'Fase no válida'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Extraer IDs de las solicitudes
            solicitud_ids = []
            for item in solicitudes_data:
                try:
                    if isinstance(item, int):
                        # Si es un entero directo: [1, 2, 3]
                        solicitud_ids.append(item)
                    elif isinstance(item, dict) and 'id' in item:
                        # Si es un objeto con ID: [{'id': 1}, {'id': 2}]
                        solicitud_ids.append(int(item['id']))
                    else:
                        # Formato no válido
                        return Response(
                            {'detail': f'Formato no válido para solicitud: {item}. Use enteros o objetos con "id"'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                except (ValueError, TypeError):
                    return Response(
                        {'detail': f'ID no válido: {item}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            if not solicitud_ids:
                return Response(
                    {'detail': 'No se encontraron IDs válidos en las solicitudes'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Obtener las solicitudes que existen
            solicitudes_existentes = ProductosSolicitud.objects.filter(
                id__in=solicitud_ids
            )
            
            # Resultados del procesamiento
            exitosas = 0
            fallidas = 0
            detalles = []
            solicitudes_actualizadas = []
            
            # Definir transiciones válidas
            transiciones_validas = {
                'SOLICITUD': ['ATENDIDO', 'CANCELADO'],
                'ATENDIDO': ['CANCELADO'],  # Solo se puede cancelar una vez atendida
                'CANCELADO': ['SOLICITUD']  # Se puede reactivar a solicitud
            }
            
            # Procesar cada solicitud
            for solicitud_id in solicitud_ids:
                try:
                    # Buscar la solicitud
                    solicitud = solicitudes_existentes.filter(id=solicitud_id).first()
                    
                    if not solicitud:
                        fallidas += 1
                        detalles.append({
                            'id': solicitud_id,
                            'fase': 'ERROR',
                            'mensaje': 'Solicitud no encontrada'
                        })
                        continue
                    
                    # Validar transición de fase
                    if nueva_fase not in transiciones_validas.get(solicitud.fase, []):
                        fallidas += 1
                        detalles.append({
                            'id': solicitud_id,
                            'fase': 'ERROR',
                            'mensaje': f'No se puede cambiar de {solicitud.fase} a {nueva_fase}'
                        })
                        continue
                    
                    # Actualizar la solicitud
                    fase_anterior = solicitud.fase
                    solicitud.fase = nueva_fase
                    solicitud.save()
                    
                    exitosas += 1
                    solicitudes_actualizadas.append(solicitud)
                    detalles.append({
                        'id': solicitud_id,
                        'fase': 'EXITOSO',
                        'mensaje': f'Fase cambiada de {fase_anterior} a {nueva_fase}'
                    })
                    
                except Exception as e:
                    fallidas += 1
                    detalles.append({
                        'id': solicitud_id,
                        'fase': 'ERROR',
                        'mensaje': f'Error interno: {str(e)}'
                    })
            
            # Preparar respuesta
            response_data = {
                'exitosas': exitosas,
                'fallidas': fallidas,
                'detalles': detalles,
                'solicitudes_actualizadas': ProductosSolicitudMiniSerializer(
                    solicitudes_actualizadas, 
                    many=True
                ).data
            }
            
            # Determinar el status code según los resultados
            if exitosas > 0 and fallidas == 0:
                status_code = status.HTTP_200_OK
            elif exitosas > 0 and fallidas > 0:
                status_code = status.HTTP_207_MULTI_STATUS  # Parcialmente exitoso
            else:
                status_code = status.HTTP_400_BAD_REQUEST  # Todas fallaron
            
            return Response(response_data, status=status_code)
            
        except Exception as e:
            return Response(
                {'detail': f'Error interno del servidor: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )