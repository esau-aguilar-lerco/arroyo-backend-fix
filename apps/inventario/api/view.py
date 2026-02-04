from django.db import models,transaction
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.generics import ListAPIView

from drf_spectacular.utils import extend_schema, OpenApiParameter,OpenApiExample,OpenApiResponse
from rest_framework import mixins,viewsets,status, filters
from rest_framework.response import Response
from apps.inventario.services.alertasvencimiento import evaluar_vencimiento


#MODELS
from apps.base.models import BaseModel
from apps.erp.models import Almacen, Compra, Producto
from apps.inventario.models import Piso, Zona, Rack,  MovimientoInventario, LoteInventario

#SERIALIZERS
from ..serializers.distribucionAlamcenSerializer import (PisoSerializer, RackSerializer, ZonaSerializer, PisoMiniSerializer)
from ..serializers.movimientoSerializer import (MovimientoSalidaSerializer,MovimientoSalidaDetalleSerializer,
                                                MovimientoEntradaAbastecimientoSerializer,
                                                AbastecimientoSuccessResponseSerializer, 
                                                    AbastecimientoErrorResponseSerializer)
from ..serializers.inventarioSerializer import (InventarioPorAlmacenSerializer,
                                                DetalleInventarioPorProductoSerializer,
                                                DetalleInventarioRackSerializer)
from ..services.entradas import AbastecimientoService
from apps.erp.serializers.compras_serializer import CompraMiniListSerializer
from apps.inventario.serializers.movimientoPrincipal import (MovimimientosMiniSerializer, 
                                                              MovimientoPrincipalSerializer,
                                                              MovimientoEntradaSerializer,
                                                              MovimientoInventarioListSerializer)



#PERMISOS CLASES 
from apps.inventario.auth.permisos import DetalleCedisPermission


"""
===================================================================
                VIEWS SET DE PISOS - OPTIMIZADO
===================================================================
"""
class PisoViewSet(viewsets.ModelViewSet):   
    serializer_class = PisoMiniSerializer
    #permission_classes = [DetalleCedisPermission]
    pagination_class = None
    
    
    def get_queryset(self):
        """
        Optimización: select_related y prefetch_related para evitar N+1 queries
        """
        return Piso.objects.select_related(
            'almacen',
            'almacen__empresa'
        ).prefetch_related(
            'zonas',
            'zonas__racks'
        ).filter(
            status_model=BaseModel.STATUS_MODEL_ACTIVE
        ).order_by('nombre')

    @extend_schema(
        summary="Listar pisos",
        description="Obtiene una lista de pisos activos, opcionalmente filtrados por almacen cedis",
        parameters=[
            OpenApiParameter(
                name="almacen_id",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="ID del almacen para filtrar los pisos"
            ),
            #OpenApiParameter(
            #    name="incluir_detalle",
            #    type=bool,
            #    location=OpenApiParameter.QUERY,
            #    required=False,
            #    description="Incluir zonas y racks (default: false)"
            #)
        ],
        responses={200: PisoMiniSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        
        # Filtro por almacén
        almacen_id = request.query_params.get('almacen_id')
        if almacen_id:
            queryset = queryset.filter(almacen_id=almacen_id)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        # Usa get_queryset() que ya tiene las optimizaciones
        try:
            instance = self.get_queryset().get(pk=kwargs['pk'])
        except Piso.DoesNotExist:
            return Response(
                {"detail": "No encontrado."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if instance.status_model == BaseModel.STATUS_MODEL_DELETE:
            return Response(
                {"detail": "No encontrado."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        try:
            instance = self.get_queryset().get(pk=kwargs['pk'])
        except Piso.DoesNotExist:
            return Response(
                {"detail": "No encontrado."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if instance.status_model == BaseModel.STATUS_MODEL_DELETE:
            return Response(
                {"detail": "No encontrado."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_queryset().get(pk=kwargs['pk'])
        except Piso.DoesNotExist:
            return Response(
                {"detail": "No encontrado."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if instance.status_model == BaseModel.STATUS_MODEL_DELETE:
            return Response(
                {"detail": "No encontrado."},
                status=status.HTTP_404_NOT_FOUND
            )

        instance.status_model = BaseModel.STATUS_MODEL_DELETE
        instance.save(update_fields=['status_model'])
        return Response({"detail": "El piso ha sido eliminado."},status=status.HTTP_200_OK)

# ===============================
#   API: Buscar pisos por almacen (documentada)
# ===============================
@extend_schema(
    summary="Detalle interno del CEDIS",
    description="Devuelve una lista de pisos activos filtrados por el id de almacén.",
    parameters=[
        OpenApiParameter(
            name="almacen_id",
            type=int,
            location=OpenApiParameter.QUERY,
            required=True,
            description="ID del almacén"
        )
    ],
    responses={200: PisoSerializer(many=True)}
)
class PisoPorAlmacenAPIView(APIView):
    #permission_classes = [DetalleCedisPermission]
    
    def get(self, request, *args, **kwargs):
        almacen_id = request.query_params.get('almacen_id')
        if not almacen_id:
            return Response({'detail': 'Debe proporcionar almacen_id como parámetro.'}, status=status.HTTP_400_BAD_REQUEST)

        almacen = Almacen.objects.filter(
            id=almacen_id,
            status_model=BaseModel.STATUS_MODEL_ACTIVE,
            is_cedis=True
        ).first()
        if not almacen:
            return Response({'detail': 'Almacén no encontrado, inactivo o no es un CEDIS.'}, status=status.HTTP_404_NOT_FOUND)

        pisos = Piso.objects.filter(
            almacen_id=almacen_id,
            status_model=BaseModel.STATUS_MODEL_ACTIVE
        )
        serializer = PisoSerializer(pisos, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

"""
===================================================================
                VIEWS SET DE ZONAS
===================================================================
"""

class ZonaViewSet(viewsets.ModelViewSet):
    queryset = Zona.objects.filter(status_model=BaseModel.STATUS_MODEL_ACTIVE)
    serializer_class = ZonaSerializer
    pagination_class = None
    #permission_classes = [DetalleCedisPermission]
    

    #filter_backends = [filters.SearchFilter]
    @extend_schema(
        summary="Listar zonas",
        description="Obtiene una lista de zonas activas, opcionalmente filtradas por piso",
        parameters=[
            OpenApiParameter(
                name="piso_id",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="ID del piso para filtrar las zonas"
            )
        ],
        responses={200: ZonaSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(
            self.get_queryset().exclude(status_model=BaseModel.STATUS_MODEL_DELETE)
        )
        
        # Filtro por piso_id
        piso_id = request.query_params.get('piso_id')
        if piso_id:
            queryset = queryset.filter(piso_id=piso_id)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if self.is_respuesta_404():
            return self.respuesta_404()

        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        if self.is_respuesta_404():
            return self.respuesta_404()

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if self.is_respuesta_404():
            return self.respuesta_404()
        
        if instance.tiene_racks_con_lotes():
            return Response(
                {"detail": "No se puede eliminar la zona porque tiene racks asignados con lotes activos."},
                status=status.HTTP_400_BAD_REQUEST
            )

        instance.status_model = BaseModel.STATUS_MODEL_DELETE
        instance.save(update_fields=['status_model'])
        return Response({"detail": "La zona ha sido eliminada."},status=status.HTTP_200_OK)

    def is_respuesta_404(self):
        instance = self.get_object()
        return instance.status_model == BaseModel.STATUS_MODEL_DELETE

    def respuesta_404(self):
        return Response(
            {"detail": "No encontrado."},
            status=status.HTTP_404_NOT_FOUND
        )

"""
===================================================================
                VIEWS SET DE RACKS
===================================================================
"""
class RackViewSet(viewsets.ModelViewSet):
    queryset = Rack.objects.filter(status_model=BaseModel.STATUS_MODEL_ACTIVE)
    serializer_class = RackSerializer
    pagination_class = None
    #permission_classes = [DetalleCedisPermission]
    
    
    @extend_schema(
        summary="Listar racks",
        description="Obtiene una lista de racks activos, opcionalmente filtrados por piso",
        parameters=[
            OpenApiParameter(
                name="zona_id",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="ID de la zona para filtrar los racks"
            )
        ],
        responses={200: RackSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(
            self.get_queryset().exclude(status_model=BaseModel.STATUS_MODEL_DELETE)
        )
        zona_id = request.query_params.get('zona_id')
        if zona_id is not None:
            queryset = queryset.filter(zona_id=zona_id)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if self.is_respuesta_404():
            return self.respuesta_404()

        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        if self.is_respuesta_404():
            return self.respuesta_404()

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if self.is_respuesta_404():
            return self.respuesta_404()
        
        if instance.tiene_lotes_asignados():
            return Response(
                {"detail": "No se puede eliminar el rack porque tiene lotes de inventario asignados."},
                status=status.HTTP_400_BAD_REQUEST
            )
        instance.status_model = BaseModel.STATUS_MODEL_DELETE
        instance.save(update_fields=['status_model'])
        return Response({"detail": "El rack ha sido eliminado."},status=status.HTTP_200_OK)

    def is_respuesta_404(self):
        instance = self.get_object()
        return instance.status_model == BaseModel.STATUS_MODEL_DELETE

    def respuesta_404(self):
        return Response(
            {"detail": "No encontrado."},
            status=status.HTTP_404_NOT_FOUND
        )



"""
===================================================================
                VIEWS PARA MOVIMIENTOS DE INVENTARIO
===================================================================
"""


#class MovimientoSalidaViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet): y reornar lo del creste data
class MovimientoSalidaViewSet(mixins.CreateModelMixin, 
                             mixins.RetrieveModelMixin, 
                             mixins.ListModelMixin, 
                             viewsets.GenericViewSet):
    """
    Permite la creación de movimientos de salida de inventario y puede ser extendida para otros tipos de movimientos.
    """
    queryset = MovimientoInventario.objects.all()
    serializer_class = MovimientoSalidaSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['status_model', 'referencia', 'movimiento']

    def get_serializer_class(self):
        """
        Usar diferentes serializers para diferentes acciones
        """
        if self.action == 'create':
            return MovimientoSalidaSerializer
        if self.action in ['list']:
            return MovimimientosMiniSerializer
        if self.action in ['retrieve']:
            return MovimientoPrincipalSerializer
        
        return MovimientoSalidaDetalleSerializer

    @extend_schema(
        request=MovimientoSalidaSerializer,
        responses={201: MovimientoSalidaDetalleSerializer},
        summary="Crear movimiento de salida",
        description="Permite crear movimientos de salida (merma o traspaso)"
    )
    def create(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'user': request.user})
        if serializer.is_valid():
            resultado = serializer.save()
            return Response(resultado, status=status.HTTP_201_CREATED)
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    def retrieve(self, request, pk=None):
        """
        Permite obtener los detalles de un movimiento de salida específico
        """
        try:
            movimiento = MovimientoInventario.objects.get(pk=pk)
        except MovimientoInventario.DoesNotExist:
            return Response({"detail": "No encontrado."}, status=status.HTTP_404_NOT_FOUND)
        serializer = MovimientoPrincipalSerializer(movimiento)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def list(self, request):
        """
        Permite listar los movimientos de salida de inventario
        """
        almacen = request.user.almacen
        if not almacen:
            almacen = Almacen.objects.filter(encargado=request.user).first()
        
        todas = request.query_params.get('todas', 'false').lower() == 'true'
        
        
        tipo = request.query_params.get('tipo',None)
        
            
        
        queryset = self.filter_queryset(
            self.get_queryset()
            .exclude(status_model=BaseModel.STATUS_MODEL_DELETE)
            .filter(
            models.Q(almacen=almacen) | models.Q(almacen_destino=almacen)
            )
            
            .order_by('-created_at')
        )
        
        if tipo is not None:
            queryset = queryset.filter(tipo=tipo)
            
            
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = MovimimientosMiniSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = MovimimientosMiniSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


"""
===================================================================
            PARA BUSCAR POR MOVIMIENTOS POR TIPO, ALMACEN Y FECHAS
=======================================================================
"""
class MovimientoTraspasoAPIView(APIView):
   
    """
    Permite buscar movimientos de inventario por tipo, almacén y fechas con paginación.
    También permite obtener el detalle completo de un movimiento específico.
    """
    
    @extend_schema(
        summary="Listar movimientos de traspaso",
        description="""
        Obtiene una lista paginada de movimientos de traspaso filtrados por tipo, fase y fechas.
        
        **Filtros disponibles:**
        - `tipo`: TIPO_ENTRADA o TIPO_SALIDA
        - `fase`: FASE_PROCESO o FASE_TERMINADA
        - `fecha_inicio` y `fecha_fin`: Rango de fechas
        
        **Nota:** Automáticamente filtra por el almacén del usuario autenticado.
        """,
        parameters=[
            OpenApiParameter(
                name="tipo",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Tipo de movimiento (TIPO_ENTRADA o TIPO_SALIDA)",
                enum=[MovimientoInventario.TIPO_ENTRADA, MovimientoInventario.TIPO_SALIDA]
            ),
            OpenApiParameter(
                name="fase",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Fase del movimiento (FASE_PROCESO o FASE_TERMINADA)",
                enum=[MovimientoInventario.FASE_PROCESO, MovimientoInventario.FASE_TERMINADA]
            ),
            OpenApiParameter(
                name="fecha_inicio",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Fecha de inicio (formato: YYYY-MM-DD)"
            ),
            OpenApiParameter(
                name="fecha_fin",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Fecha de fin (formato: YYYY-MM-DD)"
            ),
            OpenApiParameter(
                name="limit",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Número de resultados por página"
            ),
            OpenApiParameter(
                name="offset",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Desplazamiento para paginación"
            ),
        ],
        responses={
            200: MovimimientosMiniSerializer(many=True),
            400: OpenApiResponse(description="Almacén no encontrado o parámetros inválidos")
        },
        tags=['Movimientos de Inventario']
    )
    def get(self, request, pk=None):
        """
        Lista movimientos o retorna el detalle de uno específico
        """
        # Si se proporciona pk, retornar detalle
        if pk:
            return self.retrieve(request, pk)
        
        from rest_framework.pagination import LimitOffsetPagination
        
        tipo = request.query_params.get('tipo', None)
        fecha_inicio = request.query_params.get('fecha_inicio', None)
        fecha_fin = request.query_params.get('fecha_fin', None)
        
        fase = request.query_params.get('fase', None)
        
        almacen = request.user.almacen
        #if not almacen:
        #    almacen = Almacen.objects.filter(encargado=request.user).first()
        #if not almacen:
        #    return Response(
        #        {'detail': 'ALMACEN NO ENCONTRADO'},
        #        status=status.HTTP_400_BAD_REQUEST
        #    )

        queryset = MovimientoInventario.objects.filter(
            models.Q(almacen=almacen) | models.Q(almacen_destino=almacen)
        ).exclude(
            status_model=BaseModel.STATUS_MODEL_DELETE
        ).order_by('-created_at')
        
        if fase:
            queryset = queryset.filter(fase=fase)

        if tipo:
            queryset = queryset.filter(tipo=tipo)
            
            if tipo == MovimientoInventario.TIPO_ENTRADA:
                queryset = queryset.filter(almacen_destino=almacen)
            elif tipo == MovimientoInventario.TIPO_SALIDA:
                queryset = queryset.filter(almacen=almacen)
       
        if fecha_inicio and fecha_fin:
            queryset = queryset.filter(created_at__range=[fecha_inicio, fecha_fin])
        
        queryset = queryset.filter(movimiento__in=[MovimientoInventario.ENTRADA_TRASPASO,
                                                   MovimientoInventario.SALIDA_TRASPASO,])
        
        # Aplicar paginación
        paginator = LimitOffsetPagination()
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        
        serializer = MovimimientosMiniSerializer(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data)
    
    @extend_schema(
        summary="Obtener detalle de movimiento de traspaso",
        description="""
        Obtiene el detalle completo de un movimiento de traspaso específico.
        
        Incluye:
        - Información del movimiento
        - Almacenes origen y destino
        - Lista completa de productos con sus lotes
        - Cantidades por producto y lote
        """,
        responses={
            200: MovimientoPrincipalSerializer,
            404: OpenApiResponse(description="Movimiento no encontrado")
        },
        tags=['Movimientos de Inventario']
    )
    def retrieve(self, request, pk):
        """
        Obtiene el detalle completo de un movimiento
        """
        try:
            movimiento =MovimientoInventario.objects.all(
            
        ).select_related(
            'almacen',
            'almacen_destino'
        ).prefetch_related(
            'productosMovimiento__producto__unidad_sat',
            'productosMovimiento__lote'
        ).order_by('-created_at').get(pk=pk)
        except MovimientoInventario.DoesNotExist:
            return Response(
                {
                    'success': False,
                    'message': 'Movimiento no encontrado'
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = MovimientoPrincipalSerializer(movimiento)
        return Response(
            {
                'success': True,
                'data': serializer.data
            },
            status=status.HTTP_200_OK
        )





"""
================================================================================
                            DETALLES DEL INVENTARIO POR ALMACEN
================================================================================
"""


@extend_schema(
    summary="Balance de inventario por almacén",
    description="Obtiene el inventario consolidado de un almacén específico",
    parameters=[
        OpenApiParameter(
            name="almacen_id",
            type=int,
            location=OpenApiParameter.QUERY,
            required=False,
            description="ID del almacén para consultar inventario por defecto toma el asignado al usuario"
        ),
        OpenApiParameter(
            name="producto_id",
            type=int,
            location=OpenApiParameter.QUERY,
            required=False,
            description="ID del producto para filtrar (opcional)"
        ),
        OpenApiParameter(
            name="search",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Buscar productos por nombre (mínimo 3 caracteres)"
        ),
        OpenApiParameter(
            name="incluir_lotes",
            type=bool,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Incluir detalles de lotes individuales"
        )
    ],
    responses={200: InventarioPorAlmacenSerializer}
)
class InventarioAlmacenAPIView(APIView):
    def get(self, request, *args, **kwargs):
        almacen_id = request.query_params.get('almacen_id', None)
        producto_id = request.query_params.get('producto_id')
        search = request.query_params.get('search', '').strip()
        incluir_lotes = request.query_params.get('incluir_lotes', 'false').lower() == 'true'

        # Validación de parámetros
        if search and len(search) < 3:
            return Response({}, status=status.HTTP_204_NO_CONTENT)

        # Obtener almacén si no se proporciona
        if not almacen_id:
            almacen = request.user.almacen
            if not almacen:
                almacen = Almacen.objects.filter(encargado=request.user).first()
                if not almacen:
                    return Response(
                        {'detail': 'El parámetro almacen_id es requerido'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            almacen_id = almacen.id
        else:
            almacen = Almacen.objects.filter(id=almacen_id).first()
       
        # Query base optimizada
        lotes_query = (
            LoteInventario.objects
            .filter(
                almacen_id=almacen_id,
                status_model=BaseModel.STATUS_MODEL_ACTIVE,
                cantidad__gt=0
            )
            .select_related('producto', 'producto__unidad_sat')
        )

        # Filtrar por producto o búsqueda
        if producto_id:
            lotes_query = lotes_query.filter(producto_id=producto_id)
        elif search:
            lotes_query = lotes_query.filter(producto__nombre__icontains=search)

        # Agrupar por producto
        inventario_agrupado = (
            lotes_query
            .values(
                'producto_id',
                'producto__nombre',
                'producto__unidad_sat__nombre',
                'producto__unidad_sat__clave',
                "producto__codigo",
            )
            .annotate(
                cantidad_total=models.Sum('cantidad'),
                valor_total=models.Sum(models.F('cantidad') * models.F('costo_unitario')),
                numero_lotes=models.Count('id'),
                ultima_actualizacion=models.Max('updated_at'),
                proximo_vencimiento=models.Min('fecha_vencimiento')
            )
            .order_by('proximo_vencimiento', '-numero_lotes')
        )

        # ✅ TOTALES GENERALES
        resumen_totales = lotes_query.aggregate(
            valor_total_inventario=models.Sum(models.F('cantidad') * models.F('costo_unitario')),
            total_lotes_real=models.Count('id')
        )

        # Convertir a lista
        productos_list = list(inventario_agrupado)
        
        # ✅ PREPARAR LOTES SI SE SOLICITAN
        lotes_por_producto = {}
        if incluir_lotes and productos_list:
            productos_ids = [p['producto_id'] for p in productos_list]
            lotes_detallados = (
                lotes_query
                .filter(producto_id__in=productos_ids)
                .prefetch_related('ubicacion')
                .order_by('fecha_vencimiento')
            )
            for lote in lotes_detallados:
                lotes_por_producto.setdefault(lote.producto_id, []).append(lote)

        # ✅ CONSTRUIR RESPUESTA CON TODOS LOS PRODUCTOS
        productos_data = []
        for item in productos_list:
            productos_data.append({
                'producto_id': item['producto_id'],
                'codigo': item['producto__codigo'],
                'producto_nombre': item['producto__nombre'],
                'cantidad_total': item['cantidad_total'],
                'valor_total': item['valor_total'],
                'numero_lotes': item['numero_lotes'],
                'unidad_medida': item['producto__unidad_sat__nombre'],
                'unidad_clave': item['producto__unidad_sat__clave'],
                'ultima_actualizacion': item['ultima_actualizacion'],
                'proximo_vencimiento': item['proximo_vencimiento'],
                'lotes_relacionados': lotes_por_producto.get(item['producto_id'], []) if incluir_lotes else []
            })

        datos_inventario = {
            'almacen_id': almacen.id,
            'almacen_nombre': almacen.nombre,
            'almacen_tipo': almacen.get_tipo_display(),
            'fecha_consulta': timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M:%S'),
            'total_productos': len(productos_list),
            'total_lotes': resumen_totales['total_lotes_real'] or 0,
            'productos': productos_data
        }

        serializer = InventarioPorAlmacenSerializer(datos_inventario)
        
        # ✅ RETORNAR SIN PAGINACIÓN
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    


@extend_schema(
    summary="Consulta de inventario por almacén (paginado)",
    description="Obtiene el inventario consolidado de un almacén específico con paginación",
    parameters=[
        OpenApiParameter(
            name="almacen_id",
            type=int,
            location=OpenApiParameter.QUERY,
            required=False,
            description="ID del almacén para consultar inventario (por defecto toma el asignado al usuario)"
        ),
        OpenApiParameter(
            name="producto_id",
            type=int,
            location=OpenApiParameter.QUERY,
            required=False,
            description="ID del producto para filtrar (opcional)"
        ),
        OpenApiParameter(
            name="search",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Buscar productos por nombre (mínimo 3 caracteres)"
        ),
        OpenApiParameter(
            name="incluir_lotes",
            type=bool,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Incluir detalles de lotes individuales"
        ),
        OpenApiParameter(
            name="limit",
            type=int,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Número de productos por página (default: 10)"
        ),
        OpenApiParameter(
            name="offset",
            type=int,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Desplazamiento para paginación"
        ),
    ],
    responses={200: InventarioPorAlmacenSerializer}
)
class InventarioAlmacenConsultaAPIView(APIView):
    """
    Vista para consultar inventario por almacén CON PAGINACIÓN
    """
    def get(self, request, *args, **kwargs):
        from rest_framework.pagination import LimitOffsetPagination
        
        almacen_id = request.query_params.get('almacen_id', None)
        producto_id = request.query_params.get('producto_id')
        search = request.query_params.get('search', '').strip()
        incluir_lotes = request.query_params.get('incluir_lotes', 'false').lower() == 'true'

        # Validación de parámetros
        if search and len(search) < 2:
            return Response({}, status=status.HTTP_204_NO_CONTENT)

        # Obtener almacén si no se proporciona
        if not almacen_id:
            almacen = request.user.almacen
            if not almacen:
                almacen = Almacen.objects.filter(encargado=request.user).first()
                if not almacen:
                    return Response(
                        {'detail': 'El parámetro almacen_id es requerido'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            almacen_id = almacen.id
        else:
            almacen = Almacen.objects.filter(id=almacen_id).first()

        # Query base optimizada
        lotes_query = (
            LoteInventario.objects
            .filter(
                almacen_id=almacen_id,
                status_model=BaseModel.STATUS_MODEL_ACTIVE,
                cantidad__gt=0
            )
            .select_related('producto', 'producto__unidad_sat')
        )

        # Filtrar por producto o búsqueda
        if producto_id:
            lotes_query = lotes_query.filter(producto_id=producto_id)
        elif search:
            lotes_query = lotes_query.filter(producto__nombre__icontains=search)

        # Agrupar por producto
        inventario_agrupado = (
            lotes_query
            .values(
                'producto_id',
                'producto__nombre',
                'producto__unidad_sat__nombre',
                'producto__unidad_sat__clave',
                "producto__codigo",
            )
            .annotate(
                cantidad_total=models.Sum('cantidad'),
                valor_total=models.Sum(models.F('cantidad') * models.F('costo_unitario')),
                numero_lotes=models.Count('id'),
                ultima_actualizacion=models.Max('updated_at'),
                proximo_vencimiento=models.Min('fecha_vencimiento')
            )
            .order_by('proximo_vencimiento', '-numero_lotes')
        )

        # ✅ TOTALES GENERALES (SIN PAGINACIÓN)
        resumen_totales = lotes_query.aggregate(
            valor_total_inventario=models.Sum(models.F('cantidad') * models.F('costo_unitario')),
            total_lotes_real=models.Count('id')
        )

        # Convertir a lista para paginar
        productos_list = list(inventario_agrupado)
        
        # ✅ VERIFICAR SI HAY RESULTADOS ANTES DE PAGINAR
        if not productos_list:
            return Response({
                'count': 0,
                'next': None,
                'previous': None,
                'results': {
                    'almacen_id': almacen.id,
                    'almacen_nombre': almacen.nombre,
                    'almacen_tipo': almacen.get_tipo_display(),
                    'fecha_consulta': timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M:%S'),
                    'total_productos': 0,
                    'total_lotes': 0,
                    'productos': []
                }
            }, status=status.HTTP_200_OK)
        
        # ✅ VALIDAR Y CORREGIR PARÁMETROS DE PAGINACIÓN
        try:
            limit = int(request.query_params.get('limit', 10))
            offset = int(request.query_params.get('offset', 0))
        except (ValueError, TypeError):
            limit = 10
            offset = 0
        
        # ✅ VALIDAR QUE LIMIT NO SEA 0 O NEGATIVO
        if limit <= 0:
            limit = 10  # Valor por defecto
        
        # ✅ VALIDAR QUE OFFSET NO SEA NEGATIVO
        if offset < 0:
            offset = 0
        
        # ✅ APLICAR PAGINACIÓN
        paginator = LimitOffsetPagination()
        paginator.default_limit = limit
        
        productos_paginados = paginator.paginate_queryset(productos_list, request)
        
        # ✅ SI EL OFFSET ES MAYOR QUE EL TOTAL, AJUSTAR A ÚLTIMA PÁGINA
        if not productos_paginados:
            total = len(productos_list)
            last_offset = max(0, ((total - 1) // limit) * limit)
            
            request.query_params._mutable = True
            request.query_params['offset'] = str(last_offset)
            request.query_params._mutable = False
            
            productos_paginados = paginator.paginate_queryset(productos_list, request)
        
        # ✅ PREPARAR LOTES SOLO PARA PRODUCTOS PAGINADOS
        lotes_por_producto = {}
        if incluir_lotes and productos_paginados:
            productos_ids = [p['producto_id'] for p in productos_paginados]
            lotes_detallados = (
                lotes_query
                .filter(producto_id__in=productos_ids)
                .prefetch_related('ubicacion')
                .order_by('fecha_vencimiento')
            )
            
            for lote in lotes_detallados:
                if lote.producto_id not in lotes_por_producto:
                    lotes_por_producto[lote.producto_id] = []
                
                lotes_por_producto[lote.producto_id].append({
                    'id': lote.id,
                    'cantidad': lote.cantidad,
                    'costo_unitario': lote.costo_unitario,
                    'fecha_vencimiento': lote.fecha_vencimiento.strftime('%Y-%m-%d') if lote.fecha_vencimiento else None,
                    'fecha_ingreso': lote.fecha_ingreso.strftime('%Y-%m-%d %H:%M:%S') if lote.fecha_ingreso else None,
                    'ubicacion': lote.ubicacion.nombre if lote.ubicacion else None
                })

        # ✅ CONSTRUIR RESPUESTA CON PRODUCTOS PAGINADOS
        productos_data = []
        for item in productos_paginados:
            productos_data.append({
                'producto_id': item['producto_id'],
                'codigo': item['producto__codigo'],
                'producto_nombre': item['producto__nombre'],
                'cantidad_total': item['cantidad_total'],
                'valor_total': item['valor_total'],
                'numero_lotes': item['numero_lotes'],
                'unidad_medida': item['producto__unidad_sat__nombre'],
                'unidad_clave': item['producto__unidad_sat__clave'],
                'ultima_actualizacion': item['ultima_actualizacion'],
                'lotes_relacionados': lotes_por_producto.get(item['producto_id'], [])
            })

        datos_inventario = {
            'almacen_id': almacen.id,
            'almacen_nombre': almacen.nombre,
            'almacen_tipo': almacen.get_tipo_display(),
            'fecha_consulta': timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M:%S'),
            'total_productos': len(productos_list),
            'total_lotes': resumen_totales['total_lotes_real'] or 0,
            'productos': productos_data
        }

        return paginator.get_paginated_response(datos_inventario)
        
        
    
      
"""
================================================================================
                    DETALLES DEL INVENTARIO POR PRODUCTO
================================================================================
"""
@extend_schema(
    summary="Consultar inventario de un producto",
    description="Obtiene el inventario de un producto específico en todos los almacenes o uno específico",
    parameters=[
        OpenApiParameter(
            name="producto_id",
            type=int,
            location=OpenApiParameter.QUERY,
            required=True,
            description="ID del producto para consultar inventario"
        ),
        OpenApiParameter(
            name="almacen_id",
            type=int,
            location=OpenApiParameter.QUERY,
            required=False,
            description="ID del almacén específico (opcional, si no se especifica muestra todos)"
        ),
        OpenApiParameter(
            name="incluir_lotes",
            type=bool,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Incluir detalles de lotes individuales"
        )
    ],
    responses={200: DetalleInventarioPorProductoSerializer}
)
class InventarioProductoAPIView(APIView):
    """
    Vista para consultar inventario de un producto específico en todos los almacenes
    """
    def get(self, request, *args, **kwargs):
        user = request.user
        producto_id = request.query_params.get('producto_id')
        almacen_id = request.query_params.get('almacen_id')
        incluir_lotes = True#request.query_params.get('incluir_lotes', 'false').lower() == 'true'
        
        if not producto_id:
            return Response({"detail": "Producto ID es requerido"}, status=status.HTTP_400_BAD_REQUEST)

        # Verificar que el producto existe
        try:
            producto = Producto.objects.select_related('unidad_sat').get(id=producto_id)
        except Producto.DoesNotExist:
            return Response({"detail": "Producto no encontrado"}, status=status.HTTP_404_NOT_FOUND)

        # ========== PASO 1: OBTENER TODOS LOS ALMACENES FIJOS ==========
        almacenes_query = Almacen.objects.filter(
            status_model=BaseModel.STATUS_MODEL_ACTIVE,
            tipo__in=[Almacen.TIPO_FIJO]
        )
        # Filtrar por almacén específico si se proporciona
        if almacen_id:
            almacenes_query = almacenes_query.filter(id=almacen_id)
        
        almacenes_query = almacenes_query.order_by('nombre')
        
        # ========== PASO 2: CONSULTAR INVENTARIO DEL PRODUCTO ==========
        lotes_query = LoteInventario.objects.filter(
            producto=producto,
            status_model=BaseModel.STATUS_MODEL_ACTIVE,
            cantidad__gt=0
        ).select_related('almacen', 'ubicacion')
        
        # Filtrar por almacén si se especifica
        if almacen_id:
            lotes_query = lotes_query.filter(almacen_id=almacen_id)
        else:
            # Solo lotes de almacenes fijos
            lotes_query = lotes_query.filter(
                almacen__tipo=Almacen.TIPO_FIJO,
                #almacen__is_cedis=False
            )
        
        # Agrupar inventario por almacén
        inventario_por_almacen = lotes_query.values(
            'almacen__id'
        ).annotate(
            cantidad_total=models.Sum('cantidad'),
            valor_total=models.Sum(models.F('cantidad') * models.F('costo_unitario')),
            numero_lotes=models.Count('id')
        )
        
        # Crear diccionario de inventario por almacén_id
        inventario_dict = {
            item['almacen__id']: {
                'cantidad_total': item['cantidad_total'],
                'valor_total': item['valor_total'],
                'numero_lotes': item['numero_lotes']
            }
            for item in inventario_por_almacen
        }
        
        # ========== PASO 3: CALCULAR TOTALES GLOBALES ==========
        totales_globales = lotes_query.aggregate(
            cantidad_total_global=models.Sum('cantidad'),
            valor_total_global=models.Sum(models.F('cantidad') * models.F('costo_unitario')),
            total_lotes_global=models.Count('id'),
            total_almacenes_con_stock=models.Count('almacen', distinct=True)
        )
        
        # Obtener costo del último lote
        ultimo_lote = lotes_query.order_by('-fecha_ingreso').first()
        costo_ultimo_lote = ultimo_lote.costo_unitario if ultimo_lote else 0
        
        # ========== PASO 4: PREPARAR DATOS DEL PRODUCTO ==========
        datos_producto = {
            'producto_id': producto.id,
            'producto_nombre': producto.nombre,
            'producto_codigo': producto.codigo or 'Sin código',
            'precio_publico': producto.precio_publico or 0,
            'precio_mayoreo': producto.precio_mayoreo or 0,
            'costo_ultimo_lote': costo_ultimo_lote,
            'unidad_medida': producto.unidad_sat.nombre if producto.unidad_sat else 'Sin unidad',
            'unidad_clave': producto.unidad_sat.clave if producto.unidad_sat else 'N/A',
            'fecha_consulta': timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M:%S'),
            'cantidad_total_global': totales_globales['cantidad_total_global'] or 0,
            'total_almacenes': almacenes_query.count(),
            'total_lotes_global': totales_globales['total_lotes_global'] or 0,
            'almacenes': []
        }
        
        # ========== PASO 5: PREPARAR LOTES POR ALMACÉN SI SE SOLICITAN ==========
        lotes_por_almacen = {}
        if incluir_lotes:
            lotes_detallados = lotes_query.all()
            for lote in lotes_detallados:
                lotes_por_almacen.setdefault(lote.almacen_id, []).append(lote)
        
        # ========== PASO 6: CONSTRUIR LISTA DE ALMACENES ==========
        almacenes_list = []
        for almacen in almacenes_query:
            inventario = inventario_dict.get(almacen.id, {
                'cantidad_total': 0,
                'valor_total': 0,
                'numero_lotes': 0
            })
            
            # Crear objeto AlmacenData
            class AlmacenData:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)
            
            almacen_data = AlmacenData(
                almacen_id=almacen.id,
                almacen_nombre=almacen.nombre,
                almacen_tipo=almacen.tipo,
                cantidad_total=inventario['cantidad_total'],
                valor_total=inventario['valor_total'],
                numero_lotes=inventario['numero_lotes']
            )
            
            # Incluir lotes si se solicitaron
            if incluir_lotes:
                almacen_data.lotes_relacionados = lotes_por_almacen.get(almacen.id, [])
            else:
                almacen_data.lotes_relacionados = []
            
            almacenes_list.append(almacen_data)
        
        # ✅ ORDENAR ALMACENES POR CANTIDAD_TOTAL (MAYOR A MENOR)
        almacenes_list.sort(key=lambda x: x.cantidad_total, reverse=True)
        datos_producto['almacenes'] = almacenes_list
        
        # ========== PASO 7: SERIALIZAR Y RETORNAR ==========
        class DatosProducto:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
        
        datos_obj = DatosProducto(**datos_producto)
        serializer = DetalleInventarioPorProductoSerializer(datos_obj)
        
        return Response(serializer.data, status=status.HTTP_200_OK)

# 
"""
================================================================================
                    DETALLES DEL INVENTARIO POR PRODUCTO
================================================================================
"""
@extend_schema(
    summary="Balance de inventario por rack",
    description="Obtiene el inventario consolidado de un rack específico",
    parameters=[
        OpenApiParameter(
            name="rack_id",
            type=int,
            location=OpenApiParameter.QUERY,
            required=True,
            description="ID del rack para consultar inventario"
        ),
        OpenApiParameter(
            name="producto_id",
            type=int,
            location=OpenApiParameter.QUERY,
            required=False,
            description="ID del producto para filtrar (opcional)"
        ),
        
        OpenApiParameter(
            name="incluir_lotes",
            type=bool,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Incluir detalles de lotes individuales"
        )
    ],
    responses={200: DetalleInventarioRackSerializer}
)
class InventarioProductoCedisAPIView(APIView):
    """
    API View para obtener detalles del inventario de un producto en CEDIS por RACK, ZONA O PISOS 
    """
    def get(self, request, *args, **kwargs):
        producto_id = request.query_params.get("producto_id")
        rack_id = request.query_params.get("rack_id")
        incluir_lotes = request.query_params.get("incluir_lotes", "false").lower() == "true"

        if not rack_id:
            return Response({"detail": "rack_id es requerido"}, status=400)

        try:
            rack_model = Rack.objects.get(id=rack_id, status_model=BaseModel.STATUS_MODEL_ACTIVE)
        except Rack.DoesNotExist:
            return Response({"detail": "Rack no encontrado"}, status=404)

        # -------------------
        # Agregación por producto en la DB
        # -------------------
        productos_agg = LoteInventario.objects.filter(
            status_model=BaseModel.STATUS_MODEL_ACTIVE,
            ubicacion=rack_model,
            cantidad__gt=0
        ).order_by("fecha_vencimiento")

        if producto_id:
            productos_agg = productos_agg.filter(producto_id=producto_id)

        productos_agg = productos_agg.values(
            "producto_id",
            "producto__nombre",
            "producto__unidad_sat__nombre",
            "producto__unidad_sat__clave"
        ).annotate(
            cantidad_total=models.Sum("cantidad"),
            valor_total=models.Sum(models.F("cantidad")*models.F("costo_unitario")),
            numero_lotes=models.Count("id")
        )

        productos_list = list(productos_agg)

        # -------------------
        # Si no se requieren lotes, retornamos inmediatamente
        # -------------------
        if not incluir_lotes:
            # Crear objetos ProductoData para consistencia
            productos_finales = []
            for p in productos_list:
                class ProductoData:
                    def __init__(self, **kwargs):
                        for key, value in kwargs.items():
                            setattr(self, key, value)
                
                producto_obj = ProductoData(
                    producto_id=p["producto_id"],
                    producto_nombre=p["producto__nombre"],
                    cantidad_total=p["cantidad_total"],
                    valor_total=p["valor_total"],
                    numero_lotes=p["numero_lotes"],
                    unidad_medida=p["producto__unidad_sat__nombre"] or "Sin unidad",
                    unidad_clave=p["producto__unidad_sat__clave"] or "N/A",
                    lotes_relacionados=[]  # Sin lotes
                )
                productos_finales.append(producto_obj)
            
            class DatosRack:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)
                        
            rack_obj = DatosRack(
                id=rack_model.id,
                nombre=rack_model.nombre,
                fecha_consulta=timezone.now(),
                total_productos=len(productos_list),
                total_lotes=sum(p["numero_lotes"] for p in productos_list),
                cantidad_total=sum(p["cantidad_total"] for p in productos_list),
                valor_total=sum(p["valor_total"] for p in productos_list),
                productos=productos_finales
            )
            
            serializer = DetalleInventarioRackSerializer(rack_obj)
            return Response(serializer.data, status=200)

        # -------------------
        # Solo traer lotes si se piden
        # -------------------
        productos_ids = [p["producto_id"] for p in productos_list]

        lotes = LoteInventario.objects.filter(
            status_model=BaseModel.STATUS_MODEL_ACTIVE,
            ubicacion=rack_model,
            cantidad__gt=0,
            producto_id__in=productos_ids
        ).select_related('producto', 'producto__unidad_sat', 'ubicacion').order_by("fecha_vencimiento")

        # Agrupar lotes por producto
        lotes_por_producto = {}
        for lote in lotes:
            lotes_por_producto.setdefault(lote.producto_id, []).append(lote)

        #print(f"DEBUG VIEW: Total lotes encontrados: {len(lotes)}")
        #print(f"DEBUG VIEW: Productos con lotes: {len(lotes_por_producto)}")
        #for producto_id, lotes_list in lotes_por_producto.items():
        #    print(f"DEBUG VIEW: Producto {producto_id} tiene {len(lotes_list)} lotes")

        # Construir productos con lotes
        productos_finales = []
        class ProductoData:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)
        for p in productos_list:
            # Crear objeto ProductoData para que el serializer pueda acceder a los atributos
            producto_obj = ProductoData(
                producto_id=p["producto_id"],
                producto_nombre=p["producto__nombre"],
                cantidad_total=p["cantidad_total"],
                valor_total=p["valor_total"],
                numero_lotes=p["numero_lotes"],
                unidad_medida=p["producto__unidad_sat__nombre"] or "Sin unidad",
                unidad_clave=p["producto__unidad_sat__clave"] or "N/A"
            )
            
            # Agregar lotes_relacionados para que el serializer los encuentre
            if incluir_lotes:
                producto_obj.lotes_relacionados = lotes_por_producto.get(p["producto_id"], [])
                #print(f"DEBUG VIEW: Producto {p['producto_id']} asignado con {len(producto_obj.lotes_relacionados)} lotes")
            else:
                producto_obj.lotes_relacionados = []
                #print(f"DEBUG VIEW: Producto {p['producto_id']} sin lotes (incluir_lotes=False)")
                
            productos_finales.append(producto_obj)

        # -------------------
        # Construir rack final
        # -------------------
        class DatosRack:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
                    
        rack_obj = DatosRack(
            id=rack_model.id,
            nombre=rack_model.nombre,
            fecha_consulta=timezone.now(),
            total_productos=len(productos_list),
            total_lotes=sum(p["numero_lotes"] for p in productos_list),
            cantidad_total=sum(p["cantidad_total"] for p in productos_list),
            valor_total=sum(p["valor_total"] for p in productos_list),
            productos=productos_finales
        )

        serializer = DetalleInventarioRackSerializer(rack_obj)
        return Response(serializer.data, status=200)
   









"""
*******************************************************************
                VIEWS PARA MOVIMIENTOS DE ENTRADA INVENTARIO
*******************************************************************
"""

""" Listar entradas de inventario por tipo """
class EntradaListViewSet(ListAPIView):
    serializer_class = CompraMiniListSerializer
    pagination_class = None  # Desactivar paginación para este endpoint

    @extend_schema(
        summary="Listar entradas de inventario",
        description="""
        Obtiene una lista de entradas de inventario filtradas por tipo.
        
        **Tipos disponibles:**
        - `ENTRADA ABASTECIMIENTO`: Compras en camino al almacén
        - `ENTRADA TRASPASO`: Traspasos de entrada pendientes de recibir

        **Nota:** Por el momento solo retorna datos de compras (CompraMiniListSerializer)
        """,
        parameters=[
            OpenApiParameter(
                name='tipo',
                type=str,
                location=OpenApiParameter.QUERY,
                required=True,
                description='Tipo de entrada a consultar',
                enum=[
                    MovimientoInventario.ENTRADA_ABASTECIMIENTO,
                    MovimientoInventario.ENTRADA_TRASPASO
                ],
                examples=[
                    OpenApiExample('Abastecimientos', value=MovimientoInventario.ENTRADA_ABASTECIMIENTO),
                    OpenApiExample('Traspasos', value=MovimientoInventario.ENTRADA_TRASPASO),
                ]
            ),
            OpenApiParameter(
                name='almacen',
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description='ID del almacén destino (opcional)',
                examples=[
                    OpenApiExample('Almacén principal', value=1),
                    OpenApiExample('Almacén secundario', value=2),
                ]
            ),
        ],
        responses={
            200: CompraMiniListSerializer(many=True),
            400: 'Parámetros inválidos'
        },
        tags=['Inventario - Entradas']
    )
    def get(self, request, *args, **kwargs):
        tipo = request.query_params.get('tipo', None)
        almacen_id = request.query_params.get('almacen', None)
        
        # Validar tipo requerido
        if tipo not in [MovimientoInventario.ENTRADA_ABASTECIMIENTO, MovimientoInventario.ENTRADA_TRASPASO]:
            return Response(
                {
                    "detail": "Parámetro 'tipo' inválido o no proporcionado.",
                    "tipos_validos": [
                        MovimientoInventario.ENTRADA_ABASTECIMIENTO,
                        MovimientoInventario.ENTRADA_TRASPASO
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Obtener almacén si no se especifica
        if not almacen_id:
            try:
                #obtener el alamcen del usuario que hace la peticion
                almacen = request.user.almacen
                if not almacen:
                    almacen = Almacen.objects.filter(
                        encargado_id=request.user.id,
                        status_model=BaseModel.STATUS_MODEL_ACTIVE
                    ).first()
                #print(almacen)
                almacen_id = almacen.id
            except:
                return Response(
                    {"detail": f"Almacén no encontrado para el usuario {request.user.get_full_name()} - {request.user.username}."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Obtener queryset según tipo
        match tipo:
            case MovimientoInventario.ENTRADA_ABASTECIMIENTO:
                queryset = Compra.objects.filter(
                    estado=Compra.EN_CAMINO,
                    status_model=BaseModel.STATUS_MODEL_ACTIVE
                ).select_related('proveedor', 'almacen_destino').order_by('-created_at')
                
                if almacen_id:
                    queryset = queryset.filter(almacen_destino_id=almacen_id)
                
            case MovimientoInventario.ENTRADA_TRASPASO:
                # Por el momento retorna queryset vacío para traspasos
                queryset = Compra.objects.none()
                
            case _:
                queryset = Compra.objects.none()

        # Serializar y retornar
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'tipo': tipo,
            'total': queryset.count(),
            'data': serializer.data
        }, status=status.HTTP_200_OK)


class MisEntradasListViewSet(mixins.ListModelMixin, 
                             mixins.RetrieveModelMixin,
                             viewsets.GenericViewSet):
    """
    ViewSet para listar y ver detalles de entradas de inventario del almacén del usuario
    """
    #pagination_class =

    def get_serializer_class(self):
        """Usar diferentes serializers para list y retrieve"""
        if self.action == 'retrieve':
            return MovimientoPrincipalSerializer
        return MovimimientosMiniSerializer
   
    def get_queryset(self):
        """Queryset optimizado con select_related y prefetch_related"""
        fase = self.request.query_params.get('fase', MovimientoInventario.FASE_PROCESO)
        almacen = self.request.user.almacen
        if not almacen:
            almacen = Almacen.objects.filter(
                encargado_id=self.request.user.id,
                status_model=BaseModel.STATUS_MODEL_ACTIVE
            ).first()
        if not almacen:
            return MovimientoInventario.objects.none()
        
        if fase not in [MovimientoInventario.FASE_PROCESO, MovimientoInventario.FASE_TERMINADA]:
            return MovimientoInventario.objects.none()
        
        # Queryset base optimizado
        queryset = MovimientoInventario.objects.filter(
            almacen_destino=almacen,
            fase=fase,
        ).select_related(
            'almacen',
            'almacen_destino'
        ).prefetch_related(
            'productosMovimiento__producto__unidad_sat',
            'productosMovimiento__lote'
        ).order_by('-created_at')
        
        return queryset
    
    @extend_schema(
        summary="Listar mis entradas de inventario",
        description="Obtiene la lista de entradas de inventario del almacén del usuario autenticado",
        parameters=[
            OpenApiParameter(
                name='fase',
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Fase del movimiento (por defecto: FASE PROCESO)',
                enum=[MovimientoInventario.FASE_PROCESO, MovimientoInventario.FASE_TERMINADA],
                examples=[
                    OpenApiExample('En proceso', value=MovimientoInventario.FASE_PROCESO),
                    OpenApiExample('Terminadas', value=MovimientoInventario.FASE_TERMINADA),
                ]
            ),
        ],
        responses={200: MovimimientosMiniSerializer(many=True)},
        tags=['Inventario - Entradas']
    )
    def list(self, request, *args, **kwargs):
        """Lista las entradas de inventario"""
        return super().list(request, *args, **kwargs)
    
    @extend_schema(
        summary="Detalle de una entrada de inventario",
        description="Obtiene el detalle completo de una entrada de inventario específica, incluyendo todos los productos y lotes",
        responses={
            200: MovimientoPrincipalSerializer,
            404: 'Entrada no encontrada'
        },
        tags=['Inventario - Entradas']
    )
    def retrieve(self, request, pk=None, *args, **kwargs):
        """Obtiene el detalle de una entrada específica"""
        try:
            movimiento = self.get_queryset().get(pk=pk)
            mov_sec = MovimientoInventario.objects.filter(referencia=f"MOV-TRASP-VIT-{pk}").first()
        except MovimientoInventario.DoesNotExist:
            return Response(
                {'error': 'Entrada de inventario no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Estructurar datos para MovimientoPrincipalSerializer
        productos_data = []
        productos_movimiento = mov_sec.productosMovimiento.all()
        
        # Agrupar por producto
        productos_dict = {}
        for pm in productos_movimiento:
            producto_id = pm.producto.id
            if producto_id not in productos_dict:
                productos_dict[producto_id] = {
                    'producto': pm.producto,
                    'cantidad': 0,
                    'lotes': []
                }
            
            productos_dict[producto_id]['cantidad'] += pm.cantidad
            if pm.lote:
                productos_dict[producto_id]['lotes'].append({
                    'lote': str(pm.lote.id),
                    'cantidad': pm.cantidad
                })
        
        # Convertir a lista
        for producto_id, data in productos_dict.items():
            productos_data.append({
                'producto': data['producto'],
                'cantidad': data['cantidad'],
                'lotes': data['lotes']
            })
        
        # Crear datos para el serializer
        movimiento_data = {
            'id': movimiento.id,
            'almacen': movimiento.almacen,
            'almacen_destino': movimiento.almacen_destino,
            'movimiento': movimiento.movimiento,
            'tipo': movimiento.tipo,
            'referencia': movimiento.referencia,
            'cantidad': movimiento.cantidad,
            'nota': movimiento.nota,
            'productos': productos_data,
            'detalle_nota': movimiento.detalle_nota,
            'fase': movimiento.fase,
            'created_at': movimiento.created_at,
        }
        
        serializer = MovimientoPrincipalSerializer(movimiento_data)
        return Response(serializer.data, status=status.HTTP_200_OK)


"""
===================================================================
            PROCESAR ENTRADA DE INVENTARIO (RECIBIR TRASPASO)
===================================================================
"""
class ProcesarEntradaView(APIView):
    """
    Vista para procesar/recibir una entrada de inventario pendiente
    """
    
    @extend_schema(
        summary="Procesar entrada de inventario",
        description="""
        Procesa (recibe) una entrada de inventario que está en estado FASE PROCESO.
        
        **Flujo:**
        1. Valida que la entrada exista y esté en FASE PROCESO
        2. Valida que el almacen_destino sea el del usuario autenticado
        3. Recibe los productos, cantidades y lotes a ingresar
        4. Crea/actualiza lotes en el almacén destino
        5. Cambia la fase a FASE TERMINADA
        """,
        request=MovimientoEntradaSerializer,
        responses={
            200: {
                'description': 'Entrada procesada exitosamente',
                'content': {
                    'application/json': {
                        'example': {
                            'success': True,
                            'message': 'Entrada de inventario procesada exitosamente',
                            'movimiento_id': 123,
                            'referencia': 'MOV-SALIDA TRASPASO-1',
                            'productos_procesados': 3,
                            'lotes_procesados': 5
                        }
                    }
                }
            },
            400: {
                'description': 'Error de validación',
                'content': {
                    'application/json': {
                        'examples': {
                            'ya_procesada': {
                                'summary': 'Entrada ya procesada',
                                'value': {'error': 'La entrada ya fue procesada'}
                            },
                            'no_pertenece': {
                                'summary': 'No pertenece al almacén',
                                'value': {'error': 'Esta entrada no pertenece a tu almacén'}
                            }
                        }
                    }
                }
            },
            404: {
                'description': 'Entrada no encontrada',
                'content': {
                    'application/json': {
                        'example': {
                            'error': 'Entrada de inventario no encontrada'
                        }
                    }
                }
            }
        },
        tags=['Inventario - Entradas']
    )
    def post(self, request):
        """Procesa una entrada de inventario pendiente con productos y lotes"""
        
        # Validar con el serializer
        serializer = MovimientoEntradaSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Datos inválidos', 'detalles': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        movimiento = serializer.validated_data['movimiento']
        productos_data = serializer.validated_data['productos']
        
        # Obtener almacén del usuario
        almacen_usuario = request.user.almacen
        if not almacen_usuario:
            almacen_usuario = Almacen.objects.filter(
                encargado_id=request.user.id,
                status_model=BaseModel.STATUS_MODEL_ACTIVE
            ).first()
        
        #if not almacen_usuario:
        #    return Response(
        #        {'error': 'El usuario no tiene un almacén asignado'},
        #        status=status.HTTP_400_BAD_REQUEST
        #    )
        
        # Validaciones
        if movimiento.almacen_destino_id != almacen_usuario.id:
            return Response(
                {'detail': f'Esta entrada no pertenece a tu almacén {almacen_usuario.nombre}. El destino es almacen {movimiento.almacen_destino.nombre}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if movimiento.fase == MovimientoInventario.FASE_TERMINADA:
            return Response(
                {'detail': 'La entrada ya fue procesada anteriormente'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if movimiento.fase != MovimientoInventario.FASE_PROCESO:
            return Response(
                {'error': f'La entrada está en fase {movimiento.fase}, no se puede procesar'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # ========================================================
        # PROCESAR ENTRADA: AQUÍ VA TU LÓGICA PERSONALIZADA
        # ========================================================
        from ..helpers.movimientosEntrada import create_movimiento_entrada
        with transaction.atomic():
            mov = create_movimiento_entrada(movimiento, productos_data, user=request.user)
            
            return Response({
                'success': True,
                'message': 'Entrada de inventario procesada exitosamente',
                'movimiento_id': mov.id,
                'referencia': mov.referencia,
                'almacen_destino': movimiento.almacen_destino.nombre,
                #'productos_procesados': productos_procesados,
                #'lotes_procesados': lotes_procesados,
                #'cantidad_total': str(movimiento.cantidad)
            }, status=status.HTTP_200_OK)
        try:
            pass
                
        except Exception as e:
            return Response(
                {'error': f'Error al procesar la entrada: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
       


"""CREAR UNA ENTRADA DE INVENTARIO (ABASTECIMIENTO)"""

class AbastecimientoCreateView(APIView):
    """
    Vista para crear entrada de inventario por abastecimiento desde una compra
    """
    
    @extend_schema(
        summary="Crear abastecimiento de inventario (Compra)",
        description="""
        Crea una entrada de inventario por abastecimiento desde una orden de compra específica.
        
        **Proceso:**
        1. Valida que la orden de compra exista y esté en estado válido
        2. Obtiene el almacén destino de la orden de compra
        3. Crea los lotes de inventario para cada producto
        4. Registra los movimientos de inventario
        5. Actualiza el estado de la compra relacionada
        
        **Validaciones importantes:**
        - La compra debe existir y estar en estado "EN_CAMINO"
        - Para almacenes tipo CEDIS es obligatorio especificar ubicacion_rack
        - Los productos deben existir y estar activos
        - Se validan diferencias entre cantidades ordenadas vs recibidas
        
        **Efectos del proceso:**
        - Se crean lotes de inventario para cada producto
        - Se registra un movimiento principal de entrada
        - Se actualizan los estados de compra y orden de compra a "FINALIZADA"
        - Se detectan y marcan diferencias en cantidades si las hay
        """,
        request=MovimientoEntradaAbastecimientoSerializer,
        responses={
            201: OpenApiResponse(
                response=AbastecimientoSuccessResponseSerializer,
                description="Abastecimiento creado exitosamente",
                examples=[
                    OpenApiExample(
                        'Abastecimiento exitoso',
                        summary='Ejemplo de respuesta exitosa',
                        description='Respuesta cuando el abastecimiento se procesa correctamente',
                        value={
                            "success": True,
                            "message": "Abastecimiento realizado exitosamente",
                            "data": {
                                "movimiento_principal": {
                                    "id": 123,
                                    "referencia": "ABAST-COMP-001-20251020143052",
                                    "tipo": "TIPO_ENTRADA",
                                    "movimiento": "ENTRADA ABASTECIMIENTO",
                                    "fase": "FASE_TERMINADA"
                                },
                                "compra": {
                                    "id": 45,
                                    "codigo": "COMP-001",
                                    "estado_actual": "FINALIZADA"
                                },
                                "almacen_destino": {
                                    "id": 2,
                                    "nombre": "Almacén Principal",
                                    "tipo": "CEDIS"
                                },
                                "resumen": {
                                    "total_items": 3,
                                    "cantidad_total": 150.0,
                                    "costo_total": 3750.0,
                                    "costo_promedio": 25.0,
                                    "lotes_creados": 3
                                },
                                "productos_abastecidos": [
                                    {
                                        "producto": {
                                            "id": 10,
                                            "nombre": "Laptop Dell Inspiron",
                                            "codigo": "LAP-001"
                                        },
                                        "lote_id": 150,
                                        "cantidad": 50.0,
                                        "costo_unitario": 25.0,
                                        "costo_total": 1250.0,
                                        "ubicacion": "Rack A-1-1"
                                    },
                                    {
                                        "producto": {
                                            "id": 11,
                                            "nombre": "Mouse Inalámbrico",
                                            "codigo": "MOU-001"
                                        },
                                        "lote_id": 151,
                                        "cantidad": 100.0,
                                        "costo_unitario": 25.0,
                                        "costo_total": 2500.0,
                                        "ubicacion": "Rack B-2-3"
                                    }
                                ],
                                "metadatos": {
                                    "referencia": "ABAST-COMP-001-20251020143052",
                                    "nota": "Abastecimiento de compra semanal",
                                    "fecha_proceso": "2025-10-20T14:30:52.123456Z",
                                    "procesado_por": {
                                        "id": 1,
                                        "username": "admin"
                                    }
                                }
                            }
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                response=AbastecimientoErrorResponseSerializer,
                description="Error en los datos enviados",
                examples=[
                    OpenApiExample(
                        'Error de validación',
                        summary='Datos inválidos',
                        description='Error cuando los datos enviados no son válidos',
                        value={
                            "success": False,
                            "message": "Error en los datos enviados",
                            "errors": {
                                "compra": ["Este campo es requerido."],
                                "items": ["Esta lista no puede estar vacía."]
                            }
                        }
                    ),
                    OpenApiExample(
                        'Compra en estado inválido',
                        summary='Estado de compra incorrecto',
                        description='Error cuando la compra no está en estado válido',
                        value={
                            "success": False,
                            "message": "La compra debe estar en estado 'EN_CAMINO'. Estado actual: FINALIZADA",
                            "errors": {
                                "detail": "La compra debe estar en estado 'EN_CAMINO'. Estado actual: FINALIZADA"
                            }
                        }
                    )
                ]
            ),
            404: OpenApiResponse(
                response=AbastecimientoErrorResponseSerializer,
                description="Compra no encontrada",
                examples=[
                    OpenApiExample(
                        'Compra no encontrada',
                        summary='ID de compra inválido',
                        value={
                            "success": False,
                            "message": "Compra con ID 999 no encontrada",
                            "errors": {
                                "detail": "Compra con ID 999 no encontrada"
                            }
                        }
                    )
                ]
            ),
            500: OpenApiResponse(
                response=AbastecimientoErrorResponseSerializer,
                description="Error interno del servidor",
                examples=[
                    OpenApiExample(
                        'Error interno',
                        summary='Error del sistema',
                        value={
                            "success": False,
                            "message": "Error interno del servidor",
                            "errors": {
                                "detail": "Error de conexión a la base de datos"
                            }
                        }
                    )
                ]
            )
        },
        tags=['Inventario - Entradas']
    )
    def post(self, request):
        serializer = MovimientoEntradaAbastecimientoSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "message": "Error en los datos enviados",
                    "errors": serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                # Usar el servicio para procesar el abastecimiento
                resultado = AbastecimientoService.procesar_abastecimiento_completo(
                    serializer.validated_data, 
                    request.user
                )
                
                return Response(
                    {
                        "success": True,
                        "message": "Abastecimiento realizado exitosamente",
                        "data": resultado
                    },
                    status=status.HTTP_201_CREATED
                )
                
        except ValueError as e:
            return Response(
                {
                    "success": False,
                    "message": str(e),
                    "errors": {"detail": str(e)}
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "message": "Error interno del servidor",
                    "errors": {"detail": str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


