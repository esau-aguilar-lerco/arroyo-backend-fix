from rest_framework import viewsets, mixins, permissions, status, filters, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from django.db import models, transaction
from django.core.exceptions import ValidationError

from apps.base.serachFilter import MinimalSearchFilter

from apps.erp.models import Venta, VentaDetalle
from apps.erp.serializers.ventas_serializer import (
    VentaSerializer, VentaMiniSerializer, VentaEstadoSerializer,
    VentaDetalleSerializer
)

from apps.base.models import BaseModel


"""
============================================================================================
                            VIEWS DE APIS DE VENTAS
============================================================================================
"""
class VentaViewSet(viewsets.ModelViewSet):
    """
    ViewSet completo para CRUD de ventas con control de lotes
    """
    queryset = Venta.objects.all().exclude(status_model=BaseModel.STATUS_MODEL_DELETE).order_by('-id').select_related('cliente', 'ruta').prefetch_related('detalles__lotes_utilizados')
    serializer_class = VentaSerializer
    #permission_classes = [permissions.IsAuthenticated]
    filter_backends = [MinimalSearchFilter, filters.OrderingFilter]
    search_fields = ['codigo', 'cliente__nombre', 'cliente__razon_social', 'ruta__nombre']
    ordering_fields = ['created_at', 'total', 'fase']
    ordering = ['-created_at']


    def get_serializer_class(self):
        """
        Retorna el serializer apropiado según la acción
        """
        if self.action == 'cambiar_fase':
            return VentaEstadoSerializer
        elif self.action in ['list']:
            return VentaMiniSerializer
        elif self.action in ['retrieve']:
            return VentaSerializer
        return self.serializer_class
    
    @extend_schema(
        #summary="",
        description="Obtiene una lista de ventas con filtros opcionales",
        parameters=[
            OpenApiParameter(
                name='preventa',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filtrar por ventas que fueron preventa. Valores: "true", "1", "false", "0"',
                required=False,
                examples=[
                    OpenApiExample('Solo preventas', value='true'),
                    OpenApiExample('Excluir preventas', value='false'),
                ]
            ),
            OpenApiParameter(
                name='fase',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filtrar por fase de la venta',
                required=False,
                enum=['PRE_VENTA', 'EN_PROCESO','CANCELADA'],
                examples=[
                    OpenApiExample('Solo preventas', value='PRE_VENTA'),
                    OpenApiExample('Solo terminadas', value='TERMINADA'),
                ]
            ),
            OpenApiParameter(
                name='cliente',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='ID del cliente para filtrar sus ventas',
                required=False,
                examples=[
                    OpenApiExample('Cliente específico', value=123),
                ]
            ),
            OpenApiParameter(
                name='ruta',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='ID de la ruta para filtrar ventas de esa ruta',
                required=False,
                examples=[
                    OpenApiExample('Ruta específica', value=5),
                ]
            ),
            OpenApiParameter(
                name='fecha_desde',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Filtrar ventas desde esta fecha (formato: YYYY-MM-DD)',
                required=False,
                examples=[
                    OpenApiExample('Desde 1 enero 2024', value='2024-01-01'),
                ]
            ),
            OpenApiParameter(
                name='fecha_hasta',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Filtrar ventas hasta esta fecha (formato: YYYY-MM-DD)',
                required=False,
                examples=[
                    OpenApiExample('Hasta hoy', value='2024-12-31'),
                ]
            ),
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Búsqueda por código de venta, nombre de cliente, razón social o nombre de ruta',
                required=False,
                examples=[
                    OpenApiExample('Por código', value='VNT-001'),
                    OpenApiExample('Por cliente', value='Juan Pérez'),
                ]
            ),
            OpenApiParameter(
                name='ordering',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Ordenar resultados por campo específico. Usar "-" para orden descendente',
                required=False,
                enum=['created_at', '-created_at', 'total', '-total', 'fase', '-fase'],
                examples=[
                    OpenApiExample('Más recientes primero', value='-created_at'),
                    OpenApiExample('Menor a mayor monto', value='total'),
                ]
            ),
        ],
        responses={
            200: VentaMiniSerializer(many=True),
            400: inline_serializer(
                name='VentasListError',
                fields={'detail': serializers.CharField()}
            )
        }
    )  
    def list(self, request, *args, **kwargs):
        """
        Listar ventas con filtros opcionales
        """
        queryset = self.filter_queryset(self.get_queryset())

        # Filtro de preventa
        preventa = request.query_params.get('preventa', None)
        if preventa is not None:
            if preventa.lower() in ['true', '1']:
                queryset = queryset.filter(was_preventa=True)
            elif preventa.lower() in ['false', '0']:
                queryset = queryset.filter(was_preventa=False)
                
        # Filtro de is_terminada
        is_terminada = request.query_params.get('is_terminada', None)
        if is_terminada is not None:
            if is_terminada.lower() in ['true', '1']:
                queryset = queryset.filter(is_terminada=True)
            elif is_terminada.lower() in ['false', '0']:
                queryset = queryset.filter(is_terminada=False)

        # Filtros adicionales
        fase = request.query_params.get('fase', None)
        if fase:
            queryset = queryset.filter(fase=fase)
        
        cliente_id = request.query_params.get('cliente', None)
        if cliente_id:
            try:
                queryset = queryset.filter(cliente_id=int(cliente_id))
            except (ValueError, TypeError):
                pass
        
        ruta_id = request.query_params.get('ruta', None)
        if ruta_id:
            try:
                queryset = queryset.filter(ruta_id=int(ruta_id))
            except (ValueError, TypeError):
                pass

        # Filtro de fechas
        fecha_desde = request.query_params.get('fecha_desde', None)
        fecha_hasta = request.query_params.get('fecha_hasta', None)
        
        if fecha_desde:
            queryset = queryset.filter(created_at__date__gte=fecha_desde)
        if fecha_hasta:
            queryset = queryset.filter(created_at__date__lte=fecha_hasta)
            
        almacen_user = request.user.almacen
        if almacen_user:
            queryset = queryset.filter(almacen=almacen_user)

        # Paginación
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        """
        Obtener una venta específica por ID con todos sus detalles y lotes
        """
        instance = self.get_object()
        if self.is_respuesta_404():
            return self.respuesta_404()
        
        #optner el serach
        is_terminada = request.query_params.get('is_terminada', None)
        
        if is_terminada is not None:
            is_terminada = is_terminada.lower() in ['true', '1']
            print("is_terminada:", is_terminada)
            if not  is_terminada and  instance.ya_terminada:
                return self.respuesta_404() 

        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        """
        Crear nueva venta con detalles
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        response_serializer = self.get_serializer(instance)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """
        Actualizar venta (solo campos básicos, no detalles)
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        if self.is_respuesta_404():
            return self.respuesta_404()

        # No permitir editar ventas terminadas o canceladas
        if instance.fase in [Venta.FASE_TERMINADA, Venta.FASE_CANCELADA]:
            return Response(
                {"detail": "No se pueden editar ventas terminadas o canceladas."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=['patch'],
        url_path='fase'
    )
    @extend_schema(
        request=VentaEstadoSerializer,
        responses={200: VentaSerializer}
    )
    def cambiar_fase(self, request, pk=None):
        """
        Cambiar la fase de una venta (PRE_VENTA → EN_PROCESO → TERMINADA)
        """
        instance = self.get_object()
        if self.is_respuesta_404():
            return self.respuesta_404()

        serializer = VentaEstadoSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        try:
            with transaction.atomic():
                instance = serializer.save()
                
                # Si cambió a TERMINADA, el signal procesará automáticamente el inventario
                
        except ValidationError as e:
            # Capturar errores de validación de Django (incluyendo los del signal)
            error_message = str(e)
            if hasattr(e, 'message_dict'):
                error_message = '; '.join([f"{field}: {', '.join(errors)}" for field, errors in e.message_dict.items()])
            elif hasattr(e, 'messages'):
                error_message = '; '.join(e.messages)
            
            return Response(
                {"detail": error_message},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"detail": f"Error al cambiar fase: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Retornar la venta actualizada completa
        response_serializer = self.get_serializer(instance)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        """
        Eliminación lógica de venta
        """
        instance = self.get_object()
        if self.is_respuesta_404():
            return self.respuesta_404()
        
        # No permitir eliminar ventas terminadas
        if instance.fase == Venta.FASE_TERMINADA:
            return Response(
                {"detail": "No se pueden eliminar ventas terminadas."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Eliminación lógica
        instance.status_model = BaseModel.STATUS_MODEL_DELETE
        instance.save(update_fields=['status_model'])
        
        return Response(
            {"detail": "Venta eliminada correctamente."},
            status=status.HTTP_200_OK
        )

    def is_respuesta_404(self):
        """
        Verificar si la venta está eliminada lógicamente
        """
        instance = self.get_object()
        return instance.status_model == BaseModel.STATUS_MODEL_DELETE

    def respuesta_404(self):
        """
        Respuesta estándar para recursos no encontrados
        """
        return Response(
            {"detail": "Venta no encontrada."},
            status=status.HTTP_404_NOT_FOUND
        )

    @extend_schema(
        summary="Cancelar venta",
        description="""
        Cancela una venta existente cambiando su fase a CANCELADA.
        
        **Validaciones:**
        - La venta no debe estar ya cancelada
        - Solo ventas en fases válidas pueden ser canceladas
        
        **Efectos:**
        - Cambia la fase de la venta a CANCELADA
        - Puede revertir cambios en inventario (según lógica implementada)
        - Puede generar notificaciones o registros adicionales
        
        **Nota:** Esta operación puede desencadenar signals que reviertan el inventario automáticamente.
        """,
        request=None,
        responses={
            200: inline_serializer(
                name='CancelarVentaSuccess',
                fields={
                    'detail': serializers.CharField(default='Venta cancelada correctamente'),
                    'venta': VentaSerializer()
                }
            ),
            400: inline_serializer(
                name='CancelarVentaError',
                fields={
                    'detail': serializers.CharField()
                }
            ),
            404: inline_serializer(
                name='VentaNotFound',
                fields={
                    'detail': serializers.CharField(default='Venta no encontrada.')
                }
            )
        },
        examples=[
            OpenApiExample(
                'Venta ya cancelada',
                value={'detail': 'La venta ya está cancelada.'},
                response_only=True,
                status_codes=['400']
            ),
            OpenApiExample(
                'Cancelación exitosa',
                value={
                    'detail': 'Venta cancelada correctamente',
                    'venta': {
                        'id': 123,
                        'codigo': 'VNT-001',
                        'fase': 'CANCELADA',
                        'total': '1500.00'
                    }
                },
                response_only=True,
                status_codes=['200']
            )
        ]
    )
    @action(
        detail=True,
        methods=['post'],
        url_path='cancelar'
    )
    def cancelar_venta(self, request, pk=None):
        """
        Lógica para cancelar una venta
        """
        try:
            venta = self.get_object()
        except Exception:
            return Response(
                {"detail": "Venta no encontrada."},
                status=status.HTTP_404_NOT_FOUND
            )

        if venta.fase == Venta.FASE_CANCELADA:
            return Response(
                {"detail": "La venta ya está cancelada."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Lógica adicional para revertir inventario si es necesario
        venta.fase = Venta.FASE_CANCELADA
        venta.save(update_fields=['fase'])
        # Aquí se podrían agregar señales o lógica para revertir inventario, notificaciones, etc.

        serializer = VentaSerializer(venta)
        return Response(
            {"detail": "Venta cancelada correctamente", "venta": serializer.data},
            status=status.HTTP_200_OK
        )
        
    @extend_schema(
        summary="Cancelar ventas masivamente",
        description="""
        Cancela múltiples ventas en una sola operación cambiando su fase a CANCELADA.
        
        **Proceso:**
        1. Recibe un array de IDs de ventas
        2. Procesa cada venta individualmente
        3. Valida que no esté ya cancelada
        4. Cambia la fase a CANCELADA
        5. Retorna el resultado de cada operación
        
        **Validaciones por venta:**
        - La venta debe existir
        - No debe estar ya cancelada
        
        **Efectos:**
        - Cambia la fase de cada venta a CANCELADA
        - Puede revertir cambios en inventario (según signals configurados)
        - Procesa todas las ventas independientemente (no transaccional)
        
        **Nota:** 
        - Si una venta falla, las demás continúan procesándose
        - Cada resultado indica el estado individual de cada venta
        - Esta operación puede desencadenar signals que reviertan el inventario automáticamente
        """,
        request=inline_serializer(
            name='CancelarVentasMasivoRequest',
            fields={
                'ventas': serializers.ListField(
                    child=serializers.IntegerField(),
                    help_text='Array de IDs de ventas a cancelar',
                    min_length=1
                )
            }
        ),
        responses={
            200: inline_serializer(
                name='CancelarVentasMasivoResponse',
                fields={
                    'results': serializers.ListField(
                        child=inline_serializer(
                            name='ResultadoVentaCancelacion',
                            fields={
                                'venta_id': serializers.IntegerField(),
                                'status': serializers.ChoiceField(choices=['success', 'error']),
                                'detail': serializers.CharField()
                            }
                        )
                    )
                }
            )
        },
        examples=[
            OpenApiExample(
                'Request ejemplo',
                value={
                    'ventas': [123, 124, 125]
                },
                request_only=True
            ),
            OpenApiExample(
                'Response exitoso mixto',
                value=[
                    {
                        'venta_id': 123,
                        'status': 'success',
                        'detail': 'Venta cancelada correctamente.'
                    },
                    {
                        'venta_id': 124,
                        'status': 'error',
                        'detail': 'La venta ya está cancelada.'
                    },
                    {
                        'venta_id': 125,
                        'status': 'error',
                        'detail': 'Venta no encontrada.'
                    }
                ],
                response_only=True,
                status_codes=['200']
            ),
            OpenApiExample(
                'Response todo exitoso',
                value=[
                    {
                        'venta_id': 123,
                        'status': 'success',
                        'detail': 'Venta cancelada correctamente.'
                    },
                    {
                        'venta_id': 124,
                        'status': 'success',
                        'detail': 'Venta cancelada correctamente.'
                    },
                    {
                        'venta_id': 125,
                        'status': 'success',
                        'detail': 'Venta cancelada correctamente.'
                    }
                ],
                response_only=True,
                status_codes=['200']
            )
        ],
        tags=['Ventas']
    )
    @action(
        detail=False,
        methods=['post'],
        url_path='cancelar-masivo'
    )
    def cancelar_venta_masivo(self, request):
        """
        Lógica para cancelar múltiples ventas
        """
        ventas = request.data.get('ventas', [])
        
        if not ventas:
            return Response(
                {"detail": "Debe proporcionar al menos un ID de venta."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        resultados = []
        
        for venta_id in ventas:
            try:
                venta = Venta.objects.get(id=venta_id)
                
                if venta.fase == Venta.FASE_CANCELADA:
                    resultados.append({
                        'venta_id': venta_id,
                        'status': 'error',
                        'detail': 'La venta ya está cancelada.'
                    })
                    continue
                
                # Lógica adicional para revertir inventario si es necesario
                venta.fase = Venta.FASE_CANCELADA
                venta.save(update_fields=['fase'])
                # Aquí se podrían agregar señales o lógica para revertir inventario, notificaciones, etc.

                resultados.append({
                    'venta_id': venta_id,
                    'status': 'success',
                    'detail': 'Venta cancelada correctamente.'
                })
                
            except Venta.DoesNotExist:
                resultados.append({
                    'venta_id': venta_id,
                    'status': 'error',
                    'detail': 'Venta no encontrada.'
                })
            except Exception as e:
                resultados.append({
                    'venta_id': venta_id,
                    'status': 'error',
                    'detail': f'Error inesperado: {str(e)}'
                })
        
        return Response(resultados, status=status.HTTP_200_OK)
        
    @extend_schema(
        responses={200: inline_serializer(
            name='VentasEstadisticas',
            fields={
                'total_ventas': serializers.IntegerField(),
                'ventas_por_fase': serializers.DictField(),
                'total_monto': serializers.DecimalField(max_digits=15, decimal_places=2),
                'promedio_venta': serializers.DecimalField(max_digits=15, decimal_places=2),
                'ventas_con_lotes_completos': serializers.IntegerField(),
            }
        )}
    )
    @action(detail=False, methods=['get'], url_path='estadisticas')
    def estadisticas(self, request):
        """
        Obtener estadísticas generales de ventas
        """
        queryset = self.get_queryset()
        
        # Ventas por fase
        fases = {}
        for fase_code, fase_name in Venta.FASE_CHOICES:
            fases[fase_name] = queryset.filter(fase=fase_code).count()
        
        total_ventas = queryset.count()
        total_monto = queryset.aggregate(total=models.Sum('total'))['total'] or 0
        promedio = total_monto / total_ventas if total_ventas > 0 else 0
        
        # Contar ventas con lotes completos
        ventas_completas = 0
        for venta in queryset:
            if all(detalle.lotes_completos for detalle in venta.detalles.all()):
                ventas_completas += 1
        
        stats = {
            'total_ventas': total_ventas,
            'ventas_por_fase': fases,
            'total_monto': total_monto,
            'promedio_venta': promedio,
            'ventas_con_lotes_completos': ventas_completas,
        }
        
        return Response(stats, status=status.HTTP_200_OK)


class VentaMiniViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    ViewSet para listar ventas de forma resumida
    """
    queryset = Venta.objects.all().exclude(status_model=BaseModel.STATUS_MODEL_DELETE).order_by('-id').select_related('cliente', 'ruta')
    serializer_class = VentaMiniSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [MinimalSearchFilter]
    search_fields = ['codigo', 'cliente__nombre', 'cliente__razon_social']
    pagination_class = None

    def list(self, request, *args, **kwargs):
        """
        Listar ventas básicas con filtros
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Filtros adicionales
        fase = request.query_params.get('fase', None)
        if fase:
            queryset = queryset.filter(fase=fase)
        
        activo = request.query_params.get('activo', None)
        if activo is not None:
            if activo.lower() in ['true', '1']:
                queryset = queryset.filter(status_model=BaseModel.STATUS_MODEL_ACTIVE)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)



"""
============================================================================================
                        VIEWS DE APIS DE DETALLES DE VENTA
============================================================================================
"""
class VentaDetalleViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar detalles de venta individualmente
    """
    queryset = VentaDetalle.objects.all().select_related('venta', 'producto').prefetch_related('lotes_utilizados')
    serializer_class = VentaDetalleSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['producto__nombre', 'venta__codigo']

    def get_queryset(self):
        """
        Filtrar por venta si se proporciona
        """
        queryset = super().get_queryset()
        venta_id = self.request.query_params.get('venta', None)
        
        if venta_id:
            try:
                queryset = queryset.filter(venta_id=int(venta_id))
            except (ValueError, TypeError):
                pass
        
        return queryset

    @action(detail=True, methods=['post'], url_path='asignar-lotes')
    @extend_schema(
        request=inline_serializer(
            name='AsignarLotesDetalleRequest',
            fields={
                'almacen_id': serializers.IntegerField(required=False)
            }
        ),
        responses={200: VentaDetalleSerializer}
    )
    def asignar_lotes(self, request, pk=None):
        """
        Asignar lotes automáticamente a un detalle específico
        """
        instance = self.get_object()
        almacen_id = request.data.get('almacen_id')
        
        almacen = None
        if almacen_id:
            from apps.erp.models import Almacen
            try:
                almacen = Almacen.objects.get(id=almacen_id)
            except Almacen.DoesNotExist:
                return Response(
                    {"detail": "Almacén no encontrado."},
                    status=status.HTTP_404_NOT_FOUND
                )
        elif instance.venta.ruta:
            almacen = instance.venta.ruta.almacen
        elif instance.venta.almacen:
            almacen = instance.venta.almacen

        try:
            with transaction.atomic():
                # Limpiar asignaciones previas
                instance.lotes_utilizados.all().delete()
                
                # Asignar nuevos lotes
                exito = instance.asignar_lotes_automatico(almacen)
                
                response_serializer = self.get_serializer(instance)
                return Response({
                    'detalle': response_serializer.data,
                    'asignacion_completa': exito,
                    'cantidad_pendiente': instance.cantidad_pendiente_asignar
                }, status=status.HTTP_200_OK)
                
        except Exception as e:
            return Response(
                {"detail": f"Error al asignar lotes: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


