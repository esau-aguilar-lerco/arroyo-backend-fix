from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from apps.erp.models import CajaTransaccion, PagosVenta, CajaApertura, Venta
from apps.erp.serializers.caja.movimientos import (
    MovimientoCajaVentaSerializer,
    MovimientoCajaTransaccionSerializer,
    SalidaCajaGastoSerializer
)

class MovimientoCajaViewSet(viewsets.GenericViewSet):
    """
    ViewSet para manejar movimientos de caja
    """
    permission_classes = [IsAuthenticated]
    serializer_class = MovimientoCajaVentaSerializer
    
    @extend_schema(
        summary="Registrar pago de venta en caja",
        description="""
        Registra uno o varios pagos de una venta en la caja del usuario.
        
        **Proceso:**
        1. Valida que el usuario tenga una caja abierta
        2. Valida que los pagos no excedan el adeudo
        3. Crea transacciones en CajaTransaccion (ENTRADA)
        4. Crea registros en PagosVenta
        5. Actualiza el total_pagado de la venta
        6. Si el adeudo llega a 0, marca la venta como TERMINADA
        
        **Validaciones:**
        - El usuario debe tener una caja abierta
        - La venta no debe estar cancelada
        - El total de pagos no puede exceder el adeudo
        - Cada monto debe ser mayor a cero
        """,
        request=MovimientoCajaVentaSerializer,
        responses={
            204: OpenApiResponse(
                description='Pago registrado exitosamente',
                examples=[
                    OpenApiExample(
                        'Pago exitoso',
                        value={
                            'detail': 'Pago registrado exitosamente.',
                            'venta_codigo': 'VENTA-00000123',
                            'total_pagado': 1500.00,
                            'adeudo_restante': 500.00,
                            'caja': 'CAJA PRINCIPAL',
                            'cajero': 'Juan Pérez',
                            'transacciones': [
                                {
                                    'id': 1,
                                    'metodo_pago': 'EFECTIVO',
                                    'monto': 1000.00
                                },
                                {
                                    'id': 2,
                                    'metodo_pago': 'TARJETA',
                                    'monto': 500.00
                                }
                            ]
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                description='Error de validación',
                examples=[
                    OpenApiExample(
                        'Sin caja abierta',
                        value={
                            'detail': 'El usuario Juan Pérez no tiene una caja abierta.',
                            'error_code': 'SIN_CAJA_ABIERTA'
                        }
                    ),
                    OpenApiExample(
                        'Excede adeudo',
                        value={
                            'pagos': 'El total de pagos ($2000.00) excede el adeudo de la venta ($1500.00).',
                            'error_code': 'EXCEDE_ADEUDO',
                            'adeudo': '1500.00',
                            'total_pagos': '2000.00'
                        }
                    )
                ]
            )
        },
        tags=['Cajas - Movimientos']
    )
    @action(detail=False, methods=['post'], url_path='registrar-pago-venta')
    def registrar_pago_venta(self, request):
        """
        Registrar pago de una venta en la caja del usuario
        
        POST /api/movimientos-caja/registrar-pago-venta/
        
        Body:
        {
            "venta": 123,
            "pagos": [
                {
                    "metodo_pago": 1,
                    "monto": 1000.00,
                    "referencia": "TRANS-12345"
                },
                {
                    "metodo_pago": 2,
                    "monto": 500.00
                }
            ]
        }
        """
        serializer = self.get_serializer(data=request.data)
        
        
        #serializer.is_valid(raise_exception=True)
        #serializer.save()
        ## No Content response, los detalles se consultan aparte
        #return Response({
        #    'success': True,
        #    'message': 'Pago registrado exitosamente.'
        #    }, status=status.HTTP_201_CREATED)
        
        try:
            serializer.is_valid(raise_exception=True)
            serializer.save()
            # No Content response, los detalles se consultan aparte
            return Response({
                'success': True,
                'message': 'Pago registrado exitosamente.'
                }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({
                'success': False,
                'detail': str(e),
                'error_code': 'ERROR_REGISTRO_PAGO'
            }, status=status.HTTP_400_BAD_REQUEST)


    @extend_schema(
        summary="Registrar salida o gasto de caja",
        description="""
        Registra una salida o gasto de la caja del usuario.
        
        **Tipos de transacción:**
        - **SALIDA**: Salida genérica de efectivo (no requiere gasto_tipo)
        - **GASTO**: Gasto específico (requiere gasto_tipo)
        
        **Tipos de gasto disponibles:**
        - GASTO VIATICO XALAPA
        - GASTO VIATICO CORDOBA
        - GASTO INSUMOS PLASTICOS
        - GASTO MECANICO
        - OTRO
        
        **Proceso:**
        1. Valida que el usuario tenga una caja abierta
        2. Si tipo=GASTO, valida que se proporcione gasto_tipo
        3. Crea la transacción en CajaTransaccion
        4. Registra la salida con el método de pago (por defecto EFECTIVO)
        
        **Validaciones:**
        - El usuario debe tener una caja abierta
        - El monto debe ser mayor a cero
        - Si tipo=GASTO, gasto_tipo es obligatorio
        """,
        request=SalidaCajaGastoSerializer,
        responses={
            201: OpenApiResponse(
                description='Salida/Gasto registrado exitosamente',
                examples=[
                    OpenApiExample(
                        'Gasto registrado',
                        value={
                            'success': True,
                            'message': 'Salida/Gasto registrado exitosamente.',
                            'transaccion_id': 123,
                            'tipo': 'GASTO',
                            'monto': 500.00
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                description='Error de validación',
                examples=[
                    OpenApiExample(
                        'Sin caja abierta',
                        value={
                            'detail': 'El usuario Juan Pérez no tiene una caja abierta.',
                            'error_code': 'SIN_CAJA_ABIERTA'
                        }
                    ),
                    OpenApiExample(
                        'Falta gasto_tipo',
                        value={
                            'gasto_tipo': 'El campo gasto_tipo es obligatorio cuando el tipo de transacción es GASTO.',
                            'error_code': 'GASTO_TIPO_OBLIGATORIO'
                        }
                    )
                ]
            )
        },
        tags=['Cajas - Movimientos']
    )
    @action(detail=False, methods=['post'], url_path='registrar-salida-gasto')
    def registrar_salida_gasto(self, request):
        """
        Registrar una salida o gasto de caja
        
        POST /api/movimientos-caja/registrar-salida-gasto/
        
        Body (SALIDA genérica):
        {
            "tipo": "SALIDA",
            "monto": 500.00,
            "descripcion": "Compra de insumos",
            "referencia": "FACT-12345"
        }
        
        Body (GASTO específico):
        {
            "tipo": "GASTO",
            "gasto_tipo": "GASTO VIATICO XALAPA",
            "monto": 1000.00,
            "descripcion": "Viáticos para viaje a Xalapa",
            "metodo_pago": 1
        }
        """
        serializer = SalidaCajaGastoSerializer(data=request.data, context={'request': request})
        
        try:
            serializer.is_valid(raise_exception=True)
            transaccion = serializer.save()
            
            return Response({
                'success': True,
                'message': 'Salida/Gasto registrado exitosamente.',
                'transaccion_id': transaccion.id,
                'tipo': transaccion.tipo,
                'monto': transaccion.monto
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'success': False,
                'detail': str(e),
                'error_code': 'ERROR_REGISTRO_SALIDA'
            }, status=status.HTTP_400_BAD_REQUEST)



class TransaccionCajaViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    ViewSet para listar transacciones de caja con filtro por apertura
    Solo permite operación LIST
    """
    permission_classes = [IsAuthenticated]
    serializer_class = MovimientoCajaTransaccionSerializer
    
    def get_queryset(self):
        """
        Optimizar el queryset con select_related para evitar N+1 queries
        Permite filtrar por apertura_id mediante query parameter
        """
        queryset = CajaTransaccion.objects.select_related(
            'caja_apertura',           # Relación FK con CajaApertura
            'caja_apertura__caja',     # Relación FK con Caja a través de CajaApertura
            'caja_apertura__usuario',  # Relación FK con Usuario a través de CajaApertura
            'metodo_pago',             # Relación FK con MetodoPago
            'created_by',              # Usuario que creó la transacción
            'updated_by'               # Usuario que actualizó la transacción
        ).filter(
            status_model=CajaTransaccion.STATUS_MODEL_ACTIVE
        ).order_by('-created_at')
        
        # Filtro por apertura_id
        apertura_id = self.request.query_params.get('apertura_id')
        if apertura_id:
            queryset = queryset.filter(caja_apertura_id=apertura_id)
        
        # Filtro por tipo (ENTRADA o SALIDA)
        tipo = self.request.query_params.get('tipo')
        if tipo and tipo in ['ENTRADA', 'SALIDA']:
            queryset = queryset.filter(tipo=tipo)
        
        # Filtro por método de pago
        metodo_pago_id = self.request.query_params.get('metodo_pago')
        if metodo_pago_id:
            queryset = queryset.filter(metodo_pago_id=metodo_pago_id)
        
        return queryset
    
    @extend_schema(
        summary="Listar transacciones de caja",
        description="""
        Obtiene una lista de transacciones de caja con filtros opcionales.
        
        **Filtros disponibles:**
        - `apertura_id`: ID de la apertura de caja (recomendado)
        - `tipo`: Tipo de transacción (ENTRADA o SALIDA)
        - `metodo_pago`: ID del método de pago
        
        **Respuesta incluye:**
        - Lista de transacciones ordenadas por fecha (más recientes primero)
        - Información del método de pago
        - Detalles de la apertura de caja
        """,
        parameters=[
            OpenApiParameter(
                name='apertura_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description='ID de la apertura de caja para filtrar transacciones'
            ),
            OpenApiParameter(
                name='tipo',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Tipo de transacción',
                enum=['ENTRADA', 'SALIDA']
            ),
            OpenApiParameter(
                name='metodo_pago',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description='ID del método de pago'
            ),
        ],
        responses={
            200: MovimientoCajaTransaccionSerializer(many=True)
        },
        tags=['Cajas - Transacciones']
    )
    def list(self, request, *args, **kwargs):
        """
        Listar transacciones de caja con filtros
        
        GET /api/transacciones-caja/
        GET /api/transacciones-caja/?apertura_id=123
        GET /api/transacciones-caja/?apertura_id=123&tipo=ENTRADA
        GET /api/transacciones-caja/?apertura_id=123&metodo_pago=1
        """
        return super().list(request, *args, **kwargs)
