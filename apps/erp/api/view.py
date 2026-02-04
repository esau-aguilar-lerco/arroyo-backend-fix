from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import mixins,viewsets,permissions, status, filters, serializers
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from django.db import models

from drf_spectacular.utils import extend_schema, inline_serializer,OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from apps.base.serachFilter import MinimalSearchFilter


from apps.base.models import BaseModel
from apps.erp.models import (Almacen, Empresa,
                            Producto, Categoria, Proveedor,
                            Sucursal, Cliente, 
                            OrdenCompra,
                            Compra, Rutas,
                            Venta)


from apps.erp.serializers.empresa_serializer import EmpresaMiniSerializer, EmpresaSerializer
from apps.erp.serializers.productos_serializer import CategoriaMiniSerializer, ProductoMiniSerializer, ProductoSerializer, CategoriaSerializer, ProductoInventarioAlamcenSerializer
from apps.erp.serializers.proveedor_serializer import ProveedorMiniSerializer, ProveedorSerializer, ProveedorSolicitudCreditoSerializer
from apps.erp.serializers.cliente_serializer import ClienteMiniSerializer, ClienteSerializer,InformacionClienteSerializer, ClientePerformanceSerializer, ClienteCreditoSerializer
from apps.erp.serializers.almacen_serializer import AlmacenMiniSerializer, AlmacenSerializer
from apps.erp.serializers.sucursal_serializer import SucursalMiniSerializer, SucursalSerializer
from apps.erp.serializers.compras_serializer import (OrdenCompraSerializer, OrdenCompraMiniSerializer, OrdenCompraEstadoSerializer,
                                                     CompraSerializer, CompraMiniSerializer, CompraEstadoSerializer)
from apps.erp.serializers.rutas_serializer import RutasSerializer, RutasMiniSerializer, RutasEstadoSerializer
from apps.inventario.models import LoteInventario

# Permisos personalizados para el modelo LoteInventario
from apps.erp.auth.permisos import (EmpresaPermission,ClientePermission,ProveedorPermission,ProductoPermission,
                                    AlmacenPermission,SucursalPermission,OrdenCompraPermission,CompraPermission,
                                    RutasPermission)



"""
============================================================================================
                            VIEWS DE APIS DE EMPRESA   
============================================================================================
"""
class EmpresaViewSet(viewsets.ModelViewSet):
    queryset = Empresa.objects.all()
    serializer_class = EmpresaSerializer
    permission_classes = [IsAuthenticated, EmpresaPermission]
    
    filter_backends = [MinimalSearchFilter]
    search_fields = ['nombre', 'id', 'rfc']

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(
            self.get_queryset().exclude(status_model=BaseModel.STATUS_MODEL_DELETE)
        )
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if self.is_respuesta_404():
            return self.respuesta_404()

        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(request=inline_serializer(
        name='EmpresaCreateRequest',
        fields={
            'nombre': serializers.CharField(),
            'rfc': serializers.CharField(),
            'telefono': serializers.CharField(required=False, allow_blank=True),
            'email': serializers.EmailField(required=False, allow_blank=True),
            'direccion_fiscal': serializers.CharField(required=False, allow_blank=True),
            'regimen_fiscal': inline_serializer(name='RegimenFK', fields={'id': serializers.IntegerField()}),
            'cuenta_clave': serializers.CharField(required=False, allow_blank=True),
            'status_model': serializers.ChoiceField(choices=Empresa.STATUS_CHOICES, read_only=True)
        }
    ))
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(request=inline_serializer(
        name='EmpresaUpdateRequest',
        fields={
            'nombre': serializers.CharField(required=False),
            'rfc': serializers.CharField(required=False),
            'telefono': serializers.CharField(required=False, allow_blank=True),
            'email': serializers.EmailField(required=False, allow_blank=True),
            'direccion_fiscal': serializers.CharField(required=False, allow_blank=True),
            'regimen_fiscal': inline_serializer(name='RegimenFK', fields={'id': serializers.IntegerField()}),
            'cuenta_clave': serializers.CharField(required=False, allow_blank=True),
            'status_model': serializers.ChoiceField(choices=Empresa.STATUS_CHOICES, read_only=True)

        }
    ))
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
        instance.status_model = BaseModel.STATUS_MODEL_DELETE
        instance.save(update_fields=['status_model'])
        return Response({"detail": "Eliminado correctamente."}, status=status.HTTP_200_OK)

    def is_respuesta_404(self):
        instance = self.get_object()
        return instance.status_model == BaseModel.STATUS_MODEL_DELETE

    def respuesta_404(self):
        return Response(
            {"detail": "No encontrado."},
            status=status.HTTP_404_NOT_FOUND
        )

class EmpresaMiniViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Empresa.objects.all().order_by('nombre')
    serializer_class = EmpresaMiniSerializer
    #permission_classes = [EmpresaPermission]
    filter_backends = [filters.SearchFilter]
    pagination_class = None
    search_fields = ['nombre', 'id', 'rfc']

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(
            self.get_queryset().exclude(status_model=BaseModel.STATUS_MODEL_DELETE)
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    
"""
============================================================================================
                           VIEWS DE APIS DE CATEGORIAS
============================================================================================
"""
class CategoriaViewSet(viewsets.ModelViewSet):
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [MinimalSearchFilter]
    search_fields = ['nombre', 'id',]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(
            self.get_queryset().exclude(status_model=BaseModel.STATUS_MODEL_DELETE)
        )
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

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

        instance.status_model = BaseModel.STATUS_MODEL_DELETE
        instance.save(update_fields=['status_model'])
        return Response({'detail':'Eliminado correctamente'},status=status.HTTP_200_OK)

    def is_respuesta_404(self):
        instance = self.get_object()
        return instance.status_model == BaseModel.STATUS_MODEL_DELETE

    def respuesta_404(self):
        return Response(
            {"detail": "No encontrado."},
            status=status.HTTP_404_NOT_FOUND
        )

class CategoriaMiniViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Categoria.objects.all().filter(status_model=BaseModel.STATUS_MODEL_ACTIVE)
    serializer_class = CategoriaMiniSerializer
    #permission_classes = [permissions.IsAuthenticated]
    filter_backends = [MinimalSearchFilter]
    pagination_class = None
    search_fields = ['nombre', 'id',]
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(
            self.get_queryset().exclude(status_model=BaseModel.STATUS_MODEL_DELETE)
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
"""
============================================================================================
                            VIEWS DE APIS DE PRODUCTOS
============================================================================================
                            VIEWS DE APIS DE PRODUCTOS
"""
class ProductoViewSet(viewsets.ModelViewSet):
    queryset = Producto.objects.all().order_by('-id')
    serializer_class = ProductoSerializer
    permission_classes = [IsAuthenticated,ProductoPermission]
    filter_backends = [MinimalSearchFilter]
    search_fields = ['nombre', 'categoria__nombre', 'id','codigo']

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(
            self.get_queryset().exclude(status_model=BaseModel.STATUS_MODEL_DELETE)
        )
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.horas_caducidad = instance.horas_caducidad / 24
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

        instance.status_model = BaseModel.STATUS_MODEL_DELETE
        instance.save(update_fields=['status_model'])
        return Response({'detail':'Eliminado correctamente'},status=status.HTTP_200_OK)

    def is_respuesta_404(self):
        instance = self.get_object()
        return instance.status_model == BaseModel.STATUS_MODEL_DELETE

    def respuesta_404(self):
        return Response(
            {"detail": "No encontrado."},
            status=status.HTTP_404_NOT_FOUND
        )


class ProductoMiniViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Producto.objects.all().filter(status_model=BaseModel.STATUS_MODEL_ACTIVE).order_by('nombre')
    serializer_class = ProductoMiniSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [MinimalSearchFilter]
    search_fields = ['nombre', 'id', 'codigo']
    pagination_class = None

    def get_serializer_context(self):
        """
        Sobrescribe el contexto para pasar cliente_id y almacen_id al serializer
        """
        context = super().get_serializer_context()
        
        # Obtener parámetros de la URL
        cliente_id = self.request.query_params.get('cliente_id', None)
        almacen_id = self.request.query_params.get('almacen_id', None)
        is_compras = self.request.query_params.get('is_compras', False)
        completo = self.request.query_params.get('completo', False)
        # Agregar al contexto si existen
        if cliente_id:
            context['cliente_id'] = int(cliente_id)
               
        if almacen_id:
            context['almacen_id'] = int(almacen_id)
        
        if almacen_id is None:
            user_almacen = self.request.user.almacen
            #print(f"USER ALMACEN EN PRODUCTO MINI VIEWSET:",self.request.user)
            #print("USER ALMACEN EN PRODUCTO MINI VIEWSET:",user_almacen)
            if user_almacen:
                context['almacen_id'] = user_almacen.id
            else:
                context['almacen_id'] = 1

        if is_compras:
            context['is_compras'] = is_compras.lower() in ['true', '1', 'yes']
            
        if completo:
            context['completo'] = completo.lower() in ['true', '1', 'yes']
        else:
            context['completo'] = False 
           
        return context

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='cliente_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='ID del cliente para calcular precio personalizado según tipo',
                required=False
            ),
            OpenApiParameter(
                name='almacen_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='ID del almacén para obtener inventario específico',
                required=False
            ),
            OpenApiParameter(
                name='is_compras',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='Indica si se está en el contexto de compras para ajustar la búsqueda del precio',
                required=False
            ),
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Buscar por nombre, código o ID',
                required=False
            )
        ],
        summary="productos"
    )
    def list(self, request, *args, **kwargs):
        """
        Lista productos con precio personalizado según cliente y stock según almacén
        """
        completo = self.request.query_params.get('completo', 'false')
        
        complete = completo.lower() in ['true', '1', 'yes']
        
        # Si no es completo, filtrar solo productos con inventario > 0
        if complete:
            # Obtener almacen_id del contexto
            almacen_id = self.request.query_params.get('almacen_id', None)
            
            if not almacen_id:
                user_almacen = self.request.user.almacen
                if user_almacen:
                    almacen_id = user_almacen.id
                else:
                    almacen_id = 1
            
            # Filtrar productos que tengan lotes con cantidad > 0 en el almacén específico
            from apps.inventario.models import LoteInventario
            
            productos_con_stock = LoteInventario.objects.filter(
                almacen_id=almacen_id,
                cantidad__gt=0,
                status_model=BaseModel.STATUS_MODEL_ACTIVE
            ).values_list('producto_id', flat=True).distinct()
            
            # Filtrar el queryset por productos con stock
            self.queryset = self.queryset.filter(id__in=productos_con_stock)
        
        return super().list(request, *args, **kwargs)
