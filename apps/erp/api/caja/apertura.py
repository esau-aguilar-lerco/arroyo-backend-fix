from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from django.db import transaction
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample



from apps.erp.models import CajaApertura,Caja
from apps.erp.serializers.caja.apertura import CajaAperturaSerializer, CajaAperturaMiniSerializer

from apps.base.serachFilter import MinimalSearchFilter


class AperturaCajaMiniViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = CajaApertura.objects.filter(status_model=CajaApertura.STATUS_MODEL_ACTIVE,caja__tipo=Caja.SUCURSAL)
    serializer_class = CajaAperturaMiniSerializer
    #permission_classes = []  # Permitir acceso sin autenticación    
    pagination_class = None  # Desactivar paginación
    search_fields = ['caja__nombre', 'id']
    filter_backends = [MinimalSearchFilter]
    


class AperturaCajaViewSet(
    mixins.ListModelMixin,      # GET /api/aperturas-caja/
    mixins.RetrieveModelMixin,  # GET /api/aperturas-caja/{id}/
    mixins.UpdateModelMixin,    # PUT/PATCH /api/aperturas-caja/{id}/
    mixins.CreateModelMixin,    # POST /api/aperturas-caja/
    viewsets.GenericViewSet
):
    serializer_class = CajaAperturaSerializer
    search_fields = ['caja__nombre', 'id', 'usuario__first_name', 'usuario__last_name']
    filter_backends = [MinimalSearchFilter]
    
    def get_queryset(self):
        """
        Optimizar queryset con select_related y prefetch_related para evitar N+1 queries
        Incluye anotaciones para estadísticas precalculadas
        """
        from django.db.models import Sum, Q, Prefetch
        from apps.erp.models import CajaTransaccion
        
        # Prefetch optimizado para transacciones con sus relaciones
        transacciones_prefetch = Prefetch(
            'transacciones',
            queryset=CajaTransaccion.objects.filter(
                status_model=CajaTransaccion.STATUS_MODEL_ACTIVE
            ).select_related('metodo_pago', 'created_by')
        )
        
        queryset = CajaApertura.objects.filter(
            status_model=CajaApertura.STATUS_MODEL_ACTIVE
        ).select_related(
            'caja',                    # FK: Caja relacionada
            'usuario',                 # FK: Usuario cajero
            'created_by',              # FK: Usuario que creó la apertura
            'updated_by'               # FK: Usuario que actualizó/cerró
        ).prefetch_related(
            transacciones_prefetch     # Transacciones optimizadas
        ).annotate(
            # Anotar totales para evitar queries adicionales en el serializer
            _total_ingresos=Sum(
                'transacciones__monto',
                filter=Q(
                    transacciones__tipo=CajaTransaccion.TIPO_ENTRADA,
                    transacciones__status_model=CajaTransaccion.STATUS_MODEL_ACTIVE
                )
            ),
            _total_salidas=Sum(
                'transacciones__monto',
                filter=Q(
                    transacciones__tipo=CajaTransaccion.TIPO_SALIDA,
                    transacciones__status_model=CajaTransaccion.STATUS_MODEL_ACTIVE
                )
            )
        ).order_by('-fecha_apertura')
        
        return queryset
    
    #modificar el serializer a utilizar 
    def get_serializer_class(self):
        if self.action in ['list']:
            return CajaAperturaMiniSerializer
        return CajaAperturaSerializer
    @extend_schema(
        summary="Cerrar apertura de caja",
        description="""
        Cierra una apertura de caja registrando el monto final y calculando la diferencia.
        
        **Proceso:**
        1. Valida que la caja esté abierta
        2. Registra el monto final contado
        3. Calcula el monto esperado (inicial + entradas - salidas)
        4. Calcula la diferencia (monto_final - monto_esperado)
        5. Registra el usuario que cierra
        6. Marca la apertura como cerrada
        
        **Validaciones:**
        - La caja debe estar abierta (is_abierta=True)
        - El monto_final es obligatorio
        - El monto_final no puede ser negativo
        """,
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'monto_final': {
                        'type': 'number',
                        'format': 'decimal',
                        'description': 'Monto contado físicamente al cerrar la caja',
                        'example': 1500.00
                    },
                    'observaciones': {
                        'type': 'string',
                        'description': 'Observaciones sobre el cierre (opcional)',
                        'example': 'Cierre normal del turno'
                    }
                },
                'required': ['monto_final']
            }
        },
        responses={
            200: OpenApiResponse(
                response=CajaAperturaSerializer,
                description='Caja cerrada exitosamente',
                examples=[
                    OpenApiExample(
                        'Cierre exitoso',
                        value={
                            'detail': 'Caja cerrada exitosamente.',
                            'data': {
                                'id': 1,
                                'caja': 1,
                                'caja_name': 'CAJA PRINCIPAL',
                                'usuario': 5,
                                'usuario_name': 'Juan Pérez',
                                'monto_inicial': 1000.00,
                                'monto_final': 1500.00,
                                'monto_esperado': 1450.00,
                                'diferencia': 50.00,
                                'is_abierta': False,
                                'fecha_apertura': '01-11-2025 08:00:00',
                                'fecha_cierre': '01-11-2025 18:00:00',
                                'observaciones': 'Cierre normal del turno',
                                'cerrada_por': 5,
                                'cerrada_por_name': 'María López'
                            }
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                description='Error de validación',
                examples=[
                    OpenApiExample(
                        'Caja ya cerrada',
                        value={
                            'detail': 'Esta caja ya está cerrada.',
                            'error_code': 'CAJA_YA_CERRADA'
                        }
                    ),
                    OpenApiExample(
                        'Monto final requerido',
                        value={
                            'detail': 'El campo monto_final es requerido.',
                            'error_code': 'MONTO_FINAL_REQUERIDO'
                        }
                    ),
                    OpenApiExample(
                        'Monto negativo',
                        value={
                            'detail': 'El monto final no puede ser negativo.',
                            'error_code': 'MONTO_NEGATIVO'
                        }
                    )
                ]
            ),
            404: OpenApiResponse(
                description='Apertura no encontrada'
            ),
            500: OpenApiResponse(
                description='Error interno del servidor',
                examples=[
                    OpenApiExample(
                        'Error interno',
                        value={
                            'detail': 'Error al cerrar la caja: [detalle del error]',
                            'error_code': 'ERROR_INTERNO'
                        }
                    )
                ]
            )
        },
        tags=['Cajas - Aperturas']
    )
    @action(detail=True, methods=['post'], url_path='cerrar')
    def cerrar_caja(self, request, pk=None):
       
        apertura = self.get_object()
        
        # Validar que la caja esté abierta
        if not apertura.is_abierta:
            return Response(
                {
                    'detail': 'Esta caja ya está cerrada.',
                    'error_code': 'CAJA_YA_CERRADA'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Obtener datos del request
        monto_final = request.data.get('monto_final')
        #observaciones = request.data.get('observaciones', '')
        
        # Validar monto_final
        if monto_final is None:
            return Response(
                {
                    'detail': 'El campo monto_final es requerido.',
                    'error_code': 'MONTO_FINAL_REQUERIDO'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            monto_final = float(monto_final)
            
            if monto_final < 0:
                return Response(
                    {
                        'detail': 'El monto final no puede ser negativo.',
                        'error_code': 'MONTO_NEGATIVO'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            from apps.erp.models import Venta
            
        
            #trae todas las ventas de hoy que no esten termindas y que no sean ignoradas 
            #count_ventas = Venta.ventas_abiertas_count(cajero=request.user)
            #if int(count_ventas) > 0:
            #    return Response(
            #        {
            #            'detail': f'No se puede cerrar la caja. Existen {count_ventas} ventas abiertas que no han sido finalizadas.',
            #            'error_code': 'VENTAS_ABIERTAS_EXISTENTES'
            #        },
            #        status=status.HTTP_400_BAD_REQUEST
            #    )
            # Cerrar caja con transacción
            with transaction.atomic():
                apertura.cerrar_caja(
                    monto_final=monto_final,
                    usuario_cierre=request.user,
                    #observaciones=observaciones
                )
            
            # Serializar y retornar
            serializer = self.get_serializer(apertura)
            return Response(
                {
                    'detail': 'Caja cerrada exitosamente.',
                    'data': serializer.data
                },
                status=status.HTTP_200_OK
            )
            
        except ValueError as e:
            return Response(
                {
                    'detail': str(e),
                    'error_code': 'ERROR_VALIDACION'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {
                    'detail': f'Error al cerrar la caja: {str(e)}',
                    'error_code': 'ERROR_INTERNO'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )