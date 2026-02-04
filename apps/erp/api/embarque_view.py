from rest_framework import status, permissions, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from django.db import transaction
from django.db.models import Sum
from django.core.exceptions import ValidationError

from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from apps.base.models import BaseModel
from apps.erp.models import Venta, Rutas
from apps.erp.serializers.embarque.embarque_serializer import (
    EmbarqueSerializer, EmbarqueMiniSerializer, VentasEmbarqueSubidaRutaSerializer
)


"""
============================================================================================
                            VIEWS DE APIS DE EMBARQUE
============================================================================================
"""

class EmbarqueListCreateAPIView(APIView):
    """
    Vista para listar embarques disponibles y crear nuevos embarques
    """
    # permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Crear nuevo embarque",
        description="Procesa preventas y productos en tara para crear un embarque",
        request=EmbarqueSerializer,
        responses={
            201: inline_serializer(
                name='EmbarqueCreateResponse',
                fields={
                    'success': serializers.BooleanField(),
                    'message': serializers.CharField(),
                    'embarque': EmbarqueSerializer(),
                    'preventas_procesadas': serializers.ListField(child=serializers.IntegerField()),
                    'productos_tara_procesados': serializers.ListField(
                        #child=ProductosTaraAbiertosSerializer()
                    ),
                }
            ),
            400: "Error en los datos proporcionados",
            500: "Error interno del servidor"
        },
        tags=['Embarque']
    )
    def post(self, request):
        """
        Crear un nuevo embarque procesando preventas y productos en tara
        """
        from apps.inventario.models import Almacen
        
        almacen_origen = request.data.get('almacen_origen', None)
        if almacen_origen:
            # Si viene un ID, convertirlo a instancia
            if isinstance(almacen_origen, int) or (isinstance(almacen_origen, str) and almacen_origen.isdigit()):
                almacen_origen = Almacen.objects.filter(id=int(almacen_origen)).first()
                if not almacen_origen:
                    return Response(
                        {'detail': 'El almacén de origen no existe.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        else:
            almacen_origen = request.user.almacen
            
        if not almacen_origen:
            return Response(
                {'detail': 'El almacén de origen es obligatorio para crear un embarque.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = EmbarqueSerializer(data=request.data, context={'request': request, 'almacen_origen': almacen_origen})
        
        if not serializer.is_valid():
            return Response(
                {'detail': 'Datos inválidos', 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
       
        try:
            with transaction.atomic():
                # Procesar el embarque
                embarque_data = serializer.save()
                
                return Response({
                            'success': True,
                            #'message': f'Embarque creado exitosamente para ruta {ruta.nombre}',
                            'embarque_id':  embarque_data.id,
                            'fase': embarque_data.fase,

                        }, status=status.HTTP_201_CREATED)    
        except ValidationError as e:
            return Response(
                {'detail': f'Error de validación: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'detail': f'Error interno: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )


#LISTAR LAS PREVENTAS A EMBARCAR
@extend_schema(
    summary="Listar preventas con productos pendientes por cargar",
    description="Obtiene las preventas que tienen productos sin cargar, con información detallada de cada producto y su unidad SAT",
    parameters=[
        OpenApiParameter(
            name='ruta_id',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='ID de la ruta para filtrar preventas (opcional)',
            required=False
        ),
        OpenApiParameter(
            name='fase',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Filtrar por fase de la venta (PRE VENTA, EN CURSO, etc.)',
            required=False
        ),
    ],
    responses={
        200: inline_serializer(
            name='PreventasConDetallesResponse',
            fields={
                'preventas': inline_serializer(
                    name='PreventaConDetalles',
                    fields={
                        'id': serializers.IntegerField(),
                        'codigo': serializers.CharField(),
                        'cliente': inline_serializer(
                            name='ClienteInfo',
                            fields={
                                'id': serializers.IntegerField(),
                                'nombre_completo': serializers.CharField(),
                            }
                        ),
                        'ruta': inline_serializer(
                            name='RutaInfo',
                            fields={
                                'id': serializers.IntegerField(),
                                'nombre': serializers.CharField(),
                                'codigo': serializers.CharField(),
                            }
                        ),
                        'fase': serializers.CharField(),
                        'total': serializers.DecimalField(max_digits=10, decimal_places=2),
                        'is_total_cargado': serializers.BooleanField(),
                        'productos': inline_serializer(
                            name='ProductoDetalle',
                            fields={
                                'id': serializers.IntegerField(),
                                'unidad': serializers.CharField(help_text="Nombre de la unidad SAT"),
                                'unidad_clave': serializers.CharField(help_text="Clave de la unidad SAT"),
                                'nombre': serializers.CharField(),
                                'codigo': serializers.CharField(),
                                'cantidad_total': serializers.IntegerField(),
                                'is_cargado': serializers.BooleanField(),
                            },
                            many=True
                        ),
                    },
                    many=True
                )
            }
        ),
        400: "Error en los parámetros"
    },
    tags=['Embarque']
)
@api_view(['GET'])
def listar_preventas_con_detalles_carga(request):
    """
    Lista todas las preventas con sus detalles de productos y estado de carga.
    Si solo_productos=true, devuelve solo los productos agrupados con cantidades sumadas.
    """
    try:
        from apps.inventario.models import LoteInventario
        
        # Obtener parámetros de filtro
        ruta_id = request.query_params.get('ruta_id')
        fase = request.query_params.get('fase', Venta.FASE_PRE_VENTA)
        solo_productos = request.query_params.get('solo_productos', '').lower() == 'true'
        user = request.user
        almacen = user.almacen
        print(f"almacen del usuario: {almacen}")
        
        if not almacen:
            return Response(
                {'detail': 'El usuario no tiene un almacén asignado.'},
                status=status.HTTP_400_BAD_REQUEST
            ) 
        
        # Construir filtros base
        filtros = {
            'status_model': BaseModel.STATUS_MODEL_ACTIVE,
            'fase': fase,
            'was_preventa': True,
            'is_total_cargado': False,
        }
        
        if not ruta_id:
            ruta = Rutas.objects.filter(asignado=user, status_model=BaseModel.STATUS_MODEL_ACTIVE).first()
            if ruta:
                filtros['ruta_id'] = ruta.id
            else:
                return Response(
                    {'detail': 'ruta_id es un parámetro requerido'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            try:
                filtros['ruta_id'] = int(ruta_id)
            except ValueError:
                return Response(
                    {'detail': 'ruta_id debe ser un número entero'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Query optimizada
        preventas = Venta.objects.filter(
            **filtros,
            detalles__is_cargado=False
        ).select_related(
            'cliente', 
            'ruta'
        ).prefetch_related(
            'detalles__producto__unidad_sat'
        ).distinct().order_by('-created_at')
        
        # Obtener todos los productos únicos de las preventas
        productos_ids = set()
        for preventa in preventas:
            for detalle in preventa.detalles.all():
                productos_ids.add(detalle.producto_id)
        
     
        # Si solo quieren productos agrupados
        if solo_productos:
            productos_agrupados = {}
            
            for preventa in preventas:
                detalles = preventa.detalles.filter(is_cargado=False)
                
                for detalle in detalles:
                    producto_id = detalle.producto.id
                    
                    if producto_id not in productos_agrupados:
                        productos_agrupados[producto_id] = {
                            'producto_id': producto_id,
                            'nombre': detalle.producto.nombre,
                            'precio_unitario': detalle.precio_unitario,
                            'codigo': detalle.producto.codigo,
                            'unidad': detalle.producto.unidad_sat.nombre if detalle.producto.unidad_sat else 'N/A',
                            'unidad_clave': detalle.producto.unidad_sat.clave if detalle.producto.unidad_sat else 'N/A',
                            'cantidad_total': 0,
                            #'lotes': lotes_por_producto.get(producto_id, []),
                        }
                    
                    productos_agrupados[producto_id]['cantidad_total'] += detalle.cantidad
            
            return Response({'productos': list(productos_agrupados.values())}, status=status.HTTP_200_OK)
        
        # Si quieren preventas con sus productos
        preventas_data = []

        for preventa in preventas:
            detalles = preventa.detalles.all()
            
            if not detalles:
                continue
            
            productos_data = []
            
            for detalle in detalles:
                producto_id = detalle.producto_id
                
                productos_data.append({
                    'producto_id': producto_id,
                    'nombre': detalle.producto.nombre,
                    'codigo': detalle.producto.codigo,
                    'unidad': detalle.producto.unidad_sat.nombre if detalle.producto.unidad_sat else 'N/A',
                    'unidad_clave': detalle.producto.unidad_sat.clave if detalle.producto.unidad_sat else 'N/A',
                    'cantidad': detalle.cantidad,
                    'cantidad_total': detalle.cantidad,
                    'precio_unitario': detalle.precio_unitario,
                    'cantidad_inventario': LoteInventario.objects.filter(
                        producto_id=producto_id,
                        almacen=almacen,
                        status_model=BaseModel.STATUS_MODEL_ACTIVE
                    ).aggregate(total_cantidad=Sum('cantidad'))['total_cantidad'] or 0.0,
                    'is_cargado': detalle.is_cargado,
                    #'lotes': lotes_por_producto.get(producto_id, []),
                })
            
            preventa_data = {
                'id': preventa.id,
                'is_total_cargado': preventa.is_total_cargado,
                'falta_inventario': preventa.falta_inventario,
                'codigo': preventa.codigo,
                'condicion_pago': preventa.condicion_pago,
                'cliente_id': preventa.cliente.id if preventa.cliente else None,
                'cliente_nombre': preventa.cliente.get_full_name if preventa.cliente else 'Sin cliente',
                'cliente': {
                    'id': preventa.cliente.id if preventa.cliente else None,
                    'nombre_completo': preventa.cliente.get_full_name if preventa.cliente else 'Sin cliente',
                },
                'ruta': {
                    'id': preventa.ruta.id if preventa.ruta else None,
                    'nombre': preventa.ruta.nombre if preventa.ruta else 'Sin ruta',
                    'codigo': preventa.ruta.codigo if preventa.ruta else 'Sin código',
                },
                'ruta_id': preventa.ruta.id if preventa.ruta else None,
                'ruta_nombre': preventa.ruta.nombre if preventa.ruta else 'Sin ruta',
                'ruta_codigo': preventa.ruta.codigo if preventa.ruta else 'Sin código',
                'productos': productos_data,
            }
            
            preventas_data.append(preventa_data)
        
        return Response({'preventas': preventas_data}, status=status.HTTP_200_OK)
        
    except Exception as e:
        print(f"❌ [API ERROR] Error al listar preventas con detalles: {str(e)}")
        import traceback
        print(f"❌ [API ERROR] Traceback: {traceback.format_exc()}")
        
        return Response(
            {'detail': f'Error al listar preventas con detalles: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )



"""
============================================================================================
                            VIEWS DE APIS DE EMBARQUE LISTAR Y RETRIEVE
============================================================================================
"""
from rest_framework.pagination import LimitOffsetPagination
from apps.inventario.models import EmbarqueReparto
from apps.erp.serializers.embarque.embarque_serializer import EmbarqueDetailSerializer


class EmbarqueRepartoListRetrieveAPIView(APIView):
    """
    Vista para listar y obtener detalle de embarques de reparto
    """
    pagination_class = LimitOffsetPagination
    
    @extend_schema(
        summary="Listar embarques de reparto",
        description="Obtiene una lista paginada de embarques de reparto con filtros opcionales",
        parameters=[
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Buscar por nombre de ruta o nombre del encargado',
                required=False
            ),
            OpenApiParameter(
                name='ruta_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Filtrar por ID de ruta',
                required=False
            ),
            OpenApiParameter(
                name='fase',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filtrar por fase (CARGA, REPARTO, TERMINADO, CANCELADO)',
                required=False
            ),
            OpenApiParameter(
                name='encargado_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Filtrar por ID del encargado',
                required=False
            ),
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Número de resultados por página',
                required=False
            ),
            OpenApiParameter(
                name='offset',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Desplazamiento para paginación',
                required=False
            ),
            OpenApiParameter(
                name='sin_paginacion',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='Si es true, devuelve todos los resultados sin paginar',
                required=False,
                default=False
            ),
        ],
        responses={
            200: EmbarqueMiniSerializer(many=True),
        },
        tags=['Embarque']
    )
    def get(self, request, pk=None):
        """
        Lista embarques o retorna el detalle de uno específico
        """
        if pk:
            return self.retrieve(request, pk)
        
        from django.db.models import Q
        
        # Filtros
        search = request.query_params.get('search', None)
        ruta_id = request.query_params.get('ruta_id', None)
        fase = request.query_params.get('fase', None)
        encargado_id = request.query_params.get('encargado_id', None)
        sin_paginacion = request.query_params.get('sin_paginacion', '').lower() == 'true'
        
        # Query base optimizada
        queryset = EmbarqueReparto.objects.select_related(
            'ruta',
            'encargado'
        ).exclude(
            status_model=BaseModel.STATUS_MODEL_DELETE
        ).order_by('-created_at')
        
        # Búsqueda por nombre de ruta o encargado
        if search:
            queryset = queryset.filter(
                Q(ruta__nombre__icontains=search) |
                Q(ruta__codigo__icontains=search) |
                Q(encargado__nombre__icontains=search) |
                Q(encargado__apellido_paterno__icontains=search) |
                Q(encargado__apellido_materno__icontains=search)
            )
        
        # Aplicar filtros
        if ruta_id:
            queryset = queryset.filter(ruta_id=ruta_id)
        else:
            # Filtrar por la ruta del usuario si no se proporciona ruta_id
            user = request.user
            ruta = Rutas.objects.filter(asignado=user, status_model=BaseModel.STATUS_MODEL_ACTIVE).first()
            if ruta:
                queryset = queryset.filter(ruta_id=ruta.id)
                
                
        if fase:
            queryset = queryset.filter(fase=fase)
        
        if encargado_id:
            queryset = queryset.filter(encargado_id=encargado_id)
        
        # Si se solicita sin paginación, devolver todos los resultados
        if sin_paginacion:
            serializer = EmbarqueMiniSerializer(queryset, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        # Paginación
        paginator = LimitOffsetPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = EmbarqueMiniSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = EmbarqueMiniSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @extend_schema(
        summary="Obtener detalle de embarque",
        description="Obtiene el detalle completo de un embarque con sus productos y lotes. Usar include_ventas=true para incluir las ventas con sus productos cargados.",
        parameters=[
            OpenApiParameter(
                name='include_ventas',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='Si es true, incluye las ventas del embarque con sus productos cargados',
                required=False,
                default=False
            )
        ],
        responses={
            200: EmbarqueDetailSerializer,
            404: "Embarque no encontrado"
        },
        tags=['Embarque']
    )
    def retrieve(self, request, pk):
        """
        Obtiene el detalle completo de un embarque
        """
        try:
            from django.db.models import Prefetch
            from apps.inventario.models import ProductoEmbarque
            
            # Obtener parámetro include_ventas
            include_ventas = request.query_params.get('include_ventas', '').lower() == 'true'
            
            # Query base con productos
            queryset = EmbarqueReparto.objects.select_related(
                'ruta',
                'encargado',
                'created_by'
            ).prefetch_related(
                Prefetch(
                    'productos',
                    queryset=ProductoEmbarque.objects.select_related(
                        'producto__unidad_sat',
                        'preventa'
                    ).prefetch_related('lotes__lote')
                )
            )
            
            # Solo agregar prefetch de ventas si se solicita
            if include_ventas:
                queryset = queryset.prefetch_related('ventas__cliente')
            
            embarque = queryset.get(pk=pk)
            
            if embarque.status_model == BaseModel.STATUS_MODEL_DELETE:
                return Response(
                    {'detail': 'Embarque no encontrado.'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            serializer = EmbarqueDetailSerializer(embarque, context={'include_ventas': include_ventas})
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except EmbarqueReparto.DoesNotExist:
            return Response(
                {'detail': 'Embarque no encontrado.'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'detail': str(e), 'error_code': 'ERROR_RETRIEVE_EMBARQUE'},
                status=status.HTTP_400_BAD_REQUEST
            )


@extend_schema(
    summary="Iniciar reparto de embarque",
    description="Actualiza la fase del embarque a REPARTO y registra la fecha de salida",
    request=inline_serializer(
        name='IniciarRepartoRequest',
        fields={
            'embarque_id': serializers.IntegerField(help_text="ID del embarque a iniciar"),
            'encargado_id': serializers.IntegerField(required=False, help_text="ID del encargado del reparto (opcional)"),
            'nota': serializers.CharField(required=False, help_text="Nota adicional (opcional)"),
        }
    ),
    responses={
        200: inline_serializer(
            name='IniciarRepartoResponse',
            fields={
                'success': serializers.BooleanField(),
                'message': serializers.CharField(),
                'embarque_id': serializers.IntegerField(),
                'fase': serializers.CharField(),
                'fecha_salida': serializers.DateTimeField(),
            }
        ),
        400: "Error en los datos proporcionados",
        404: "Embarque no encontrado"
    },
    tags=['Embarque']
)
@api_view(['POST'])
def iniciar_reparto(request):
    """
    Inicia el reparto de un embarque actualizando su fase a REPARTO y registrando la fecha de salida
    """
    from django.utils import timezone
    
    embarque_id = request.data.get('embarque_id')
    nota = request.data.get('nota', None)
    
    if not embarque_id:
        return Response(
            {'detail': 'embarque_id es requerido'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        embarque = EmbarqueReparto.objects.select_related('ruta').get(
            pk=embarque_id,
            status_model=BaseModel.STATUS_MODEL_ACTIVE
        )
        
        # Validar que el embarque esté en fase CARGA
        if embarque.fase != EmbarqueReparto.FASE_CARGA:
            return Response(
                {'detail': f'El embarque debe estar en fase CARGA para iniciar reparto. Fase actual: {embarque.fase}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Actualizar fase y fecha de salida
        embarque.fase = EmbarqueReparto.FASE_REPARTO
        embarque.fecha_salida = timezone.now()
        
        # Actualizar encargado si se proporciona
        #if encargado_id:
        #    try:
        #        encargado = Usuario.objects.get(pk=encargado_id)
        #        embarque.encargado = encargado
        #    except Usuario.DoesNotExist:
        #        return Response(
        #            {'detail': 'Encargado no encontrado'},
        #            status=status.HTTP_404_NOT_FOUND
        #        )
        
        # Agregar nota si se proporciona
        if nota:
            embarque.nota = f"{embarque.nota or ''}\n[INICIO REPARTO]: {nota}".strip()
        else:
            embarque.nota = f"{embarque.nota or ''}\n[INICIO REPARTO] POR {request.user.full_name()}".strip()
        embarque.save(update_fields=['fase', 'fecha_salida', 'encargado', 'nota', 'updated_at'])
        
        # Obtener nombre del encargado
        encargado_nombre = None
        if embarque.encargado:
            encargado_nombre = embarque.encargado.full_name() if callable(embarque.encargado.full_name) else embarque.encargado.full_name
        
        return Response({
            'success': True,
            'message': f'Reparto iniciado exitosamente para embarque {embarque_id}',
            'embarque_id': embarque.id,
            'fase': embarque.fase,
            'fecha_salida': embarque.fecha_salida.strftime('%Y-%m-%d %H:%M:%S'),
            'ruta_nombre': embarque.ruta.nombre if embarque.ruta else None,
            'encargado_nombre': encargado_nombre,
        }, status=status.HTTP_200_OK)
        
    except EmbarqueReparto.DoesNotExist:
        return Response(
            {'detail': 'Embarque no encontrado'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'detail': str(e), 'error_code': 'ERROR_INICIAR_REPARTO'},
            status=status.HTTP_400_BAD_REQUEST
        )


@extend_schema(
    summary="Finalizar reparto de embarque",
    description="Actualiza la fase del embarque a TERMINADO, finalizando el reparto",
    request=inline_serializer(
        name='FinalizarRepartoRequest',
        fields={
            'reparto_id': serializers.IntegerField(help_text="ID del embarque/reparto a finalizar"),
        }
    ),
    responses={
        200: inline_serializer(
            name='FinalizarRepartoResponse',
            fields={
                'success': serializers.BooleanField(),
                'message': serializers.CharField(),
                'reparto_id': serializers.IntegerField(),
                'fase': serializers.CharField(),
            }
        ),
        400: "Error en los datos proporcionados",
        404: "Reparto no encontrado"
    },
    tags=['Embarque']
)
@api_view(['POST'])
def finalizar_reparto(request):
    reparto_id = request.data.get('reparto_id')
    model_reparto = EmbarqueReparto.objects.filter(id=reparto_id).first()
    if not model_reparto:
        return Response(
            {'detail': 'Reparto no encontrado'},
            status=status.HTTP_404_NOT_FOUND
        )
        
    if model_reparto.fase != EmbarqueReparto.FASE_REPARTO:
        return Response(
            {'detail': f'El reparto debe estar en fase REPARTO para finalizar. Fase actual: {model_reparto.fase}'},
            status=status.HTTP_400_BAD_REQUEST
        )
        
    model_reparto.fase = EmbarqueReparto.FASE_TERMINADO
    
    
    
    model_reparto.save()
    return Response(
        {
            'success': True,
            'message': f'Reparto {reparto_id} finalizado exitosamente',
            'reparto_id': model_reparto.id,
            'fase': model_reparto.fase,
        },
        status=status.HTTP_200_OK
    )


"""
============================================================================================
                            VIEWS PARA CHECKIN DE PRODUCTOS EN EMBARQUE
============================================================================================
"""

@extend_schema(
    summary="Checkin de productos en embarque",
    description="Realiza el checkin de productos de ventas en un embarque de ruta. Permite marcar los productos que se están cargando en el vehículo.",
    request=VentasEmbarqueSubidaRutaSerializer,
    responses={
        200: inline_serializer(
            name='CheckinProductoResponse',
            fields={
                'success': serializers.BooleanField(),
                'message': serializers.CharField(),
                'embarque_id': serializers.IntegerField(),
                'ventas_procesadas': serializers.IntegerField(),
                'productos_checkin': serializers.IntegerField(),
            }
        ),
        400: "Error en los datos proporcionados",
        404: "Embarque no encontrado"
    },
    tags=['Embarque']
)
@api_view(['POST'])
def checkin_producto_embarque(request):
    """
    Realiza el checkin de productos de ventas en un embarque.
    Marca los productos como cargados en el vehículo de reparto.
    """
    serializer = VentasEmbarqueSubidaRutaSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {'detail': 'Datos inválidos', 'errors': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            embarque = serializer.validated_data.get('embarque')
            ventas_data = serializer.validated_data.get('ventas', [])
            productos_tara = serializer.validated_data.get('productos_tara', [])
            
            # Validar que el embarque esté en fase CARGA o REPARTO
            if embarque.fase not in [EmbarqueReparto.FASE_CARGA,]:
                return Response(
                    {'detail': f'El embarque debe estar en fase CARGA . Fase actual: {embarque.fase}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            
            
            productos_checkin_count = 0
            ventas_procesadas = 0
            
            for venta_data in ventas_data:
                venta = venta_data.get('venta')
                productos = venta_data.get('productos', [])
                
                for producto_data in productos:
                    producto = producto_data.get('producto')
                    check = producto_data.get('check', False)
                    
                    if check:
                        # Actualizar el detalle de venta correspondiente
                        from apps.erp.models import VentaDetalle
                        detalle = VentaDetalle.objects.filter(
                            venta=venta,
                            producto=producto
                        ).first()
                        
                        if detalle:
                            # Marcar como cargado (cantidad_cargada = cantidad)
                            detalle.cantidad_cargada = detalle.cantidad_logistica
                            detalle.is_cargado = True
                            detalle.save(update_fields=['cantidad_cargada', 'is_cargado'])
                            productos_checkin_count += 1
                
                ventas_procesadas += 1
                
                ## Verificar si todos los detalles de la venta están cargados
                #from apps.erp.models import VentaDetalle
                #detalles_sin_cargar = VentaDetalle.objects.filter(
                #    venta=venta,
                #    is_cargado=False
                #).count()
                #
                #if detalles_sin_cargar == 0:
                #    venta.is_total_cargado = True
                #    venta.save(update_fields=['is_total_cargado'])
            
            # Procesar productos de tara si existen
            tara_checkin_count = 0
            for producto_tara in productos_tara:
                producto_carga = producto_tara.get('producto_carga')
                check = producto_tara.get('check', False)
                
                if check:
                    producto_carga.is_cargado = True
                    producto_carga.save(update_fields=['is_cargado'])
                    
                    # Aquí se puede agregar lógica adicional para tara
                    tara_checkin_count += 1
                    
            #embarque.fase = EmbarqueReparto.FASE_REPARTO
            #embarque.save()
            from django.utils import timezone
            
            embarque.fase = EmbarqueReparto.FASE_REPARTO
            embarque.fecha_salida = timezone.now()
            embarque.save()
            
            return Response({
                'success': True,
                'message': f'Checkin realizado exitosamente',
                'embarque_id': embarque.id,
                'ventas_procesadas': ventas_procesadas,
                'productos_checkin': productos_checkin_count,
                'productos_tara_checkin': tara_checkin_count,
            }, status=status.HTTP_200_OK)
            
    except Exception as e:
        return Response(
            {'detail': f'Error al realizar checkin: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )


"""
============================================================================================
                            VIEWS PARA MOVIMIENTOS DE CAJA DEL EMBARQUE
============================================================================================
"""

@extend_schema(
    summary="Obtener movimientos de caja del embarque",
    description="Obtiene los movimientos de caja (transacciones) asociados a la apertura de caja de un embarque/reparto.",
    parameters=[
        OpenApiParameter(
            name='embarque_id',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='ID del embarque/reparto',
            required=True
        ),
    ],
    responses={
        200: "EmbarqueCajaMovimientosSerializer con ventas",
        400: "Error: embarque_id requerido",
        404: "Embarque no encontrado o no tiene caja asignada"
    },
    tags=['Embarque']
)
@api_view(['GET'])
def obtener_caja_movimientos_embarque(request):
    """
    Endpoint para obtener los movimientos de caja asociados a un embarque,
    incluyendo las ventas realizadas durante el periodo del embarque.
    """
    from django.utils import timezone
    from apps.erp.serializers.embarque.embarque_serializer import (
        EmbarqueCajaMovimientosSerializer,
        VentaEmbarqueCajaSerializer
    )
    from apps.erp.models import CajaApertura, CajaTransaccion
    
    embarque_id = request.query_params.get('embarque_id')
    
    if not embarque_id:
        return Response(
            {'detail': 'El parámetro embarque_id es requerido'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Buscar el embarque
    embarque = EmbarqueReparto.objects.select_related(
        'apertura_caja',
        'apertura_caja__usuario'
    ).filter(id=embarque_id).first()
    
    if not embarque:
        return Response(
            {'detail': 'Embarque no encontrado'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Verificar que el embarque tenga una caja asignada
    if not embarque.apertura_caja:
        return Response(
            {'detail': 'El embarque no tiene una caja asignada'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Obtener la apertura de caja con sus transacciones
    apertura_caja = CajaApertura.objects.select_related(
        'caja',
        'usuario'
    ).prefetch_related(
        'transacciones',
        'transacciones__metodo_pago'
    ).get(id=embarque.apertura_caja.id)
    
    serializer = EmbarqueCajaMovimientosSerializer(apertura_caja)
    response_data = serializer.data
    
    # Obtener las ventas realizadas durante el periodo del embarque
    # Filtrar por el usuario de la apertura de caja y el rango de fechas
    usuario_caja = embarque.apertura_caja.usuario
    fecha_inicio = embarque.created_at
    fecha_fin = embarque.fecha_finalizada if embarque.fecha_finalizada else timezone.now()
    
    ventas_queryset = Venta.objects.select_related(
        'cliente',
        'created_by'
    ).filter(
        created_by=usuario_caja,
        created_at__gte=fecha_inicio,
        created_at__lte=fecha_fin,
        status_model=Venta.STATUS_MODEL_ACTIVE
    ).exclude(
        fase=Venta.FASE_CANCELADA
    ).order_by('-created_at')
    
    ventas_serializer = VentaEmbarqueCajaSerializer(ventas_queryset, many=True)
    
    # Calcular totales de ventas
    total_ventas = sum(float(v.total) for v in ventas_queryset)
    total_cobrado_ventas = sum(float(v.total_pagado) for v in ventas_queryset)
    
    response_data['ventas'] = ventas_serializer.data
    response_data['total_ventas'] = round(total_ventas, 2)
    response_data['total_cobrado_ventas'] = round(total_cobrado_ventas, 2)
    response_data['cantidad_ventas'] = ventas_queryset.count()
    
    return Response(response_data, status=status.HTTP_200_OK)