class ProductoInventarioAPIView(APIView):
    """
    API para obtener información completa del inventario de un producto
    incluyendo datos del producto, inventario por almacén y último precio
    """
    
    @extend_schema(
        summary="Detalle del inventario del producto por alamcen",
        description="Obtiene información detallada del producto incluyendo inventario, precios, costos y último precio del último lote",
        parameters=[
            inline_serializer(
                name='ProductoInventarioParams',
                fields={
                    'producto_id': serializers.IntegerField(required=True, help_text="ID del producto"),
                    'almacen_id': serializers.IntegerField(required=False, help_text="ID del almacén específico (opcional)")
                }
            )
        ],
        responses={
            200: ProductoInventarioAlamcenSerializer,
            404: inline_serializer(
                name='ProductoNotFound',
                fields={'detail': serializers.CharField()}
            )
        }
    )
    def get(self, request, *args, **kwargs):
        producto_id = request.query_params.get('producto_id')
        almacen_id = request.query_params.get('almacen_id')
        
        # Validar que se proporcione producto_id
        if not producto_id:
            return Response(
                {"detail": "El parámetro 'producto_id' es requerido."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Buscar el producto
        try:
            modelo_producto = Producto.objects.select_related(
                'categoria', 'unidad_sat'
            ).get(id=producto_id)
        except Producto.DoesNotExist:
            return Response(
                {"detail": "Producto no encontrado."}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Determinar el almacén específico si se proporciona
        model_almacen = None
        if almacen_id:
            model_almacen = Almacen.objects.filter(id=almacen_id).first()
        
        if not model_almacen:
            # Buscar si es encargado de almacén
            model_almacen = Almacen.objects.filter(encargado=request.user).first()
            if not model_almacen:
                return Response(
                    {"detail": "Almacén no encontrado."}, 
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Inventario por almacén específico (si se proporciona)
        inventario_almacen = None
        if model_almacen:
            lotes_almacen = LoteInventario.objects.filter(
                producto=modelo_producto,
                almacen=model_almacen,
                status_model=LoteInventario.STATUS_MODEL_ACTIVE,
                cantidad__gt=0
            ).aggregate(
                cantidad_total=models.Sum('cantidad'),
                lotes_count=models.Count('id'),
                costo_promedio=models.Avg('costo_unitario')
            )
            
            inventario_almacen = {
                'almacen_id': model_almacen.id,
                'almacen_nombre': model_almacen.nombre,
                'cantidad_total': float(lotes_almacen['cantidad_total'] or 0),
                'lotes_count': lotes_almacen['lotes_count'] or 0,
                'costo_promedio': float(lotes_almacen['costo_promedio'] or 0)
            }
        
        # Último precio del último lote (independiente del almacén)
        ultimo_lote = LoteInventario.objects.filter(
            producto=modelo_producto,
            status_model=LoteInventario.STATUS_MODEL_ACTIVE
        ).select_related('almacen').order_by('-fecha_ingreso').first()
        
        ultimo_precio = 0
        if ultimo_lote:
            ultimo_precio = ultimo_lote.costo_unitario
        
        # Resumen global del producto en todos los almacenes
        resumen_global_query = LoteInventario.objects.filter(
            producto=modelo_producto,
            status_model=LoteInventario.STATUS_MODEL_ACTIVE,
            cantidad__gt=0
        ).aggregate(
            total_stock=models.Sum('cantidad'),
            almacenes_con_stock=models.Count('almacen', distinct=True),
            # Valor total del inventario (cantidad * costo_unitario)
            valor_inventario=models.Sum(
                models.F('cantidad') * models.F('costo_unitario')
            )
        )
        
        resumen_global = {
            'total_stock': float(resumen_global_query['total_stock'] or 0),
            'almacenes_con_stock': resumen_global_query['almacenes_con_stock'] or 0,
            'valor_inventario': float(resumen_global_query['valor_inventario'] or 0)
        }
        
        # Datos para el serializer
        data = {
            'modelo_producto': modelo_producto,
            'inventario_almacen': inventario_almacen,
            'resumen_global': resumen_global,
            'ultimo_precio': ultimo_precio
        }
        
        # Usar el serializer
        serializer = ProductoInventarioAlamcenSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)
        

"""
============================================================================================
                            VIEWS DE APIS DE PROVEEDORES
============================================================================================
"""
class ProveedorViewSet(viewsets.ModelViewSet):
    queryset = Proveedor.objects.all()
    serializer_class = ProveedorSerializer
    permission_classes = [IsAuthenticated, ProveedorPermission]
    filter_backends = [MinimalSearchFilter]
    search_fields = ['nombre', 'id', 'rfc','codigo','razon_social']

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset().exclude(status_model=Proveedor.STATUS_MODEL_DELETE))
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response( serializer.data,
                )
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data,status=status.HTTP_200_OK)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

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

        instance.status_model = BaseModel.STATUS_MODEL_DELETE
        instance.save(update_fields=['status_model'])
        return Response({'detail':'Eliminado correctamente'},status=status.HTTP_200_OK)

    def is_respuesta_404(self):
        instance = self.get_object()
        return instance.status_model == BaseModel.STATUS_MODEL_DELETE

    def respuesta_404(self):
        return Response(
            {"detail": "No encontrado."},
            status=status.HTTP_404_NOT_FOUND
        )
        
        
    @action(detail=True, methods=['get'], url_path='info-credito', permission_classes=[IsAuthenticated])
    def info_credito(self, request, pk=None):
        """
        Obtener información del cliente para créditos
        
        GET /api/proveedores/{id}/info-credito/
        """
        try:
            proveedor = self.get_object()
            
            if proveedor.status_model == BaseModel.STATUS_MODEL_DELETE:
                return Response(
                    {"detail": "Proveedor no encontrado."},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            serializer = ProveedorSolicitudCreditoSerializer(proveedor)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Proveedor.DoesNotExist:
            return Response(
                {"detail": "Proveedor no encontrado."},
                status=status.HTTP_404_NOT_FOUND
            )
   

class ProveedorMiniViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Proveedor.objects.all().filter(status_model=BaseModel.STATUS_MODEL_ACTIVE).order_by('nombre')
    serializer_class = ProveedorMiniSerializer
    permission_classes = [IsAuthenticated, ]#
    filter_backends = [MinimalSearchFilter]

    pagination_class = None
    search_fields = ['codigo', 'nombre', 'id']

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset().exclude(status_model=Proveedor.STATUS_MODEL_DELETE))
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

"""
============================================================================================
                            VIEWS DE APIS DE CLIENTES
============================================================================================
"""
class ClienteViewSet(viewsets.ModelViewSet):
    queryset = Cliente.objects.all().order_by('-id')  # Assuming Cliente is a subclass of Proveedor
    serializer_class = ClienteSerializer
    permission_classes = [ClientePermission]

    filter_backends = [MinimalSearchFilter]

    search_fields = ['nombre', 'id', 'rfc','codigo','razon_social']

    def list (self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset().exclude(status_model=BaseModel.STATUS_MODEL_DELETE))
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if self.is_respuesta_404():
            return self.respuesta_404()

        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
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

        instance.status_model = BaseModel.STATUS_MODEL_DELETE
        instance.save(update_fields=['status_model'])
        return Response({'detail':'Eliminado correctamente'},status=status.HTTP_200_OK)

    def is_respuesta_404(self):
        instance = self.get_object()
        return instance.status_model == BaseModel.STATUS_MODEL_DELETE

    def respuesta_404(self):
        return Response(
            {"detail": "No encontrado."},
            status=status.HTTP_404_NOT_FOUND
        )
    
    @extend_schema(
        summary="Información del cliente para créditos",
        description="Obtiene información básica del cliente para el módulo de créditos incluyendo datos de límite de crédito, disponible y capacidad de pago.",
        responses={
            200: ClienteCreditoSerializer,
            404: inline_serializer(
                name='ClienteCreditoNotFound',
                fields={'detail': serializers.CharField(default='Cliente no encontrado.')}
            )
        },
        tags=['clientes']
    )
    @action(detail=True, methods=['get'], url_path='info-credito', permission_classes=[IsAuthenticated])
    def info_credito(self, request, pk=None):
        """
        Obtener información del cliente para créditos
        
        GET /api/clientes/{id}/info-credito/
        """
        try:
            cliente = self.get_object()
            
            if cliente.status_model == BaseModel.STATUS_MODEL_DELETE:
                return Response(
                    {"detail": "Cliente no encontrado."},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            serializer = ClienteCreditoSerializer(cliente)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Cliente.DoesNotExist:
            return Response(
                {"detail": "Cliente no encontrado."},
                status=status.HTTP_404_NOT_FOUND
            )

class ClienteMiniViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Cliente.objects.all().filter(status_model=BaseModel.STATUS_MODEL_ACTIVE).order_by('nombre')
    serializer_class = ClienteMiniSerializer
    search_fields = ['id', 'nombre']
    #search_backends = [MinimalSearchFilter]
    filter_backends = [MinimalSearchFilter]
    
    pagination_class = None
    permission_classes = [IsAuthenticated]

    #def list(self, request, *args, **kwargs):
    #    queryset = self.filter_queryset(self.get_queryset().exclude(status_model=BaseModel.STATUS_MODEL_DELETE))
    #    page = self.paginate_queryset(queryset)
    #    if page is not None:
    #        serializer = self.get_serializer(page, many=True)
    #        return self.get_paginated_response(serializer.data)
#
    #    serializer = self.get_serializer(queryset, many=True)
    #    return Response(serializer.data, status=status.HTTP_200_OK)



class InformacionClienteViewSet(viewsets.GenericViewSet):
    """
    ViewSet optimizado para obtener información detallada de un cliente
    """
    serializer_class = InformacionClienteSerializer
    permission_classes = [IsAuthenticated, ClientePermission]
    def get_queryset(self):
        """
        Queryset optimizado con prefetch de datos relacionados
        """
        from django.db.models import Prefetch
        
        return Cliente.objects.filter(
            status_model=BaseModel.STATUS_MODEL_ACTIVE
        ).select_related(
            'vendedor', 'regimen_fiscal'
        ).prefetch_related(
            ## Prefetch direcciones con sus relaciones
            #'direccion_cliente__estado',
            #'direccion_cliente__municipio', 
            #'direccion_cliente__codigo_postal',
            #'direccion_cliente__colonia',
            # Prefetch ventas terminadas con productos para análisis
            Prefetch(
                'ventas',
                queryset=Venta.objects.filter(fase__in=[Venta.FASE_TERMINADA, Venta.FASE_CANCELADA, Venta.FASE_PRE_VENTA])
                .select_related()
                .prefetch_related('detalles__producto')
                .order_by('-created_at')[:50],  # Solo las últimas 50 para optimizar
                to_attr='_ventas_terminadas_prefetch'
            )
        )

    @extend_schema(
        summary="Información del cliente para venta",
        description="Obtiene información completa del cliente incluyendo dirección, últimos productos comprados, ventas recientes, productos favoritos, estado de adeudo y estadísticas de ventas",
        responses={
            200: InformacionClienteSerializer,
            404: inline_serializer(
                name='ClienteNotFound',
                fields={'detail': serializers.CharField(default='Cliente no encontrado.')}
            )
        }
    )
    def retrieve(self, request, *args, **kwargs):
        """
        Obtener información completa de un cliente específico con consultas optimizadas:
        - Datos básicos del cliente
        - Dirección principal  
        - Últimos 5 productos comprados
        - Últimas 10 ventas recientes
        - Top 10 productos favoritos
        - Estado de adeudo
        - Estadísticas de ventas
        """
        try:
            cliente = self.get_object()
            
            # Pre-procesar datos para optimizar serialización
            if hasattr(cliente, '_ventas_terminadas_prefetch'):
                cliente._ventas_terminadas = cliente._ventas_terminadas_prefetch
            
            serializer = self.get_serializer(cliente)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Cliente.DoesNotExist:
            return Response(
                {"detail": "Cliente no encontrado."},
                status=status.HTTP_404_NOT_FOUND
            )


"""
============================================================================================
#             ALMACEN VIEWSET
#=================================================================
"""
class AlmacenViewSet(viewsets.ModelViewSet):
    queryset = Almacen.objects.all()
    serializer_class = AlmacenSerializer
    permission_classes = [IsAuthenticated, AlmacenPermission]
    filter_backends = [MinimalSearchFilter]
    search_fields = ['codigo', 'nombre', 'id']

    def list (self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset().exclude(status_model=BaseModel.STATUS_MODEL_DELETE)).filter(tipo__in=[Almacen.TIPO_FIJO, Almacen.TIPO_RUTA]).order_by('-id')
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

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

        instance.status_model = BaseModel.STATUS_MODEL_DELETE
        instance.save(update_fields=['status_model'])
        return Response({'detail':'Elimindo correctamente'},status=status.HTTP_200_OK)
    
    
    def is_respuesta_404(self):
        instance = self.get_object()
        return instance.status_model == BaseModel.STATUS_MODEL_DELETE

    def respuesta_404(self):
        return Response(
            {"detail": "No encontrado."},
            status=status.HTTP_404_NOT_FOUND
        )
   
class AlmacenMiniViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    A viewset for listing minimal Almacen instances.

    Query Parameters:
        is_cedis (bool, optional): Filtra los almacenes por el campo 'is_cedis'.
            Ejemplo: ?is_cedis=true o ?is_cedis=false

    Excludes objects with status_model set to BaseModel.STATUS_MODEL_DELETE.
    Pagination is disabled for this viewset.
    """
    queryset = Almacen.objects.all().filter(status_model__in=[BaseModel.STATUS_MODEL_ACTIVE, BaseModel.STATUS_MODEL_INACTIVE], tipo__in=[Almacen.TIPO_FIJO, Almacen.TIPO_RUTA, Almacen.TIPO_INSIDENCIAS]).order_by('nombre')
    serializer_class = AlmacenMiniSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    filter_backends = [MinimalSearchFilter]

    search_fields = ['codigo', 'nombre', 'id']

    @property
    def is_cedis(self):
        """
        Propiedad para obtener el valor de 'is_cedis' desde los query params.
        Devuelve True, False o None.
        """
        value = self.request.query_params.get('is_cedis')
        if value is not None:
            if value.lower() in ['1', 'true', 'yes']:
                return True
            elif value.lower() in ['0', 'false', 'no']:
                return False
        return None

    def get_queryset(self):
        queryset = super().get_queryset().exclude(status_model=BaseModel.STATUS_MODEL_DELETE)
        is_cedis = self.is_cedis
        if is_cedis is not None:
            queryset = queryset.filter(is_cedis=is_cedis)
        return queryset
"""
============================================================================================
                            VIEWS DE APIS DE SUCURSALES
============================================================================================
                            VIEWS DE APIS DE SUCURSALES
"""
class SucursalViewSet(viewsets.ModelViewSet):
    queryset = Sucursal.objects.all()
    serializer_class = SucursalSerializer
    permission_classes = [IsAuthenticated, SucursalPermission]
    filter_backends = [MinimalSearchFilter]
    search_fields = ['codigo', 'nombre', 'id', 'empresa__nombre', 'almacen__nombre', 'encargado__full_name']

    def list (self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset().exclude(status_model=BaseModel.STATUS_MODEL_DELETE))
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if self.is_respuesta_404():
            return self.respuesta_404()

        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
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
        instance.status_model = BaseModel.STATUS_MODEL_DELETE
        instance.save(update_fields=['status_model'])
        return Response({"detail": "Eliminado correctamente."}, status=status.HTTP_200_OK)
    
    def is_respuesta_404(self):
        instance = self.get_object()
        return instance.status_model == BaseModel.STATUS_MODEL_DELETE

    def respuesta_404(self):
        return Response({"detail": "No encontrado."}, status=status.HTTP_404_NOT_FOUND) 

class SucursalMiniViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Sucursal.objects.all().filter(status_model=BaseModel.STATUS_MODEL_ACTIVE).order_by('-id')
    serializer_class = SucursalMiniSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [MinimalSearchFilter]
    search_fields = ['codigo', 'nombre', 'id', 'empresa__nombre', 'almacen__nombre', 'encargado__nombre']
    pagination_class = None

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset().exclude(status_model=BaseModel.STATUS_MODEL_DELETE))
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


"""
============================================================================================
                            VIEWS DE APIS DE ÓRDENES DE COMPRA
============================================================================================
"""
class OrdenCompraViewSet(viewsets.ModelViewSet):
    """
    ViewSet completo para CRUD de órdenes de compra
    """
    queryset = OrdenCompra.objects.all().exclude(status_model=BaseModel.STATUS_MODEL_DELETE).order_by('-id').select_related('proveedor', 'encargado')

    serializer_class = OrdenCompraSerializer
    permission_classes = [IsAuthenticated , OrdenCompraPermission]
    
    #permission_classes = [permissions.IsAuthenticated]
    filter_backends = [MinimalSearchFilter]
    search_fields = ['codigo', 'id', 'proveedor__nombre', 'proveedor__codigo','encargado__nombre']

    
   
    def get_serializer_class(self):
        """
        Usar diferentes serializers según la acción
        """
        if self.action == 'update_estado':
            return OrdenCompraEstadoSerializer
        elif self.action == 'list':
            return OrdenCompraMiniSerializer
        return OrdenCompraSerializer

    @extend_schema(
    summary="Listar órdenes de compra",
    parameters=[
        OpenApiParameter(
            name='estado',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Filtrar órdenes por estado específico',
            required=False,
            enum=[OrdenCompra.SOLICITUD, OrdenCompra.PENDIENTE, OrdenCompra.EN_PROCESO, OrdenCompra.FINALIZADA, OrdenCompra.CANCELADA],
            examples=[
                OpenApiExample('Solo solicitudes', value=OrdenCompra.SOLICITUD),
                OpenApiExample('Solo pendientes', value=OrdenCompra.PENDIENTE),
                OpenApiExample('Solo en proceso', value=OrdenCompra.EN_PROCESO),
                OpenApiExample('Solo finalizadas', value=OrdenCompra.FINALIZADA),
                OpenApiExample('Solo canceladas', value=OrdenCompra.CANCELADA),
            ]
        ),
        OpenApiParameter(
            name='proveedor_id',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='ID del proveedor para filtrar sus órdenes',
            required=False,
            examples=[
                OpenApiExample('Proveedor específico', value=123),
                OpenApiExample('Otro proveedor', value=456),
            ]
        ),
        OpenApiParameter(
            name='proveedor_name',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Búsqueda parcial por nombre del proveedor (insensible a mayúsculas)',
            required=False,
            examples=[
                OpenApiExample('Por nombre parcial', value='COCA'),
                OpenApiExample('Por empresa', value='DISTRIBUIDORA'),
            ]
        ),
        OpenApiParameter(
            name='search',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Búsqueda global en código de orden, nombre del proveedor, código del proveedor y nombre del encargado',
            required=False,
            examples=[
                OpenApiExample('Por código de orden', value='ORD-001'),
                OpenApiExample('Por nombre encargado', value='Juan'),
                OpenApiExample('Por código proveedor', value='PROV-123'),
            ]
        ),
        OpenApiParameter(
            name='ordering',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Campo por el cual ordenar los resultados. Usar "-" para orden descendente',
            required=False,
            enum=['-id', 'id', '-created_at', 'created_at', '-total', 'total', '-estado', 'estado'],
            examples=[
                OpenApiExample('Más recientes primero', value='-created_at'),
                OpenApiExample('Menor a mayor total', value='total'),
                OpenApiExample('Por estado A-Z', value='estado'),
            ]
        ),
        OpenApiParameter(
            name='page',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='Número de página para paginación',
            required=False,
            examples=[
                OpenApiExample('Primera página', value=1),
                OpenApiExample('Segunda página', value=2),
            ]
        ),
        OpenApiParameter(
            name='page_size',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='Cantidad de elementos por página (máximo 100)',
            required=False,
            examples=[
                OpenApiExample('10 elementos', value=10),
                OpenApiExample('25 elementos', value=25),
                OpenApiExample('50 elementos', value=50),
            ]
        ),
    ],
    responses={
        200: OrdenCompraMiniSerializer(many=True)
    },
    tags=['Órdenes de Compra']
)
    def list(self, request, *args, **kwargs):
        
        """
        Listar órdenes de compra con filtros adicionales
        """
        queryset = self.filter_queryset(self.get_queryset())
       
        if not request.user.is_superuser:
            queryset = queryset.filter(encargado_id=request.user.id)
           

        # Filtros adicionales
        estado = request.query_params.get('estado', None)
        proveedor_id = request.query_params.get('proveedor_id', None)
        proveedor_name = request.query_params.get('proveedor_name', None)
        
        if estado:
            queryset = queryset.filter(estado=estado)
        
        if proveedor_id:
            queryset = queryset.filter(proveedor_id=proveedor_id)
        if proveedor_name:
            queryset = queryset.filter(proveedor__nombre__icontains=proveedor_name)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    

    def retrieve(self, request, *args, **kwargs):
        """
        Obtener una orden de compra específica
        """
        instance = self.get_object()
        if self.is_respuesta_404():
            return self.respuesta_404()

        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        """
        Crear nueva orden de compra
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """
        Actualizar orden de compra completa
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        if self.is_respuesta_404():
            return self.respuesta_404()
        
        # No permitir editar órdenes finalizadas o canceladas
        if instance.estado in [OrdenCompra.FINALIZADA, OrdenCompra.CANCELADA, OrdenCompra.EN_PROCESO]:
            return Response(
                {"detail": f"No se puede editar una orden de compra {instance.estado.lower()}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=['patch'],
        url_path='estado'
    )
    @extend_schema(
        request=OrdenCompraEstadoSerializer,
        responses={200: OrdenCompraEstadoSerializer}
    )
    def update_estado(self, request, pk=None):
        """
        Actualizar solo el estado de una orden de compra
        """
        instance = self.get_object()
        
        if self.is_respuesta_404():
            return self.respuesta_404()
        
        serializer = OrdenCompraEstadoSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        """
        Eliminar orden de compra (soft delete)
        """
        instance = self.get_object()
        
        if self.is_respuesta_404():
            return self.respuesta_404()
        
        # No permitir eliminar órdenes finalizadas
        if instance.estado == OrdenCompra.FINALIZADA:
            return Response(
                {"detail": "No se puede eliminar una orden de compra finalizada."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        instance.status_model = BaseModel.STATUS_MODEL_DELETE
        instance.save(update_fields=['status_model'])
        return Response(
            {"detail": "La orden de compra ha sido eliminada."},
            status=status.HTTP_200_OK
        )

    def is_respuesta_404(self):
        """
        Verificar si la instancia está eliminada
        """
        instance = self.get_object()
        return instance.status_model == BaseModel.STATUS_MODEL_DELETE

    def respuesta_404(self):
        """
        Respuesta 404 estándar
        """
        return Response(
            {"detail": "No encontrado."},
            status=status.HTTP_404_NOT_FOUND
        )


class OrdenCompraMiniViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    ViewSet para listar órdenes de compra de forma resumida
    """
    queryset = OrdenCompra.objects.all().exclude(status_model=BaseModel.STATUS_MODEL_DELETE).order_by('-id').select_related('encargado','proveedor')
    serializer_class = OrdenCompraMiniSerializer
    #permission_classes = [permissions.IsAuthenticated]
    permission_classes = [IsAuthenticated ]
    
    filter_backends = [MinimalSearchFilter]
    search_fields = ['codigo', 'id', 'proveedor__nombre', 'proveedor__codigo', 'encargado__nombre']
    pagination_class = None



    @extend_schema(
    parameters=[
        OpenApiParameter(
            name='estado',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Filtrar órdenes por estado específico',
            required=False,
            enum=[OrdenCompra.SOLICITUD, OrdenCompra.EN_PROCESO, OrdenCompra.FINALIZADA, OrdenCompra.CANCELADA],
            examples=[
                OpenApiExample('Solo solicitudes', value=OrdenCompra.SOLICITUD),
                #OpenApiExample('Solo pendientes', value=OrdenCompra.PENDIENTE),
                OpenApiExample('Solo en proceso', value=OrdenCompra.EN_PROCESO),
                OpenApiExample('Solo finalizadas', value=OrdenCompra.FINALIZADA),
                OpenApiExample('Solo canceladas', value=OrdenCompra.CANCELADA),
            ]
        ),
        OpenApiParameter(
            name='proveedor_id',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='ID del proveedor para filtrar sus órdenes',
            required=False,
            examples=[
                OpenApiExample('Proveedor específico', value=123),
                OpenApiExample('Otro proveedor', value=456),
            ]
        ),
        OpenApiParameter(
            name='search',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Búsqueda en código de orden, nombre del proveedor, código del proveedor y nombre del encargado',
            required=False,
            examples=[
                OpenApiExample('Por código de orden', value='ORD-001'),
                OpenApiExample('Por nombre proveedor', value='COCA COLA'),
                OpenApiExample('Por código proveedor', value='PROV-123'),
                OpenApiExample('Por nombre encargado', value='Juan'),
            ]
        ),
    ],
    responses={
        200: OrdenCompraMiniSerializer(many=True),
        400: inline_serializer(
            name='OrdenCompraMiniListError',
            fields={
                'detail': serializers.CharField(
                    default='Error en los parámetros de filtrado'
                )
            }
        )
        
    },
    tags=['Órdenes de Compra - Mini']
)
    def list(self, request, *args, **kwargs):
        """
        Listar órdenes de compra mini con filtros
        """
        queryset = self.filter_queryset(self.get_queryset())
        #print(f"[DEBUG MINI LIST] Queryset final count: {queryset.count()}")
        if request.user and not request.user.is_superuser:
            queryset = queryset.filter(encargado=request.user.id)

        # Filtros adicionales
        estado = request.query_params.get('estado', None)
        if estado:
            queryset = queryset.filter(estado=estado)
        prooveedor_id = request.query_params.get('proveedor_id', None)
        if prooveedor_id:
            try:
                queryset = queryset.filter(proveedor_id=int(prooveedor_id))
            except (ValueError, TypeError):
                pass
        
        serializer = self.get_serializer(queryset, many=True)
        #print(f"[DEBUG MINI LIST] Registros serializados: {len(serializer.data)}")
        return Response(serializer.data, status=status.HTTP_200_OK)
   

class OrdenCompraCompletaListView(ListAPIView):
    """
    Vista para listar órdenes de compra completas con paginación automática
    """
    serializer_class = OrdenCompraSerializer
    #permission_classes = [permissions.IsAuthenticated]
    permission_classes = [IsAuthenticated , OrdenCompraPermission]
    
    filter_backends = [MinimalSearchFilter, filters.OrderingFilter]
    search_fields = ['codigo', 'id', 'proveedor__nombre', 'proveedor__codigo','encargado__nombre']
    ordering_fields = ['id', 'created_at']
    ordering = ['-id']
    
    def get_queryset(self):
        """Obtener queryset con filtros personalizados"""
        queryset = OrdenCompra.objects.all().exclude(
            status_model=BaseModel.STATUS_MODEL_DELETE
        ).select_related('proveedor', 'encargado')
        
        if self.request.user and not self.request.user.is_superuser:
            queryset = queryset.filter(encargado=self.request.user.id)

        # Filtros personalizados
        estado = self.request.query_params.get('estado', None)
        if estado:
            queryset = queryset.filter(estado=estado)
        
        proveedor_id = self.request.query_params.get('proveedor_id', None)
        if proveedor_id:
            try:
                queryset = queryset.filter(proveedor_id=int(proveedor_id))
            except (ValueError, TypeError):
                pass  # Ignorar valores inválidos
        
        return queryset

    @extend_schema(
        summary="Listar órdenes de compra completas",
        description="Obtiene una lista paginada de órdenes de compra con información detallada",
        parameters=[
            OpenApiParameter(
                name='estado',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Filtrar por estado',
                required=False,
            ),
            OpenApiParameter(
                name='proveedor_id',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Filtrar por proveedor',
                required=False,
            ),
            OpenApiParameter(
                name='page',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Número de página',
                required=False,
            ),
        ],
        responses={200: OrdenCompraSerializer(many=True)},
        tags=['Órdenes de Compra']
    )
    def get(self, request, *args, **kwargs):
        """Listar órdenes con paginación automática"""
        return super().get(request, *args, **kwargs)


"""
============================================================================================
                            VIEWS DE APIS DE COMPRA
============================================================================================
"""

class CompraViewSet(viewsets.ModelViewSet):
    """
    ViewSet para CRUD completo de compras
    """
    queryset = Compra.objects.all()
    serializer_class = CompraSerializer
    permission_classes = [IsAuthenticated , CompraPermission]
    
    filter_backends = [MinimalSearchFilter, filters.OrderingFilter]
    search_fields = ['codigo', 'proveedor__nombre', 'proveedor__codigo', 'orden_compra__codigo']
    ordering_fields = ['created_at', 'fecha_salida', 'total', 'estado']
    ordering = ['-created_at']



    def get_queryset(self):
        """
        Optimizar consultas con select_related y prefetch_related
        """
        return (
            Compra.objects
            .select_related('proveedor', 'almacen_destino', 'almacen_virtual', 'orden_compra')
            .prefetch_related(
                'detalles__producto',
                'pagos__metodo_pago'
            )
            .exclude(status_model=BaseModel.STATUS_MODEL_DELETE)
        )


    @extend_schema(
    #summary="Listar compras",    
    parameters=[
        OpenApiParameter(
            name='estado',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Filtrar compras por estado específico',
            required=False,
            enum=[Compra.PROCESANDO, Compra.FINALIZADA, Compra.EN_CAMINO, Compra.CANCELED],
            examples=[
                OpenApiExample('Solo en procesamiento', value=Compra.PROCESANDO),
                OpenApiExample('Solo en camino', value=Compra.EN_CAMINO),
                OpenApiExample('Solo en Finalizada', value=Compra.FINALIZADA),
                OpenApiExample('Solo en Cancelada', value=Compra.CANCELED),
            ]
        ),
        OpenApiParameter(
            name='proveedor',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='ID del proveedor para filtrar sus compras',
            required=False,
            examples=[
                OpenApiExample('Proveedor específico', value=123),
                OpenApiExample('Otro proveedor', value=456),
            ]
        ),
        OpenApiParameter(
            name='almacen',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='ID del almacén destino para filtrar compras',
            required=False,
            examples=[
                OpenApiExample('Almacén principal', value=1),
                OpenApiExample('Almacén secundario', value=2),
            ]
        ),
        OpenApiParameter(
            name='search',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Búsqueda global en código de compra, nombre del proveedor, código del proveedor y código de orden de compra',
            required=False,
            examples=[
                OpenApiExample('Por código de compra', value='COMP-001'),
                OpenApiExample('Por nombre proveedor', value='COCA COLA'),
                OpenApiExample('Por código de orden', value='ORD-123'),
            ]
        ),
        ],
    responses={
        200: CompraSerializer(many=True),
    },
        #tags=['Compras']
    )
    def list(self, request, *args, **kwargs):
        """
        Listar compras con filtros avanzados
        """
        queryset = self.filter_queryset(self.get_queryset())

        #if request.user and not request.user.is_superuser:
        #    queryset = queryset.filter(created_by_id=request.user.id)
        
        # Filtros adicionales por query parameters
        estado = request.query_params.get('estado', None)
        if estado:
            queryset = queryset.filter(estado=estado)
            #print(f"[DEBUG LIST] Filtrado por estado: {estado}")
        
        proveedor_id = request.query_params.get('proveedor', None)
        if proveedor_id:
            try:
                queryset = queryset.filter(proveedor_id=int(proveedor_id))
            except (ValueError, TypeError):
                pass
        
        almacen_id = request.query_params.get('almacen', None)
        if almacen_id:
            try:
                queryset = queryset.filter(almacen_destino_id=int(almacen_id))
            except (ValueError, TypeError):
                pass
        
        fecha_desde = request.query_params.get('fecha_desde', None)
        if fecha_desde:
            queryset = queryset.filter(fecha_salida__gte=fecha_desde)
        
        fecha_hasta = request.query_params.get('fecha_hasta', None)
        if fecha_hasta:
            queryset = queryset.filter(fecha_salida__lte=fecha_hasta)
        
        

       
        
        # Paginación
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        """
        Obtener una compra específica
        """
        instance = self.get_object()
        if instance.status_model == BaseModel.STATUS_MODEL_DELETE:
            return Response(
                {'detail': 'La compra no existe o ha sido eliminada'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        """
        Crear nueva compra
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )

    def update(self, request, *args, **kwargs):
        """
        Actualizar compra completa
        """
        instance = self.get_object()
        
        # Validar que la compra no esté en estado final
        if instance.estado in [Compra.ALMACEN, Compra.CANCELED, Compra.FINALIZADA, Compra.EN_CAMINO]:
            return Response(
                {'detail': 'No se puede modificar una compra que ya está en almacén o finalizada o cancelada o en camino. Estado de la compra: ' + instance.estado},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    def destroy(self, request, *args, **kwargs):
        """
        Eliminación lógica de compra
        """
        instance = self.get_object()
        
        # Validar que la compra se pueda eliminar
        if instance.estado == Compra.ALMACEN:
            return Response(
                {'error': 'No se puede eliminar una compra que ya está en almacén'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Soft delete
        instance.status_model = BaseModel.STATUS_MODEL_DELETE
        instance.save(update_fields=['status_model'])
        
        return Response(
            {'detail': 'Compra eliminada exitosamente'},
            status=status.HTTP_200_OK
        )

    @extend_schema(
        #summary="Cambiar estado de una compra",
        request=CompraEstadoSerializer,
        responses={200: CompraSerializer}
    )
    @action(detail=True, methods=['patch'], url_path='estado')
    def cambiar_estado(self, request, pk=None):
        """
        Cambiar el estado de una compra específica
        """
        instance = self.get_object()
        serializer = CompraEstadoSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        # Retornar la compra actualizada
        response_serializer = self.get_serializer(instance)
        return Response(
            {
                'message': f'Estado cambiado a {instance.estado} exitosamente',
                'data': response_serializer.data
            },
            status=status.HTTP_200_OK
        )

   

class CompraMiniViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    ViewSet para listar compras básicas (solo lectura)
    """
    queryset = Compra.objects.all()
    serializer_class = CompraMiniSerializer
    permission_classes = [IsAuthenticated]

    filter_backends = [MinimalSearchFilter, filters.OrderingFilter]
    search_fields = ['codigo', 'proveedor__nombre', 'almacen_destino__nombre']
    ordering_fields = ['created_at', 'fecha_salida', 'total']
    ordering = ['-created_at']
    pagination_class = None

    def get_queryset(self):
        """
        Optimizar consultas para lista básica
        """
        return (
            Compra.objects
            .select_related('proveedor', 'almacen_destino', 'orden_compra')
            .exclude(status_model=BaseModel.STATUS_MODEL_DELETE)
        )
    

    @extend_schema(
    parameters=[
        OpenApiParameter(
            name='estado',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Filtrar compras por estado específico',
            required=False,
            enum=[Compra.PROCESANDO, Compra.EN_CAMINO,  Compra.CANCELED, Compra.FINALIZADA],
            examples=[
                OpenApiExample('Solo en procesamiento', value=Compra.PROCESANDO),
                OpenApiExample('Solo en camino', value=Compra.EN_CAMINO),
                OpenApiExample('Solo canceladas', value=Compra.CANCELED),
                OpenApiExample('Solo finalizadas', value=Compra.FINALIZADA),
            ]
        ),
        OpenApiParameter(
            name='proveedor',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='ID del proveedor para filtrar sus compras',
            required=False,
            examples=[
                OpenApiExample('ID Proveedor específico', value=123),
                OpenApiExample(' ID Otro proveedor', value=456),
            ]
        ),
        OpenApiParameter(
            name='search',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Búsqueda en código de compra, nombre del proveedor y nombre del almacén destino',
            required=False,
            examples=[
                OpenApiExample('Por código de compra', value='COMP-001'),
                OpenApiExample('Por nombre proveedor', value='TIBURON BLANCO'),
                OpenApiExample('Por almacén', value='PRINCIPAL'),
            ]
        ),
        OpenApiParameter(
            name='ordering',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Campo por el cual ordenar los resultados. Usar "-" para orden descendente',
            required=False,
            enum=['-created_at', 'created_at', '-fecha_salida', 'fecha_salida', '-total', 'total'],
            examples=[
                OpenApiExample('Más recientes primero', value='-created_at'),
                OpenApiExample('Por fecha de salida', value='-fecha_salida'),
                OpenApiExample('Por total menor a mayor', value='total'),
            ]
        ),
    ],
    responses={
        200: CompraMiniSerializer(many=True),
        400: inline_serializer(
            name='CompraMiniListError',
            fields={
                'detail': serializers.CharField(
                    default='Error en los parámetros de filtrado'
                )
            }
        ),
        401: inline_serializer(
            name='Unauthorized',
            fields={
                'detail': serializers.CharField(
                    default='Credenciales de autenticación no fueron proporcionadas.'
                )
            }
        )
    },
    #tags=['Compras - Mini']
    )
    def list(self, request, *args, **kwargs):
        """
        Listar compras básicas con filtros
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Filtros adicionales
        estado = request.query_params.get('estado', None)
        if estado:
            queryset = queryset.filter(estado=estado)
        
        proveedor_id = request.query_params.get('proveedor', None)
        if proveedor_id:
            try:
                queryset = queryset.filter(proveedor_id=int(proveedor_id))
            except (ValueError, TypeError):
                pass

        if request.user and not request.user.is_superuser:
            queryset = queryset.filter(created_by_id=request.user.id)

         # Paginación
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


"""
============================================================================================
                            VIEWS DE APIS DE RUTAS
============================================================================================
"""
class RutasViewSet(viewsets.ModelViewSet):
    """
    ViewSet completo para CRUD de rutas
    """
    queryset = Rutas.objects.all().exclude(status_model=BaseModel.STATUS_MODEL_DELETE).order_by('-id').select_related('asignado', 'almacen')
    serializer_class = RutasSerializer
    permission_classes = [IsAuthenticated, RutasPermission]
    filter_backends = [MinimalSearchFilter, filters.OrderingFilter]
    search_fields = ['codigo', 'nombre', 'origen', 'destino', 'unidad', 'asignado__full_name', 'almacen__nombre']
    ordering_fields = ['created_at', 'nombre', 'origen', 'destino']
    ordering = ['-created_at']

    def get_serializer_class(self):
        """
        Retorna el serializer apropiado según la acción
        """
        if self.action == 'estado':
            return RutasEstadoSerializer
        return self.serializer_class

    def list(self, request, *args, **kwargs):
        """
        Listar rutas con filtros opcionales
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Filtros adicionales
        asignado_id = request.query_params.get('asignado', None)
        if asignado_id:
            try:
                queryset = queryset.filter(asignado_id=int(asignado_id))
            except (ValueError, TypeError):
                pass
        
        # Filtro por estado (activo/inactivo)
        activo = request.query_params.get('activo', None)
        if activo is not None:
            if activo.lower() in ['true', '1']:
                queryset = queryset.filter(status_model=BaseModel.STATUS_MODEL_ACTIVE)
            elif activo.lower() in ['false', '0']:
                queryset = queryset.filter(status_model=BaseModel.STATUS_MODEL_INACTIVE)

        # Paginación
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        """
        Obtener una ruta específica por ID
        """
        instance = self.get_object()
        if self.is_respuesta_404():
            return self.respuesta_404()

        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        """
        Crear nueva ruta (el almacén se crea automáticamente)
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # El signal creará automáticamente el almacén
        instance = serializer.save()
        
        # Retornar la ruta con su almacén recién creado
        response_serializer = self.get_serializer(instance)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """
        Actualizar ruta (parcial o completa)
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        if self.is_respuesta_404():
            return self.respuesta_404()

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        
        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        """
        Eliminación lógica de ruta
        """
        instance = self.get_object()
        if self.is_respuesta_404():
            return self.respuesta_404()
        
        # Eliminación lógica
        instance.status_model = BaseModel.STATUS_MODEL_DELETE
        instance.save(update_fields=['status_model'])
        
        return Response(
            {"detail": "Ruta eliminada correctamente."},
            status=status.HTTP_200_OK
        )

    def is_respuesta_404(self):
        """
        Verificar si la ruta está eliminada lógicamente
        """
        instance = self.get_object()
        return instance.status_model == BaseModel.STATUS_MODEL_DELETE

    def respuesta_404(self):
        """
        Respuesta estándar para recursos no encontrados
        """
        return Response(
            {"detail": "Ruta no encontrada."},
            status=status.HTTP_404_NOT_FOUND
        )

        """
        Obtener estadísticas generales de rutas
        """
        queryset = self.get_queryset()
        
        stats = {
            'total_rutas': queryset.count(),
            'rutas_activas': queryset.filter(status_model=BaseModel.STATUS_MODEL_ACTIVE).count(),
            'rutas_asignadas': queryset.filter(asignado__isnull=False).count(),
            'rutas_sin_asignar': queryset.filter(asignado__isnull=True).count(),
            'distribución_por_unidad': {}
        }
        
        # Distribución por tipo de unidad
        unidades = queryset.values_list('unidad', flat=True).distinct()
        for unidad in unidades:
            if unidad:
                stats['distribución_por_unidad'][unidad] = queryset.filter(unidad=unidad).count()
        
        return Response(stats, status=status.HTTP_200_OK)


class RutasMiniViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    ViewSet para listar rutas de forma resumida
    """
    queryset = Rutas.objects.all().exclude(status_model=BaseModel.STATUS_MODEL_DELETE).order_by('-id').select_related('asignado', 'almacen')
    serializer_class = RutasMiniSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [MinimalSearchFilter]
    search_fields = ['codigo', 'nombre', 'origen', 'destino', 'asignado__full_name']
    pagination_class = None

    def list(self, request, *args, **kwargs):
        """
        Listar rutas básicas con filtros
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Filtros adicionales
        activo = request.query_params.get('activo', None)
        if activo is not None:
            if activo.lower() in ['true', '1']:
                queryset = queryset.filter(status_model=BaseModel.STATUS_MODEL_ACTIVE)
            elif activo.lower() in ['false', '0']:
                queryset = queryset.filter(status_model=BaseModel.STATUS_MODEL_INACTIVE)
        
        asignado = request.query_params.get('asignado', None)
        if asignado is not None:
            if asignado.lower() in ['true', '1']:
                queryset = queryset.filter(asignado__isnull=False)
            elif asignado.lower() in ['false', '0']:
                queryset = queryset.filter(asignado__isnull=True)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)