from rest_framework import viewsets, mixins, status, filters, serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action

from drf_spectacular.utils import extend_schema, OpenApiParameter, inline_serializer
from drf_spectacular.types import OpenApiTypes

from apps.base.models import BaseModel
from apps.base.serachFilter import MinimalSearchFilter
from apps.erp.models import GastosCompra
from apps.erp.serializers.compras_serializer import (
    GastosCompraCreateSerializer,
    CompraGastoListSerializer,
    CompraGastoRetrieveSerializer,
    GastosCompraMultipleCreateSerializer
)





class GastosCompraViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de gastos de compra
    
    Endpoints:
    - GET /api/gastos-compra/ - Listar gastos
    - POST /api/gastos-compra/ - Crear gasto
    - GET /api/gastos-compra/{id}/ - Detalle de gasto
    - PUT /api/gastos-compra/{id}/ - Actualizar gasto
    - DELETE /api/gastos-compra/{id}/ - Eliminar gasto
    """
    queryset = GastosCompra.objects.all()
    permission_classes = [IsAuthenticated]
    
    filter_backends = [MinimalSearchFilter, filters.OrderingFilter]
    search_fields = ['concepto', 'descripcion', 'compra__codigo']
    ordering_fields = ['created_at', 'monto']
    ordering = ['-created_at']

    def get_serializer_class(self):
        """Seleccionar serializer según la acción"""
        if self.action == 'create':
            return GastosCompraCreateSerializer
        elif self.action == 'retrieve':
            return CompraGastoRetrieveSerializer
        elif self.action in ['update', 'partial_update']:
            return GastosCompraCreateSerializer
        return CompraGastoListSerializer

    def get_queryset(self):
        """Optimizar consultas"""
        return (
            GastosCompra.objects
            .select_related('compra', 'created_by', 'updated_by')
            .exclude(status_model=BaseModel.STATUS_MODEL_DELETE)
        )

    @extend_schema(
        summary="Listar gastos de compra",
        description="""
        Lista todos los gastos de compra con opciones de filtrado.
        
        **Filtros disponibles:**
        - `compra`: ID de la compra
        - `dia_inicio`: Fecha inicio (YYYY-MM-DD)
        - `dia_fin`: Fecha fin (YYYY-MM-DD)
        - `search`: Búsqueda en concepto, descripción o código de compra
        """,
        parameters=[
            OpenApiParameter(
                name='compra',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='ID de la compra',
                required=False,
            ),
            OpenApiParameter(
                name='dia_inicio',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Fecha inicio (YYYY-MM-DD)',
                required=False,
            ),
            OpenApiParameter(
                name='dia_fin',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Fecha fin (YYYY-MM-DD)',
                required=False,
            ),
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Búsqueda en concepto, descripción o código de compra',
                required=False,
            ),
        ],
        responses={
            200: CompraGastoListSerializer(many=True),
        },
        tags=['Gastos de Compra']
    )
    def list(self, request, *args, **kwargs):
        """Listar gastos de compra"""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Filtros
        compra_id = request.query_params.get('compra')
        if compra_id:
            try:
                queryset = queryset.filter(compra_id=int(compra_id))
            except (ValueError, TypeError):
                pass
        
        # Filtros de fecha
        dia_inicio = request.query_params.get('dia_inicio')
        if dia_inicio:
            queryset = queryset.filter(created_at__date__gte=dia_inicio)
        
        dia_fin = request.query_params.get('dia_fin')
        if dia_fin:
            queryset = queryset.filter(created_at__date__lte=dia_fin)
        
        # Paginación
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Detalle de gasto",
        description="Obtiene el detalle completo de un gasto de compra.",
        responses={
            200: CompraGastoRetrieveSerializer,
            404: "Gasto no encontrado"
        },
        tags=['Gastos de Compra']
    )
    def retrieve(self, request, *args, **kwargs):
        """Obtener detalle de gasto"""
        instance = self.get_object()
        if instance.status_model == BaseModel.STATUS_MODEL_DELETE:
            return Response(
                {'detail': 'El gasto no existe o ha sido eliminado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Crear gasto de compra",
        description="Registra un nuevo gasto asociado a una compra.",
        request=GastosCompraCreateSerializer,
        responses={
            201: CompraGastoRetrieveSerializer,
            400: "Error de validación"
        },
        tags=['Gastos de Compra']
    )
    def create(self, request, *args, **kwargs):
        """Crear nuevo gasto"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Asignar created_by
        gasto = serializer.save(created_by=request.user)
        
        # Retornar con serializer de detalle
        response_serializer = CompraGastoRetrieveSerializer(gasto)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )

    @extend_schema(
        summary="Actualizar gasto",
        description="Actualiza un gasto de compra existente.",
        request=GastosCompraCreateSerializer,
        responses={
            200: CompraGastoRetrieveSerializer,
            400: "Error de validación"
        },
        tags=['Gastos de Compra']
    )
    def update(self, request, *args, **kwargs):
        """Actualizar gasto"""
        instance = self.get_object()
        serializer = GastosCompraCreateSerializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Asignar updated_by
        gasto = serializer.save(updated_by=request.user)
        
        response_serializer = CompraGastoRetrieveSerializer(gasto)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Actualizar gasto parcialmente",
        description="Actualiza parcialmente un gasto de compra.",
        request=GastosCompraCreateSerializer,
        responses={
            200: CompraGastoRetrieveSerializer,
            400: "Error de validación"
        },
        tags=['Gastos de Compra']
    )
    def partial_update(self, request, *args, **kwargs):
        """Actualizar gasto parcialmente"""
        instance = self.get_object()
        serializer = GastosCompraCreateSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        gasto = serializer.save(updated_by=request.user)
        
        response_serializer = CompraGastoRetrieveSerializer(gasto)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Eliminar gasto",
        description="Elimina lógicamente un gasto de compra.",
        responses={
            200: inline_serializer(
                name='GastoDeleteResponse',
                fields={'detail': serializers.CharField()}
            ),
        },
        tags=['Gastos de Compra']
    )
    def destroy(self, request, *args, **kwargs):
        """Eliminación lógica"""
        instance = self.get_object()
        
        instance.status_model = BaseModel.STATUS_MODEL_DELETE
        instance.save(update_fields=['status_model'])
        
        return Response(
            {'detail': 'Gasto eliminado exitosamente'},
            status=status.HTTP_200_OK
        )

    @extend_schema(
        summary="Crear múltiples gastos de compra",
        description="""
        Registra múltiples gastos de compra en una sola petición.
        
        **Ejemplo de request:**
        ```json
        {
            "gastos": [
                {
                    "compra": 1,
                    "concepto": "Flete",
                    "descripcion": "Transporte de mercancía",
                    "monto": 1500.00
                },
                {
                    "compra": 1,
                    "concepto": "Maniobras",
                    "descripcion": "Descarga de productos",
                    "monto": 500.00
                }
            ]
        }
        ```
        """,
        request=GastosCompraMultipleCreateSerializer,
        responses={
            201: inline_serializer(
                name='GastosMultipleCreateResponse',
                fields={
                    'detail': serializers.CharField(),
                    'gastos_creados': serializers.IntegerField(),
                    'gastos': CompraGastoRetrieveSerializer(many=True)
                }
            ),
            400: "Error de validación"
        },
        tags=['Gastos de Compra']
    )
    @action(detail=False, methods=['post'], url_path='crear-multiples')
    def crear_multiples(self, request, *args, **kwargs):
        """Crear múltiples gastos de compra"""
        gastos_data = request.data.get('gastos', [])
        
        if not gastos_data:
            return Response(
                {'detail': 'Debe proporcionar al menos un gasto en el array "gastos"'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not isinstance(gastos_data, list):
            return Response(
                {'detail': 'El campo "gastos" debe ser un array'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        gastos_creados = []
        errores = []
        
        for idx, gasto_data in enumerate(gastos_data):
            serializer = GastosCompraCreateSerializer(data=gasto_data)
            if serializer.is_valid():
                gasto = serializer.save(created_by=request.user)
                gastos_creados.append(gasto)
            else:
                errores.append({
                    'indice': idx,
                    'errores': serializer.errors
                })
        
        if errores:
            return Response(
                {
                    'detail': f'Se encontraron errores en {len(errores)} gasto(s)',
                    'gastos_creados': len(gastos_creados),
                    'errores': errores
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        response_serializer = CompraGastoRetrieveSerializer(gastos_creados, many=True)
        return Response(
            {
                'detail': f'Se crearon {len(gastos_creados)} gasto(s) exitosamente',
                'gastos_creados': len(gastos_creados),
                'gastos': response_serializer.data
            },
            status=status.HTTP_201_CREATED
        )
