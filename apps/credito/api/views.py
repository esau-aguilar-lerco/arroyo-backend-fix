import hashlib
import json
import logging
from decimal import Decimal, InvalidOperation

from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum, Count, Max, Min
from django.utils import timezone
from datetime import timedelta

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from apps.base.serachFilter import MinimalSearchFilter
from apps.credito.models import CreditoCliente, OperacionPrelacionPago, PagosCredito
from apps.contabilidad.models import MetodoPago
from apps.credito.serializers.credito import (
    CreditoClienteSerializer,
    CreditoClienteMiniSerializer,
    CreditoClienteListSerializer,
    PagosCreditoSerializer,
    PagoCreditoCreateSingularSerializer,
    PagoCreditoCreateMasivoSerializer,
    PagoCreditoUpdateSerializer,
    PagoCreditoCancelarSerializer,
    EstadisticasClienteResponseSerializer,
)

logger = logging.getLogger(__name__)


class CreditoClienteMiniViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    ViewSet simplificado para listar créditos sin paginación
    """
    queryset = CreditoCliente.objects.all().select_related('cliente').order_by('-fecha', '-created_at')
    serializer_class = CreditoClienteMiniSerializer
    pagination_class = None  # Desactivar paginación
    search_fields = ['cliente__nombre', 'cliente__codigo']
    filter_backends = [MinimalSearchFilter]


class CreditoClienteViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    ViewSet para gestión de créditos de clientes
    
    Endpoints:
    - GET /api/creditos/ - Listar créditos con filtros
    - GET /api/creditos/{id}/ - Detalle de crédito con historial de pagos
    - GET /api/creditos/vencidos/ - Créditos vencidos
    - GET /api/creditos/activos/ - Créditos activos
    - GET /api/creditos/por_cliente/{cliente_id}/ - Créditos de un cliente
    - GET /api/creditos/estadisticas/ - Estadísticas generales
    """
    queryset = CreditoCliente.objects.select_related(
        'cliente', 'created_by', 'updated_by'
    ).prefetch_related('pagos').order_by('-fecha', '-created_at')
    
    search_fields = ['cliente__nombre', 'cliente__codigo']
    filter_backends = [MinimalSearchFilter]

    def get_serializer_class(self):
        """Seleccionar serializer según la acción"""
        if self.action == 'retrieve':
            return CreditoClienteListSerializer
        return CreditoClienteMiniSerializer

    def _agrupar_por_cliente(self, queryset):
        """
        Agrupar créditos por cliente con totales consolidados.
        """
        hoy = timezone.now().date()
        agrupados = (
            queryset.values(
                'cliente_id',
                'cliente__codigo',
                'cliente__nombre',
                'cliente__apellido_paterno',
                'cliente__apellido_materno',
                'cliente__razon_social',
            )
            .annotate(
                total_creditos=Count('id'),
                total_dispersado=Sum('monto'),
                total_pagado=Sum('monto_pagado'),
                fecha_ultimo_credito=Max('fecha'),
                fecha_vencimiento_proxima=Min('fecha_vencimiento', filter=Q(is_pagado=False)),
                creditos_vencidos=Count('id', filter=Q(is_pagado=False, fecha_vencimiento__lt=hoy)),
                creditos_activos=Count('id', filter=Q(is_pagado=False, fecha_vencimiento__gte=hoy)),
            )
            .order_by('cliente__nombre')
        )

        resultados = []
        for item in agrupados:
            total_dispersado = item['total_dispersado'] or 0
            total_pagado = item['total_pagado'] or 0
            adeudo = total_dispersado - total_pagado

            nombre = (item['cliente__nombre'] or '').strip()
            apellido_paterno = (item['cliente__apellido_paterno'] or '').strip()
            apellido_materno = (item['cliente__apellido_materno'] or '').strip()
            razon_social = (item['cliente__razon_social'] or '').strip()

            if nombre:
                nombre_cliente = " ".join(
                    [part for part in [nombre, apellido_paterno, apellido_materno] if part]
                )
            else:
                nombre_cliente = razon_social

            if adeudo <= 0:
                estado = 'PAGADA'
            elif (item['creditos_vencidos'] or 0) > 0:
                estado = 'VENCIDA'
            else:
                estado = 'ACTIVA'

            resultados.append({
                'cliente': {
                    'id': item['cliente_id'],
                    'codigo': item['cliente__codigo'],
                    'nombre': nombre_cliente,
                },
                'total_creditos': item['total_creditos'] or 0,
                'total_dispersado': float(total_dispersado),
                'total_pagado': float(total_pagado),
                'adeudo': float(adeudo),
                'fecha_ultimo_credito': item['fecha_ultimo_credito'],
                'fecha_vencimiento_proxima': item['fecha_vencimiento_proxima'],
                'creditos_vencidos': item['creditos_vencidos'] or 0,
                'creditos_activos': item['creditos_activos'] or 0,
                'estado': estado,
            })

        page = self.paginate_queryset(resultados)
        if page is not None:
            return self.get_paginated_response(page)
        return Response(resultados)
    
    @extend_schema(
        summary="Listar créditos de clientes",
        description="""
        Lista todos los créditos con opciones de filtrado avanzado.
        
        **Filtros disponibles (query params):**
        - `cliente`: ID del cliente
        - `estado`: Estado del crédito (ACTIVA, PAGADA)
        - `is_pagado`: true/false (si está liquidado)
        - `fecha_desde`: Fecha inicio (YYYY-MM-DD)
        - `fecha_hasta`: Fecha fin (YYYY-MM-DD)
        - `dia_inicio`: Fecha inicio alternativa (YYYY-MM-DD)
        - `dia_fin`: Fecha fin alternativa (YYYY-MM-DD)
        - `vencidos`: true/false (solo créditos vencidos)
        - `search`: Búsqueda por nombre o código de cliente
        """,
        parameters=[
            OpenApiParameter(
                name='cliente',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='ID del cliente',
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
            200: CreditoClienteMiniSerializer(many=True),
        },
        tags=['Créditos']
    )
    def list(self, request, *args, **kwargs):
        """Listar créditos con filtros"""
        queryset = self.get_queryset()
        
        # Obtener filtros desde query params
        cliente_id = request.query_params.get('cliente')
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
        
        if cliente_id:
            queryset = queryset.filter(cliente_id=cliente_id)
        
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

        agrupado = request.query_params.get('agrupado')
        if agrupado and agrupado.lower() == 'true':
            return self._agrupar_por_cliente(queryset)
        
        # Paginar y retornar
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Detalle de crédito",
        description="Obtiene el detalle completo de un crédito incluyendo el historial de pagos.",
        responses={
            200: CreditoClienteListSerializer,
            404: OpenApiResponse(description='Crédito no encontrado')
        },
        tags=['Créditos']
    )
    def retrieve(self, request, *args, **kwargs):
        """Detalle de crédito con historial de pagos incluido en el serializer"""
        return super().retrieve(request, *args, **kwargs)
    
    @extend_schema(
        summary="Créditos vencidos",
        description="Lista todos los créditos que no han sido pagados y cuya fecha de vencimiento ya pasó.",
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
            200: CreditoClienteListSerializer(many=True)
        },
        tags=['Créditos']
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

        search = request.query_params.get('search')
        if search:
            queryset = self.filter_queryset(queryset)

        agrupado = request.query_params.get('agrupado')
        if agrupado and agrupado.lower() == 'true':
            return self._agrupar_por_cliente(queryset)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = CreditoClienteListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = CreditoClienteListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Créditos activos",
        description="Lista todos los créditos que aún no han sido pagados completamente.",
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
            200: CreditoClienteListSerializer(many=True)
        },
        tags=['Créditos']
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

        search = request.query_params.get('search')
        if search:
            queryset = self.filter_queryset(queryset)

        agrupado = request.query_params.get('agrupado')
        if agrupado and agrupado.lower() == 'true':
            return self._agrupar_por_cliente(queryset)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = CreditoClienteListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = CreditoClienteListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Créditos por cliente",
        description="Lista todos los créditos de un cliente específico.",
        parameters=[
            OpenApiParameter(
                name='cliente_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID del cliente',
                required=True
            ),
            OpenApiParameter(
                name='activos',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='CREDITOS ACTIVOS DEL CLIENTE',
                required=False
            ),
            OpenApiParameter(
                name='vencidos',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='CREDITOS VENCIDOS DEL CLIENTE',
                required=False
            ),
            OpenApiParameter(
                name='pagados',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='CREDITOS PAGADOS DEL CLIENTE',
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
            200: CreditoClienteListSerializer(many=True)
        },
        tags=['Créditos']
    )
    @action(detail=False, methods=['get'], url_path='por_cliente/(?P<cliente_id>[^/.]+)')
    def por_cliente(self, request, cliente_id=None):
        """Listar créditos de un cliente específico"""
        activos = request.query_params.get('activos', False)
        vencidos = request.query_params.get('vencidos', False)
        pagados = request.query_params.get('pagados', False)
        dia_inicio = request.query_params.get('dia_inicio')
        dia_fin = request.query_params.get('dia_fin')
        
        queryset = self.get_queryset().filter(cliente_id=cliente_id).order_by('fecha', 'created_at')
        
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
            serializer = CreditoClienteListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = CreditoClienteListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Estadísticas de créditos",
        description="""
        Obtiene estadísticas generales de todos los créditos en el sistema.
        
        **Incluye:**
        - Total de dispersiones
        - Monto total dispersado
        - Monto total pagado
        - Adeudo total pendiente
        - Cantidad de créditos activos, liquidados y vencidos
        - Créditos próximos a vencer (7 días)
        """,
        responses={
            200: OpenApiResponse(
                description='Estadísticas de créditos',
                examples=[
                    OpenApiExample(
                        'Ejemplo de respuesta',
                        value={
                            'total_dispersiones': 150,
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
        tags=['Créditos']
    )
    @action(detail=False, methods=['get'], url_path='estadisticas')
    def estadisticas(self, request):
        """Obtener estadísticas generales de créditos"""
        hoy = timezone.now().date()
        
        # Estadísticas generales
        stats = CreditoCliente.objects.aggregate(
            total_dispersiones=Count('id'),
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
        por_vencer = CreditoCliente.objects.filter(
            is_pagado=False,
            fecha_vencimiento__gte=hoy,
            fecha_vencimiento__lte=proximos_7_dias
        ).count()
        
        return Response({
            'total_dispersiones': stats['total_dispersiones'] or 0,
            'total_dispersado': float(stats['total_dispersado'] or 0),
            'total_pagado': float(stats['total_pagado'] or 0),
            'adeudo_total': float(adeudo_total),
            'creditos_activos': stats['activos'] or 0,
            'creditos_liquidados': stats['liquidados'] or 0,
            'creditos_vencidos': stats['vencidos'] or 0,
            'creditos_por_vencer_7_dias': por_vencer
        })
    
    @extend_schema(
        summary="Estadísticas de créditos por cliente",
        description="""
        Obtiene estadísticas detalladas de los créditos de un cliente específico.
        
        **Incluye:**
        - Información del cliente (ID, código, nombre)
        - Total de créditos dispersados
        - Monto total dispersado
        - Monto total pagado
        - Adeudo total pendiente
        - Créditos activos, liquidados y vencidos
        - Promedio de crédito
        - Listado paginado de todos sus créditos con historial de pagos
        
        **Filtros opcionales (query params):**
        - `page`: Número de página para la lista de créditos
        - `page_size`: Tamaño de página (por defecto 10)
        """,
        parameters=[
            OpenApiParameter(
                name='cliente_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID del cliente',
                required=True
            ),
            OpenApiParameter(
                name='page',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Número de página',
                required=False
            ),
            OpenApiParameter(
                name='page_size',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Tamaño de página',
                required=False
            ),
        ],
        responses={
            200: EstadisticasClienteResponseSerializer,
            404: OpenApiResponse(description='Cliente no encontrado')
        },
        tags=['Créditos']
    )
    @action(detail=False, methods=['get'], url_path='estadisticas-cliente/(?P<cliente_id>[^/.]+)')
    def estadisticas_cliente(self, request, cliente_id=None):
        """
        Obtener estadísticas detalladas de créditos de un cliente
        
        GET /api/creditos/estadisticas-cliente/{cliente_id}/
        """
        from apps.erp.models import Cliente
        
        # Verificar que el cliente existe
        try:
            cliente = Cliente.objects.get(id=cliente_id)
        except Cliente.DoesNotExist:
            return Response({
                'detail': f'Cliente con ID {cliente_id} no encontrado.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        hoy = timezone.now().date()
        
        # Estadísticas del cliente
        creditos_cliente = CreditoCliente.objects.filter(cliente_id=cliente_id)
        
        stats = creditos_cliente.aggregate(
            total_creditos=Count('id'),
            total_dispersado=Sum('monto'),
            total_pagado=Sum('monto_pagado'),
            activos=Count('id', filter=Q(is_pagado=False)),
            liquidados=Count('id', filter=Q(is_pagado=True)),
            vencidos=Count('id', filter=Q(is_pagado=False, fecha_vencimiento__lt=hoy))
        )
        
        # Calcular adeudo total del cliente
        adeudo_total = (stats['total_dispersado'] or 0) - (stats['total_pagado'] or 0)
        
        # Calcular promedio de crédito
        total_creditos = stats['total_creditos'] or 0
        promedio_credito = (stats['total_dispersado'] or 0) / total_creditos if total_creditos > 0 else 0
        
        # Obtener listado de créditos paginado
        #creditos_queryset = creditos_cliente.select_related(
        #    'cliente', 'created_by'
        #).prefetch_related('pagos').order_by('-fecha', '-created_at')
        
        # Aplicar paginación usando el método del ViewSet
        #page = self.paginate_queryset(creditos_queryset)
        
        #if page is not None:
        #    #creditos_serializer = CreditoClienteListSerializer(page, many=True)
        #    # Usar get_paginated_response del ViewSet que construye los links correctamente
        #    #paginated_response = self.get_paginated_response(creditos_serializer.data)
        #    #creditos_data = paginated_response.data
        #else:
        #    creditos_serializer = CreditoClienteListSerializer(creditos_queryset, many=True)
        #    creditos_data = {
        #        'count': creditos_queryset.count(),
        #        'next': None,
        #        'previous': None,
        #        'results': creditos_serializer.data
        #    }
        
        return Response({
            'cliente': {
                'id': cliente.id,
                'codigo': cliente.codigo,
                'nombre': cliente.nombre_completo
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


class PagosCreditoViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de pagos de crédito
    
    Endpoints:
    - GET /api/pagos-credito/ - Listar pagos
    - POST /api/pagos-credito/ - Crear pago
    - GET /api/pagos-credito/{id}/ - Detalle de pago
    - GET /api/pagos-credito/por_cliente/{cliente_id}/ - Pagos de un cliente
    """
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _error_response(detail, code, http_status):
        return Response({'detail': detail, 'code': code}, status=http_status)

    def _log_prelacion_event(
        self,
        request,
        *,
        event,
        entidad_id,
        idempotency_key=None,
        total=None,
        operacion_id=None,
        code=None,
        detail=None,
    ):
        caja_id = None
        try:
            caja_apertura = request.user.get_mi_caja() if request.user else None
            caja_id = getattr(caja_apertura, 'caja_id', None) or getattr(caja_apertura, 'id', None)
        except Exception:
            caja_id = None

        payload = {
            'event': event,
            'operacion_id': operacion_id,
            'entidad': 'CLIENTE',
            'entidad_id': entidad_id,
            'idempotency_key': idempotency_key,
            'total': str(total) if total is not None else None,
            'usuario_id': getattr(request.user, 'id', None),
            'caja_id': caja_id,
            'code': code,
            'detail': detail,
        }
        logger.info(
            'prelacion_pago_event %s',
            json.dumps(payload, sort_keys=True, default=str),
        )

    @staticmethod
    def _map_prelacion_error_code(detail):
        message = (detail or '').lower()
        if 'no tiene créditos activos' in message:
            return 'NO_ACTIVE_CREDITS'
        if 'excede el adeudo total' in message:
            return 'AMOUNT_EXCEEDS_BALANCE'
        if 'no fue posible distribuir los pagos' in message:
            return 'PAYMENT_DISTRIBUTION_ERROR'
        return 'PRELACION_ERROR'

    @staticmethod
    def _to_money(value, field_name='monto'):
        try:
            amount = Decimal(str(value)).quantize(Decimal('0.01'))
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError(f'Valor inválido en {field_name}.')
        if amount <= Decimal('0.00'):
            raise ValueError(f'{field_name} debe ser mayor a cero.')
        return amount

    def _build_payment_pool(self, pagos):
        if not isinstance(pagos, list) or not pagos:
            raise ValueError('Debe proporcionar al menos un pago.')

        pool = []
        total = Decimal('0.00')
        for idx, pago in enumerate(pagos, start=1):
            if not isinstance(pago, dict):
                raise ValueError(f'Formato inválido en pagos[{idx}].')

            metodo_raw = pago.get('metodo_pago')
            metodo_id = metodo_raw.get('id') if isinstance(metodo_raw, dict) else metodo_raw
            metodo = MetodoPago.objects.filter(id=metodo_id).first()
            if not metodo:
                raise ValueError(f'Método de pago inválido en pagos[{idx}].')

            monto = self._to_money(pago.get('monto'), f'pagos[{idx}].monto')
            referencia = (pago.get('referencia') or '').strip()
            pool.append({
                'metodo_pago': metodo.id,
                'referencia': referencia,
                'restante': monto,
            })
            total += monto
        return pool, total

    @staticmethod
    def _consume_pool(pool, objetivo):
        restante = objetivo.quantize(Decimal('0.01'))
        pagos_credito = []
        for item in pool:
            if restante <= Decimal('0.00'):
                break
            if item['restante'] <= Decimal('0.00'):
                continue
            usar = min(item['restante'], restante).quantize(Decimal('0.01'))
            if usar <= Decimal('0.00'):
                continue
            pagos_credito.append({
                'metodo_pago': item['metodo_pago'],
                'monto': str(usar),
                'referencia': item['referencia'],
            })
            item['restante'] = (item['restante'] - usar).quantize(Decimal('0.01'))
            restante = (restante - usar).quantize(Decimal('0.01'))
        return pagos_credito, restante

    @staticmethod
    def _resolve_idempotency_key(request):
        key = (
            request.headers.get('Idempotency-Key')
            or request.data.get('idempotency_key')
            or ''
        ).strip()
        if not key:
            raise ValueError('Debe enviar Idempotency-Key en header o idempotency_key en body.')
        if len(key) > 128:
            raise ValueError('Idempotency-Key excede 128 caracteres.')
        return key

    @staticmethod
    def _build_request_hash(cliente_id, cantidad_pagar, pool):
        canonical = {
            'tipo': 'CLIENTE',
            'cliente': int(cliente_id),
            'cantidad_pagar': str(cantidad_pagar.quantize(Decimal('0.01'))),
            'pagos': [
                {
                    'metodo_pago': int(item['metodo_pago']),
                    'monto': str(item['restante'].quantize(Decimal('0.01'))),
                    'referencia': item['referencia'],
                }
                for item in pool
            ],
        }
        raw = json.dumps(canonical, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()
    
    def get_queryset(self):
        """Queryset con select_related para optimizar consultas"""
        queryset = PagosCredito.objects.select_related(
            'credito', 'credito__cliente', 'metodo_pago', 'created_by'
        )
        
        # Filtros desde query params
        credito_id = self.request.query_params.get('credito')
        metodo_pago_id = self.request.query_params.get('metodo_pago')
        fecha_desde = self.request.query_params.get('fecha_desde')
        fecha_hasta = self.request.query_params.get('fecha_hasta')
        
        if credito_id:
            queryset = queryset.filter(credito_id=credito_id)
        
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
            return PagoCreditoCreateSingularSerializer
        return PagosCreditoSerializer
    
    @extend_schema(
        summary="Listar pagos de crédito",
        description="""
        Lista todos los pagos registrados con opciones de filtrado.
        
        **Filtros disponibles (query params):**
        - `credito`: ID del crédito
        - `metodo_pago`: ID del método de pago
        - `fecha_desde`: Fecha inicio (YYYY-MM-DD)
        - `fecha_hasta`: Fecha fin (YYYY-MM-DD)
        """,
        parameters=[
            OpenApiParameter(
                name='credito',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='ID del crédito',
                required=False
            ),
            OpenApiParameter(
                name='metodo_pago',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='ID del método de pago',
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
        ],
        responses={
            200: PagosCreditoSerializer(many=True)
        },
        tags=['Pagos de Crédito']
    )
    def list(self, request, *args, **kwargs):
        """Listar pagos con filtros"""
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=['post'], url_path='prelacion')
    def prelacion(self, request):
        """
        Aplica un pago global a los créditos activos de un cliente por prelación:
        primero al crédito más antiguo por fecha de vencimiento.
        """
        cliente_id = request.data.get('cliente')
        if not cliente_id:
            return self._error_response(
                'Debe enviar el campo cliente.',
                'MISSING_CLIENTE',
                status.HTTP_400_BAD_REQUEST
            )

        try:
            cliente_id_int = int(cliente_id)
        except (TypeError, ValueError):
            return self._error_response(
                'El campo cliente debe ser un entero válido.',
                'INVALID_CLIENTE_ID',
                status.HTTP_400_BAD_REQUEST,
            )

        try:
            cantidad_pagar = self._to_money(request.data.get('cantidad_pagar'), 'cantidad_pagar')
        except ValueError as exc:
            return self._error_response(str(exc), 'INVALID_AMOUNT', status.HTTP_400_BAD_REQUEST)

        try:
            idempotency_key = self._resolve_idempotency_key(request)
        except ValueError as exc:
            return self._error_response(str(exc), 'IDEMPOTENCY_KEY_INVALID', status.HTTP_400_BAD_REQUEST)

        try:
            pool, total_pagos = self._build_payment_pool(request.data.get('pagos', []))
        except ValueError as exc:
            return self._error_response(str(exc), 'INVALID_PAYMENT_SPLIT', status.HTTP_400_BAD_REQUEST)

        request_hash = self._build_request_hash(cliente_id_int, cantidad_pagar, pool)
        self._log_prelacion_event(
            request,
            event='REQUEST_RECEIVED',
            entidad_id=cliente_id_int,
            idempotency_key=idempotency_key,
            total=cantidad_pagar,
        )

        if total_pagos != cantidad_pagar:
            return self._error_response(
                (
                    f'El total de pagos (${total_pagos}) debe coincidir '
                    f'con cantidad_pagar (${cantidad_pagar}).'
                ),
                'PAYMENT_TOTAL_MISMATCH',
                status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            try:
                operacion = OperacionPrelacionPago.objects.create(
                    tipo=OperacionPrelacionPago.TIPO_CLIENTE,
                    entidad_id=cliente_id_int,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    estado=OperacionPrelacionPago.ESTADO_IN_PROGRESS,
                    created_by=request.user,
                )
            except IntegrityError:
                operacion = OperacionPrelacionPago.objects.select_for_update().get(
                    tipo=OperacionPrelacionPago.TIPO_CLIENTE,
                    entidad_id=cliente_id_int,
                    idempotency_key=idempotency_key,
                    status_model=OperacionPrelacionPago.STATUS_MODEL_ACTIVE,
                )

                if operacion.request_hash != request_hash:
                    detail = (
                        'Idempotency-Key ya fue usado con otro payload '
                        f'para cliente {cliente_id_int}.'
                    )
                    self._log_prelacion_event(
                        request,
                        event='IDEMPOTENCY_CONFLICT',
                        operacion_id=operacion.id,
                        entidad_id=cliente_id_int,
                        idempotency_key=idempotency_key,
                        total=cantidad_pagar,
                        code='IDEMPOTENCY_CONFLICT',
                        detail=detail,
                    )
                    return self._error_response(detail, 'IDEMPOTENCY_CONFLICT', status.HTTP_409_CONFLICT)

                if (
                    operacion.estado == OperacionPrelacionPago.ESTADO_COMPLETED
                    and operacion.response_payload
                ):
                    response_data = dict(operacion.response_payload)
                    response_data['idempotent_replay'] = True
                    response_data['code'] = 'IDEMPOTENT_REPLAY'
                    self._log_prelacion_event(
                        request,
                        event='IDEMPOTENT_REPLAY',
                        operacion_id=operacion.id,
                        entidad_id=cliente_id_int,
                        idempotency_key=idempotency_key,
                        total=cantidad_pagar,
                        code='IDEMPOTENT_REPLAY',
                    )
                    return Response(
                        response_data,
                        status=operacion.http_status or status.HTTP_200_OK,
                    )

                if operacion.estado == OperacionPrelacionPago.ESTADO_IN_PROGRESS:
                    detail = 'La operación con este Idempotency-Key está en progreso.'
                    self._log_prelacion_event(
                        request,
                        event='IDEMPOTENCY_IN_PROGRESS',
                        operacion_id=operacion.id,
                        entidad_id=cliente_id_int,
                        idempotency_key=idempotency_key,
                        total=cantidad_pagar,
                        code='IDEMPOTENCY_IN_PROGRESS',
                        detail=detail,
                    )
                    return self._error_response(
                        detail,
                        'IDEMPOTENCY_IN_PROGRESS',
                        status.HTTP_409_CONFLICT,
                    )

                operacion.estado = OperacionPrelacionPago.ESTADO_IN_PROGRESS
                operacion.error_message = None
                operacion.response_payload = None
                operacion.http_status = None
                operacion.completed_at = None
                operacion.save(
                    update_fields=[
                        'estado',
                        'error_message',
                        'response_payload',
                        'http_status',
                        'completed_at',
                        'updated_at',
                    ]
                )

        try:
            with transaction.atomic():
                operacion_lock = OperacionPrelacionPago.objects.select_for_update().get(id=operacion.id)

                creditos = list(
                    CreditoCliente.objects.select_for_update().filter(
                        cliente_id=cliente_id_int,
                        is_pagado=False,
                        status_model=CreditoCliente.STATUS_MODEL_ACTIVE,
                    ).order_by('fecha_vencimiento', 'fecha', 'id')
                )

                if not creditos:
                    raise ValueError('El cliente no tiene créditos activos para aplicar prelación.')

                adeudo_total = sum((c.adeudo_actual() for c in creditos), Decimal('0.00')).quantize(Decimal('0.01'))
                if cantidad_pagar > adeudo_total:
                    raise ValueError(
                        f'La cantidad a pagar (${cantidad_pagar}) excede el adeudo total (${adeudo_total}).'
                    )

                restante_global = cantidad_pagar
                aplicaciones = []
                orden_creditos = [c.id for c in creditos]

                for credito in creditos:
                    if restante_global <= Decimal('0.00'):
                        break
                    adeudo_inicial = credito.adeudo_actual()
                    if adeudo_inicial <= Decimal('0.00'):
                        continue

                    monto_aplicar = min(adeudo_inicial, restante_global).quantize(Decimal('0.01'))
                    pagos_credito, faltante = self._consume_pool(pool, monto_aplicar)
                    if faltante > Decimal('0.00'):
                        raise ValueError('No fue posible distribuir los pagos para completar la prelación.')

                    payload = {
                        'credito': credito.id,
                        'cantidad_pagar': str(monto_aplicar),
                        'pagos': pagos_credito,
                    }
                    serializer = PagoCreditoCreateSingularSerializer(data=payload, context={'request': request})
                    serializer.is_valid(raise_exception=True)
                    credito_actualizado = serializer.save()

                    aplicaciones.append({
                        'credito_id': credito_actualizado.id,
                        'fecha_vencimiento': (
                            credito_actualizado.fecha_vencimiento.isoformat()
                            if credito_actualizado.fecha_vencimiento
                            else None
                        ),
                        'monto_aplicado': float(monto_aplicar),
                        'adeudo_inicial': float(adeudo_inicial),
                        'adeudo_restante': float(credito_actualizado.adeudo_actual()),
                        'estado': credito_actualizado.estado,
                        'pagos_aplicados': [
                            {
                                'metodo_pago': p['metodo_pago'],
                                'referencia': p.get('referencia', ''),
                                'monto': float(Decimal(p['monto'])),
                            }
                            for p in pagos_credito
                        ],
                    })
                    restante_global = (restante_global - monto_aplicar).quantize(Decimal('0.01'))

                response_payload = {
                    'detail': 'Pago aplicado por prelación correctamente.',
                    'code': 'PRELACION_APPLIED',
                    'data': {
                        'cliente_id': cliente_id_int,
                        'idempotency_key': idempotency_key,
                        'request_hash': request_hash,
                        'monto_solicitado': float(cantidad_pagar),
                        'monto_aplicado': float(cantidad_pagar - restante_global),
                        'monto_no_aplicado': float(restante_global),
                        'adeudo_total_inicial': float(adeudo_total),
                        'orden_creditos': orden_creditos,
                        'aplicaciones': aplicaciones,
                        'total_creditos_afectados': len(aplicaciones),
                        'processed_at': timezone.now().isoformat(),
                    },
                }

                operacion_lock.estado = OperacionPrelacionPago.ESTADO_COMPLETED
                operacion_lock.response_payload = response_payload
                operacion_lock.http_status = status.HTTP_201_CREATED
                operacion_lock.completed_at = timezone.now()
                operacion_lock.error_message = None
                operacion_lock.save(
                    update_fields=[
                        'estado',
                        'response_payload',
                        'http_status',
                        'completed_at',
                        'error_message',
                        'updated_at',
                    ]
                )
                self._log_prelacion_event(
                    request,
                    event='PRELACION_APPLIED',
                    operacion_id=operacion_lock.id,
                    entidad_id=cliente_id_int,
                    idempotency_key=idempotency_key,
                    total=cantidad_pagar,
                    code='PRELACION_APPLIED',
                )

            return Response(response_payload, status=status.HTTP_201_CREATED)
        except Exception as exc:
            error_detail = str(exc)
            error_code = self._map_prelacion_error_code(error_detail)
            with transaction.atomic():
                operacion_error = OperacionPrelacionPago.objects.select_for_update().get(id=operacion.id)
                operacion_error.estado = OperacionPrelacionPago.ESTADO_FAILED
                operacion_error.error_message = error_detail
                operacion_error.http_status = status.HTTP_400_BAD_REQUEST
                operacion_error.completed_at = timezone.now()
                operacion_error.save(
                    update_fields=[
                        'estado',
                        'error_message',
                        'http_status',
                        'completed_at',
                        'updated_at',
                    ]
                )
            self._log_prelacion_event(
                request,
                event='PRELACION_FAILED',
                operacion_id=operacion.id,
                entidad_id=cliente_id_int,
                idempotency_key=idempotency_key,
                total=cantidad_pagar,
                code=error_code,
                detail=error_detail,
            )
            return self._error_response(error_detail, error_code, status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Registrar pago de crédito",
        description="""
        Registra un nuevo pago para un crédito.
        
        **Validaciones:**
        - El crédito debe existir y no estar liquidado
        - El monto no puede exceder el adeudo actual
        - El monto debe ser mayor a cero
        
        **Nota:** Una vez registrado, el pago no puede ser modificado ni eliminado.
        """,
        request=PagoCreditoCreateSingularSerializer,
        responses={
            201: CreditoClienteListSerializer,
            400: OpenApiResponse(description='Error de validación')
        },
        tags=['Pagos de Crédito']
    )
    def create(self, request, *args, **kwargs):
        """Registrar pago singular a un crédito"""
        serializer = self.get_serializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
            
            # El serializer retorna el crédito actualizado
            credito = serializer.save()
            credito_serializer = CreditoClienteListSerializer(credito)
            return Response(
                credito_serializer.data,
            status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'detail': str(e),
                'error_code': 'ERROR_REGISTRO_PAGO'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    def perform_create(self, serializer):
        """Guardar con usuario que crea"""
        serializer.save(created_by=self.request.user)
    
    @extend_schema(
        summary="Detalle de pago",
        description="Obtiene el detalle completo de un pago registrado.",
        responses={
            200: PagosCreditoSerializer,
            404: OpenApiResponse(description='Pago no encontrado')
        },
        tags=['Pagos de Crédito']
    )
    def retrieve(self, request, *args, **kwargs):
        """Detalle de pago"""
        return super().retrieve(request, *args, **kwargs)
    
    @extend_schema(exclude=True)
    def update(self, request, *args, **kwargs):
        """No permitir editar pagos una vez registrados (usar editar-abono en su lugar)"""
        return Response(
            {"error": "No se pueden modificar pagos directamente. Use el endpoint /editar-abono/"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    @extend_schema(exclude=True)
    def partial_update(self, request, *args, **kwargs):
        """No permitir editar pagos parcialmente"""
        return Response(
            {"error": "No se pueden modificar pagos directamente. Use el endpoint /editar-abono/"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    @extend_schema(exclude=True)
    def destroy(self, request, *args, **kwargs):
        """No permitir eliminar pagos directamente (usar cancelar-abono en su lugar)"""
        return Response(
            {"error": "No se pueden eliminar pagos directamente. Use el endpoint /cancelar-abono/"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    @extend_schema(
        summary="Editar abono de crédito",
        description="""
        Edita un abono existente de un crédito.
        
        **Proceso:**
        - Elimina el pago anterior y sus transacciones de caja
        - Revierte el monto pagado en el crédito y saldo del cliente
        - Crea los nuevos pagos con los montos indicados
        - Registra las nuevas transacciones en caja
        
        **Nota:** Esta operación es atómica, si algo falla se revierten todos los cambios.
        """,
        request=PagoCreditoUpdateSerializer,
        responses={
            200: CreditoClienteListSerializer,
            400: OpenApiResponse(description='Error de validación')
        },
        tags=['Pagos de Crédito']
    )
    @action(detail=False, methods=['put'], url_path='editar-abono')
    def editar_abono(self, request):
        """Editar un abono existente de un crédito"""
        serializer = PagoCreditoUpdateSerializer(data=request.data, context={'request': request})
        
        try:
            serializer.is_valid(raise_exception=True)
            credito = serializer.update(None, serializer.validated_data)
            credito_serializer = CreditoClienteListSerializer(credito)
            return Response(
                {
                    'detail': 'Abono actualizado exitosamente.',
                    'data': credito_serializer.data
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response({
                'detail': str(e),
                'error_code': 'ERROR_EDITAR_ABONO'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Cancelar abono de crédito",
        description="""
        Cancela un abono existente de un crédito.
        
        **Proceso:**
        - Elimina el pago y sus transacciones de caja
        - Revierte el monto pagado en el crédito
        - Revierte el saldo del cliente
        - Registra una transacción de salida en caja por la cancelación
        - Si el crédito estaba liquidado, lo reactiva
        
        **Nota:** Esta operación es atómica, si algo falla se revierten todos los cambios.
        """,
        request=PagoCreditoCancelarSerializer,
        responses={
            200: OpenApiResponse(
                description='Abono cancelado exitosamente',
                examples=[
                    OpenApiExample(
                        'Respuesta exitosa',
                        value={
                            'detail': 'Abono cancelado exitosamente.',
                            'data': {
                                'pago_id_cancelado': 1,
                                'credito_id': 5,
                                'cliente': 'Juan Pérez',
                                'monto_revertido': 1000.00,
                                'nuevo_adeudo': 2000.00,
                                'motivo': 'Error en el monto',
                                'mensaje': 'Pago #1 cancelado exitosamente.'
                            }
                        }
                    )
                ]
            ),
            400: OpenApiResponse(description='Error de validación')
        },
        tags=['Pagos de Crédito']
    )
    @action(detail=False, methods=['post'], url_path='cancelar-abono')
    def cancelar_abono(self, request):
        """Cancelar un abono de crédito"""
        serializer = PagoCreditoCancelarSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        resultado = serializer.save()
        try:
            
            return Response(
                {
                    'detail': 'Abono cancelado exitosamente.',
                    'data': resultado
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response({
                'detail': str(e),
                'error_code': 'ERROR_CANCELAR_ABONO'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Pagos por cliente",
        description="Lista todos los pagos realizados por un cliente específico.",
        parameters=[
            OpenApiParameter(
                name='cliente_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID del cliente',
                required=True
            ),
        ],
        responses={
            200: PagosCreditoSerializer(many=True)
        },
        tags=['Pagos de Crédito']
    )
    @action(detail=False, methods=['get'], url_path='por-cliente/(?P<cliente_id>[^/.]+)')
    def por_cliente(self, request, cliente_id=None):
        """Listar pagos de un cliente específico"""
        queryset = self.get_queryset().filter(credito__cliente_id=cliente_id)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Pagos por crédito",
        description="Lista todos los pagos realizados a un crédito específico.",
        parameters=[
            OpenApiParameter(
                name='credito_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID del crédito',
                required=True
            ),
        ],
        responses={
            200: PagosCreditoSerializer(many=True)
        },
        tags=['Pagos de Crédito']
    )
    @action(detail=False, methods=['get'], url_path='por-credito/(?P<credito_id>[^/.]+)')
    def por_credito(self, request, credito_id=None):
        """Listar pagos de un crédito específico"""
        queryset = self.get_queryset().filter(credito_id=credito_id)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Estadísticas de pagos",
        description="Obtiene estadísticas generales de todos los pagos registrados.",
        responses={
            200: OpenApiResponse(
                description='Estadísticas de pagos',
                examples=[
                    OpenApiExample(
                        'Ejemplo de respuesta',
                        value={
                            'total_pagos': 250,
                            'monto_total_pagado': 125000.00,
                            'por_metodo_pago': [
                                {
                                    'metodo_pago__nombre': 'Efectivo',
                                    'total': 75000.00,
                                    'cantidad': 150
                                }
                            ]
                        }
                    )
                ]
            )
        },
        tags=['Pagos de Crédito']
    )
    @action(detail=False, methods=['get'], url_path='estadisticas')
    def estadisticas(self, request):
        """Obtener estadísticas de pagos"""
        stats = PagosCredito.objects.aggregate(
            total_pagos=Count('id'),
            monto_total_pagado=Sum('monto')
        )
        
        # Pagos por método de pago
        por_metodo = PagosCredito.objects.values(
            'metodo_pago__nombre'
        ).annotate(
            total=Sum('monto'),
            cantidad=Count('id')
        ).order_by('-total')
        
        return Response({
            'total_pagos': stats['total_pagos'] or 0,
            'monto_total_pagado': float(stats['monto_total_pagado'] or 0),
            'por_metodo_pago': list(por_metodo)
        })
    
    @extend_schema(
        summary="Registrar pagos masivos",
        description="""
        Registra pagos a múltiples créditos en una sola petición.
        
        **Características:**
        - Procesa todos los pagos en una transacción atómica
        - Si algún pago falla, se revierten todos los cambios
        - Valida que el usuario tenga caja abierta
        - Valida que cada pago no exceda el adeudo del crédito
        - Registra transacciones en la caja del usuario
        
        **Estructura del request:**
        ```json
        {
            "lista": [
                {
                    "credito": 1,
                    "pagos": [
                        {
                            "metodo_pago": 1,
                            "monto": 1000.00,
                            "referencia": "REF-001"
                        }
                    ]
                }
            ]
        }
        ```
        """,
        request=PagoCreditoCreateMasivoSerializer,
        responses={
            201: OpenApiResponse(
                description='Pagos masivos procesados exitosamente',
                examples=[
                    OpenApiExample(
                        'Respuesta exitosa',
                        value={
                            'detail': 'Pagos masivos registrados exitosamente.',
                            'data': {
                                'creditos_procesados': [
                                    {
                                        'credito_id': 1,
                                        'cliente': 'Juan Pérez',
                                        'monto_pagado': 1000.00,
                                        'adeudo_restante': 500.00,
                                        'pagos_registrados': 1
                                    }
                                ],
                                'total_creditos': 2,
                                'total_pagos': 3,
                                'monto_total': 2000.00,
                                'mensaje': 'Se procesaron exitosamente 2 créditos con 3 pagos.'
                            }
                        }
                    )
                ]
            ),
            400: OpenApiResponse(description='Error de validación')
        },
        tags=['Pagos de Crédito']
    )
    @action(detail=False, methods=['post'], url_path='registrar-masivo')
    def registrar_masivo(self, request):
        """
        Registrar pagos masivos a múltiples créditos
        
        POST /api/pagos-credito/registrar-masivo/
        """
        serializer = PagoCreditoCreateMasivoSerializer(
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
                'error_code': 'ERROR_PAGOS_MASIVOS'
            }, status=status.HTTP_400_BAD_REQUEST)
