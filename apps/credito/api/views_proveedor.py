from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Sum, Count
from django.utils import timezone
from datetime import timedelta

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from apps.base.serachFilter import MinimalSearchFilter
from apps.credito.models import CreditoProveedor, PagosCreditoProveedor
from apps.credito.serializers.credito_proveedor import (
    CreditoProveedorSerializer,
    CreditoProveedorMiniSerializer,
    CreditoProveedorListSerializer,
    PagosCreditoProveedorSerializer,
    PagoCreditoProveedorCreateSingularSerializer,
    PagoCreditoProveedorCreateMasivoSerializer,
)


class CreditoProveedorMiniViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    ViewSet simplificado para listar créditos de proveedor sin paginación
    """
    serializer_class = CreditoProveedorMiniSerializer
    pagination_class = None
    search_fields = ['proveedor__nombre', 'proveedor__codigo']
    filter_backends = [MinimalSearchFilter]
    
    def get_queryset(self):
        """Queryset con filtro opcional por proveedor"""
        queryset = CreditoProveedor.objects.all().select_related('proveedor').order_by('created_at')
        
        # Filtrar por proveedor si se proporciona
        proveedor_id = self.request.query_params.get('proveedor')
        if proveedor_id:
            queryset = queryset.filter(proveedor_id=proveedor_id)
        
        # Filtrar por activos (no pagados)
        activos = self.request.query_params.get('activos')
        if activos and activos.lower() == 'true':
            queryset = queryset.filter(is_pagado=False)
        
        # Filtrar por vencidos
        vencidos = self.request.query_params.get('vencidos')
        if vencidos and vencidos.lower() == 'true':
            from django.utils import timezone
            hoy = timezone.now().date()
            queryset = queryset.filter(is_pagado=False, fecha_vencimiento__lt=hoy)
        
        # Filtrar por pagados
        pagados = self.request.query_params.get('pagados')
        if pagados:
            flag = pagados.lower() == 'true'
            queryset = queryset.filter(is_pagado=flag)
        
        return queryset


class CreditoProveedorViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    ViewSet para gestión de créditos de proveedores
    
    Endpoints:
    - GET /api/creditos-proveedor/ - Listar créditos con filtros
    - GET /api/creditos-proveedor/{id}/ - Detalle de crédito con historial de pagos
    - GET /api/creditos-proveedor/vencidos/ - Créditos vencidos
    - GET /api/creditos-proveedor/activos/ - Créditos activos
    - GET /api/creditos-proveedor/por_proveedor/{proveedor_id}/ - Créditos de un proveedor
    - GET /api/creditos-proveedor/estadisticas/ - Estadísticas generales
    - GET /api/creditos-proveedor/estadisticas-proveedor/{proveedor_id}/ - Estadísticas por proveedor
    """
    queryset = CreditoProveedor.objects.select_related(
        'proveedor', 'created_by', 'updated_by'
    ).prefetch_related('pagos_proveedor').order_by('created_at')
    
    search_fields = ['proveedor__nombre', 'proveedor__codigo']
    filter_backends = [MinimalSearchFilter]

    def get_serializer_class(self):
        """Seleccionar serializer según la acción"""
        if self.action == 'retrieve':
            return CreditoProveedorSerializer
        return CreditoProveedorMiniSerializer
    
    @extend_schema(
        summary="Listar créditos de proveedores",
        description="""
        Lista todos los créditos de proveedores con opciones de filtrado avanzado.
        
        **Filtros disponibles (query params):**
        - `proveedor`: ID del proveedor
        - `estado`: Estado del crédito (ACTIVA, PAGADA)
        - `is_pagado`: true/false (si está liquidado)
        - `fecha_desde`: Fecha inicio (YYYY-MM-DD)
        - `fecha_hasta`: Fecha fin (YYYY-MM-DD)
        - `dia_inicio`: Fecha inicio alternativa (YYYY-MM-DD)
        - `dia_fin`: Fecha fin alternativa (YYYY-MM-DD)
        - `vencidos`: true/false (solo créditos vencidos)
        - `search`: Búsqueda por nombre o código de proveedor
        """,
        parameters=[
            OpenApiParameter(
                name='proveedor',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='ID del proveedor',
                required=False
            ),
            OpenApiParameter(
                name='estado',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Estado del crédito (ACTIVA, PAGADA)',
                required=False,
                enum=['ACTIVA', 'PAGADA']
            ),
            OpenApiParameter(
                name='is_pagado',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='Filtrar por créditos liquidados',
                required=False
            ),
            OpenApiParameter(
                name='fecha_desde',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Fecha desde (YYYY-MM-DD)',
                required=False
            ),
            OpenApiParameter(
                name='fecha_hasta',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Fecha hasta (YYYY-MM-DD)',
                required=False
            ),
            OpenApiParameter(
                name='dia_inicio',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Fecha inicio alternativa (YYYY-MM-DD)',
                required=False
            ),
            OpenApiParameter(
                name='dia_fin',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Fecha fin alternativa (YYYY-MM-DD)',
                required=False
            ),
            OpenApiParameter(
                name='vencidos',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='Solo créditos vencidos (true/false)',
                required=False
            ),
        ],
        responses={
            200: CreditoProveedorMiniSerializer(many=True),
        },
        tags=['Créditos Proveedor']
    )
    def list(self, request, *args, **kwargs):
        """Listar créditos con filtros"""
        queryset = self.get_queryset()
        
        # Obtener filtros desde query params
        proveedor_id = request.query_params.get('proveedor')
        estado = request.query_params.get('estado')
        is_pagado = request.query_params.get('is_pagado')
        fecha_desde = request.query_params.get('fecha_desde') or request.query_params.get('dia_inicio')
        fecha_hasta = request.query_params.get('fecha_hasta') or request.query_params.get('dia_fin')
        vencidos = request.query_params.get('vencidos')
        
        # Aplicar filtros
        if vencidos and vencidos.lower() == 'true':
            hoy = timezone.now().date()
            queryset = queryset.filter(
                is_pagado=False,
                fecha_vencimiento__lt=hoy
            )
        
        if proveedor_id:
            queryset = queryset.filter(proveedor_id=proveedor_id)
        
        if estado:
            queryset = queryset.filter(estado=estado)
        
        if is_pagado is not None:
            queryset = queryset.filter(is_pagado=is_pagado.lower() == 'true')
        
        if fecha_desde:
            queryset = queryset.filter(fecha__gte=fecha_desde)
        
        if fecha_hasta:
            queryset = queryset.filter(fecha__lte=fecha_hasta)
        
        # Aplicar búsqueda si existe
        search = request.query_params.get('search')
        if search:
            queryset = self.filter_queryset(queryset)
        
        # Paginar y retornar
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Detalle de crédito de proveedor",
        description="Obtiene el detalle completo de un crédito de proveedor incluyendo el historial de pagos.",
        responses={
            200: CreditoProveedorListSerializer,
            404: OpenApiResponse(description='Crédito no encontrado')
        },
        tags=['Créditos Proveedor']
    )
    def retrieve(self, request, *args, **kwargs):
        """Detalle de crédito con historial de pagos incluido en el serializer"""
        return super().retrieve(request, *args, **kwargs)
    
    @extend_schema(
        summary="Créditos de proveedor vencidos",
        description="Lista todos los créditos de proveedores que no han sido pagados y cuya fecha de vencimiento ya pasó.",
        parameters=[
            OpenApiParameter(
                name='dia_inicio',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Fecha inicio (YYYY-MM-DD)',
                required=False
            ),
            OpenApiParameter(
                name='dia_fin',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Fecha fin (YYYY-MM-DD)',
                required=False
            ),
        ],
        responses={
            200: CreditoProveedorListSerializer(many=True)
        },
        tags=['Créditos Proveedor']
    )
    @action(detail=False, methods=['get'], url_path='vencidos')
    def vencidos(self, request):
        """Listar créditos vencidos (no pagados y fecha vencimiento < hoy)"""
        hoy = timezone.now().date()
        dia_inicio = request.query_params.get('dia_inicio')
        dia_fin = request.query_params.get('dia_fin')
        
        queryset = self.get_queryset().filter(
            is_pagado=False,
            fecha_vencimiento__lt=hoy
        )
        
        if dia_inicio:
            queryset = queryset.filter(fecha__gte=dia_inicio)
        if dia_fin:
            queryset = queryset.filter(fecha__lte=dia_fin)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = CreditoProveedorListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = CreditoProveedorListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Créditos de proveedor activos",
        description="Lista todos los créditos de proveedores que aún no han sido pagados completamente.",
        parameters=[
            OpenApiParameter(
                name='dia_inicio',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Fecha inicio (YYYY-MM-DD)',
                required=False
            ),
            OpenApiParameter(
                name='dia_fin',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Fecha fin (YYYY-MM-DD)',
                required=False
            ),
        ],
        responses={
            200: CreditoProveedorListSerializer(many=True)
        },
        tags=['Créditos Proveedor']
    )
    @action(detail=False, methods=['get'], url_path='activos')
    def activos(self, request):
        """Listar créditos activos (no pagados)"""
        dia_inicio = request.query_params.get('dia_inicio')
        dia_fin = request.query_params.get('dia_fin')
        
        queryset = self.get_queryset().filter(fecha_vencimiento__gte=timezone.now().date())
        
        if dia_inicio:
            queryset = queryset.filter(fecha__gte=dia_inicio)
        if dia_fin:
            queryset = queryset.filter(fecha__lte=dia_fin)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = CreditoProveedorListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = CreditoProveedorListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Créditos por proveedor",
        description="Lista todos los créditos de un proveedor específico.",
        parameters=[
            OpenApiParameter(
                name='proveedor_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID del proveedor',
                required=True
            ),
            OpenApiParameter(
                name='activos',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='CREDITOS ACTIVOS DEL PROVEEDOR',
                required=False
            ),
            OpenApiParameter(
                name='vencidos',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='CREDITOS VENCIDOS DEL PROVEEDOR',
                required=False
            ),
            OpenApiParameter(
                name='pagados',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='CREDITOS PAGADOS DEL PROVEEDOR',
                required=False
            ),
            OpenApiParameter(
                name='dia_inicio',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Fecha inicio (YYYY-MM-DD)',
                required=False
            ),
            OpenApiParameter(
                name='dia_fin',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Fecha fin (YYYY-MM-DD)',
                required=False
            ),
        ],
        responses={
            200: CreditoProveedorListSerializer(many=True)
        },
        tags=['Créditos Proveedor']
    )
    @action(detail=False, methods=['get'], url_path='por_proveedor/(?P<proveedor_id>[^/.]+)')
    def por_proveedor(self, request, proveedor_id=None):
        """Listar créditos de un proveedor específico"""
        activos = request.query_params.get('activos', False)
        vencidos = request.query_params.get('vencidos', False)
        pagados = request.query_params.get('pagados', False)
        dia_inicio = request.query_params.get('dia_inicio')
        dia_fin = request.query_params.get('dia_fin')
        
        queryset = self.get_queryset().filter(proveedor_id=proveedor_id).order_by('fecha', 'created_at')
        
        if activos and activos.lower() == 'true':
            queryset = queryset.filter(is_pagado=False)
        
        if vencidos and vencidos.lower() == 'true':
            hoy = timezone.now().date()
            queryset = queryset.filter(is_pagado=False, fecha_vencimiento__lt=hoy)
        
        if pagados:
            flag = pagados.lower() == 'true'
            queryset = queryset.filter(is_pagado=flag)
        
        if dia_inicio:
            queryset = queryset.filter(fecha__gte=dia_inicio)
        if dia_fin:
            queryset = queryset.filter(fecha__lte=dia_fin)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = CreditoProveedorListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = CreditoProveedorListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Estadísticas de créditos de proveedor",
        description="""
        Obtiene estadísticas generales de todos los créditos de proveedores en el sistema.
        
        **Incluye:**
        - Total de créditos
        - Monto total de créditos
        - Monto total pagado
        - Adeudo total pendiente
        - Cantidad de créditos activos, liquidados y vencidos
        - Créditos próximos a vencer (7 días)
        """,
        responses={
            200: OpenApiResponse(
                description='Estadísticas de créditos de proveedor',
                examples=[
                    OpenApiExample(
                        'Ejemplo de respuesta',
                        value={
                            'total_creditos': 150,
                            'total_dispersado': 500000.00,
                            'total_pagado': 350000.00,
                            'adeudo_total': 150000.00,
                            'creditos_activos': 45,
                            'creditos_liquidados': 105,
                            'creditos_vencidos': 12,
                            'creditos_por_vencer_7_dias': 8
                        }
                    )
                ]
            )
        },
        tags=['Créditos Proveedor']
    )
    @action(detail=False, methods=['get'], url_path='estadisticas')
    def estadisticas(self, request):
        """Obtener estadísticas generales de créditos de proveedor"""
        hoy = timezone.now().date()
        
        # Estadísticas generales
        stats = CreditoProveedor.objects.aggregate(
            total_creditos=Count('id'),
            total_dispersado=Sum('monto'),
            total_pagado=Sum('monto_pagado'),
            activos=Count('id', filter=Q(is_pagado=False)),
            liquidados=Count('id', filter=Q(is_pagado=True)),
            vencidos=Count('id', filter=Q(is_pagado=False, fecha_vencimiento__lt=hoy))
        )
        
        # Calcular adeudo total
        adeudo_total = (stats['total_dispersado'] or 0) - (stats['total_pagado'] or 0)
        
        # Créditos por vencer en los próximos 7 días
        proximos_7_dias = hoy + timedelta(days=7)
        por_vencer = CreditoProveedor.objects.filter(
            is_pagado=False,
            fecha_vencimiento__gte=hoy,
            fecha_vencimiento__lte=proximos_7_dias
        ).count()
        
        return Response({
            'total_creditos': stats['total_creditos'] or 0,
            'total_dispersado': float(stats['total_dispersado'] or 0),
            'total_pagado': float(stats['total_pagado'] or 0),
            'adeudo_total': float(adeudo_total),
            'creditos_activos': stats['activos'] or 0,
            'creditos_liquidados': stats['liquidados'] or 0,
            'creditos_vencidos': stats['vencidos'] or 0,
            'creditos_por_vencer_7_dias': por_vencer
        })
    
    @extend_schema(
        summary="Estadísticas de créditos por proveedor",
        description="""
        Obtiene estadísticas detalladas de los créditos de un proveedor específico.
        
        **Incluye:**
        - Información del proveedor (ID, código, nombre)
        - Total de créditos
        - Monto total de créditos
        - Monto total pagado
        - Adeudo total pendiente
        - Créditos activos, liquidados y vencidos
        - Promedio de crédito
        - Listado paginado de todos sus créditos con historial de pagos
        """,
        parameters=[
            OpenApiParameter(
                name='proveedor_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID del proveedor',
                required=True
            ),
        ],
        responses={
            200: OpenApiResponse(description='Estadísticas del proveedor'),
            404: OpenApiResponse(description='Proveedor no encontrado')
        },
        tags=['Créditos Proveedor']
    )
    @action(detail=False, methods=['get'], url_path='estadisticas-proveedor/(?P<proveedor_id>[^/.]+)')
    def estadisticas_proveedor(self, request, proveedor_id=None):
        """
        Obtener estadísticas detalladas de créditos de un proveedor
        """
        from apps.erp.models import Proveedor
        
        # Verificar que el proveedor existe
        try:
            proveedor = Proveedor.objects.get(id=proveedor_id)
        except Proveedor.DoesNotExist:
            return Response({
                'detail': f'Proveedor con ID {proveedor_id} no encontrado.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        hoy = timezone.now().date()
        
        # Estadísticas del proveedor
        creditos_proveedor = CreditoProveedor.objects.filter(proveedor_id=proveedor_id)
        
        stats = creditos_proveedor.aggregate(
            total_creditos=Count('id'),
            total_dispersado=Sum('monto'),
            total_pagado=Sum('monto_pagado'),
            activos=Count('id', filter=Q(is_pagado=False)),
            liquidados=Count('id', filter=Q(is_pagado=True)),
            vencidos=Count('id', filter=Q(is_pagado=False, fecha_vencimiento__lt=hoy))
        )
        
        # Calcular adeudo total del proveedor
        adeudo_total = (stats['total_dispersado'] or 0) - (stats['total_pagado'] or 0)
        
        # Calcular promedio de crédito
        total_creditos = stats['total_creditos'] or 0
        promedio_credito = (stats['total_dispersado'] or 0) / total_creditos if total_creditos > 0 else 0
        
        # Obtener listado de créditos paginado
        creditos_queryset = creditos_proveedor.select_related(
            'proveedor', 'created_by'
        ).prefetch_related('pagos_proveedor').order_by('-fecha', '-created_at')
        
        page = self.paginate_queryset(creditos_queryset)
        
        if page is not None:
            creditos_serializer = CreditoProveedorListSerializer(page, many=True)
            paginated_response = self.get_paginated_response(creditos_serializer.data)
            creditos_data = paginated_response.data
        else:
            creditos_serializer = CreditoProveedorListSerializer(creditos_queryset, many=True)
            creditos_data = {
                'count': creditos_queryset.count(),
                'next': None,
                'previous': None,
                'results': creditos_serializer.data
            }
        
        return Response({
            'proveedor': {
                'id': proveedor.id,
                'codigo': proveedor.codigo,
                'nombre': proveedor.nombre
            },
            'estadisticas': {
                'total_creditos': total_creditos,
                'total_dispersado': float(stats['total_dispersado'] or 0),
                'total_pagado': float(stats['total_pagado'] or 0),
                'adeudo_total': float(adeudo_total),
                'creditos_activos': stats['activos'] or 0,
                'creditos_liquidados': stats['liquidados'] or 0,
                'creditos_vencidos': stats['vencidos'] or 0,
                'promedio_credito': float(promedio_credito)
            },
            #'creditos': creditos_data
        })


class PagosCreditoProveedorViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de pagos de crédito de proveedor
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Queryset con select_related para optimizar consultas"""
        queryset = PagosCreditoProveedor.objects.select_related(
            'credito_proveedor', 'credito_proveedor__proveedor', 'metodo_pago', 'created_by'
        )
        
        # Filtros desde query params
        credito_id = self.request.query_params.get('credito')
        metodo_pago_id = self.request.query_params.get('metodo_pago')
        fecha_desde = self.request.query_params.get('fecha_desde')
        fecha_hasta = self.request.query_params.get('fecha_hasta')
        
        if credito_id:
            queryset = queryset.filter(credito_proveedor_id=credito_id)
        
        if metodo_pago_id:
            queryset = queryset.filter(metodo_pago_id=metodo_pago_id)
        
        if fecha_desde:
            queryset = queryset.filter(created_at__date__gte=fecha_desde)
        
        if fecha_hasta:
            queryset = queryset.filter(created_at__date__lte=fecha_hasta)
        
        return queryset.order_by('-created_at')
    
    def get_serializer_class(self):
        """Seleccionar serializer según la acción"""
        if self.action == 'create':
            return PagoCreditoProveedorCreateSingularSerializer
        return PagosCreditoProveedorSerializer
    
    @extend_schema(
        summary="Listar pagos de crédito de proveedor",
        parameters=[
            OpenApiParameter(name='credito', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='metodo_pago', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='fecha_desde', type=OpenApiTypes.DATE, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='fecha_hasta', type=OpenApiTypes.DATE, location=OpenApiParameter.QUERY),
        ],
        responses={200: PagosCreditoProveedorSerializer(many=True)},
        tags=['Pagos Crédito Proveedor']
    )
    def list(self, request, *args, **kwargs):
        """Listar pagos con filtros"""
        return super().list(request, *args, **kwargs)
    
    @extend_schema(
        summary="Registrar pago de crédito de proveedor",
        description="""
        Registra un nuevo pago para un crédito de proveedor.
        
        **Campos requeridos:**
        - credito: ID del crédito
        - cantidad_pagar: Monto que se aplicará al crédito
        - pagos: Array de pagos con diferentes métodos
        
        **Validaciones:**
        - El crédito debe existir y no estar liquidado
        - cantidad_pagar no puede exceder el adeudo
        - Total de pagos >= cantidad_pagar
        
        **NO requiere caja abierta** - Los pagos a proveedores son independientes del sistema de caja.
        """,
        request=PagoCreditoProveedorCreateSingularSerializer,
        responses={
            201: CreditoProveedorListSerializer,
            400: OpenApiResponse(description='Error de validación')
        },
        tags=['Pagos Crédito Proveedor']
    )
    def create(self, request, *args, **kwargs):
        """Registrar pago singular a un crédito de proveedor"""
        serializer = self.get_serializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
            credito = serializer.save()
            credito_serializer = CreditoProveedorListSerializer(credito)
            return Response(credito_serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'detail': str(e),
                'error_code': 'ERROR_REGISTRO_PAGO_PROVEEDOR'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(exclude=True)
    def update(self, request, *args, **kwargs):
        return Response(
            {"error": "No se pueden modificar pagos una vez registrados."},
            status=status.HTTP_403_FORBIDDEN
        )
    
    @extend_schema(exclude=True)
    def partial_update(self, request, *args, **kwargs):
        return Response(
            {"error": "No se pueden modificar pagos una vez registrados."},
            status=status.HTTP_403_FORBIDDEN
        )
    
    @extend_schema(exclude=True)
    def destroy(self, request, *args, **kwargs):
        return Response(
            {"error": "No se pueden eliminar pagos."},
            status=status.HTTP_403_FORBIDDEN
        )
    
    @extend_schema(
        summary="Pagos por proveedor",
        tags=['Pagos Crédito Proveedor']
    )
    @action(detail=False, methods=['get'], url_path='por-proveedor/(?P<proveedor_id>[^/.]+)')
    def por_proveedor(self, request, proveedor_id=None):
        """Listar pagos de un proveedor específico"""
        queryset = self.get_queryset().filter(credito_proveedor__proveedor_id=proveedor_id)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Registrar pagos masivos a proveedores",
        description="""
        Registra pagos a múltiples créditos de proveedor en una sola petición.
        
        **Características:**
        - Procesa todos los pagos en una transacción atómica
        - Si algún pago falla, se revierten todos los cambios
        - NO requiere caja abierta
        - Valida duplicados en la lista
        - Cada pago debe incluir su campo cantidad_pagar
        
        **Estructura del request:**
        ```json
        {
            "lista": [
                {
                    "credito": 1,
                    "cantidad_pagar": 1000.00,
                    "pagos": [
                        {
                            "metodo_pago": 1,
                            "monto": 500.00
                        },
                        {
                            "metodo_pago": 2,
                            "monto": 500.00
                        }
                    ]
                }
            ]
        }
        ```
        """,
        request=PagoCreditoProveedorCreateMasivoSerializer,
        responses={201: OpenApiResponse(description='Pagos registrados')},
        tags=['Pagos Crédito Proveedor']
    )
    @action(detail=False, methods=['post'], url_path='registrar-masivo')
    def registrar_masivo(self, request):
        """Registrar pagos masivos a múltiples créditos de proveedor"""
        serializer = PagoCreditoProveedorCreateMasivoSerializer(
            data=request.data,
            context={'request': request}
        )
        
        try:
            serializer.is_valid(raise_exception=True)
            resultado = serializer.save()
            return Response({
                'detail': 'Pagos masivos registrados exitosamente.',
                'data': resultado
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'detail': f'Error al procesar pagos masivos: {str(e)}',
                'error_code': 'ERROR_PAGOS_MASIVOS_PROVEEDOR'
            }, status=status.HTTP_400_BAD_REQUEST)
