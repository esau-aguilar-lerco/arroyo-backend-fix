from django.db import models
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.base.models import BaseModel
from apps.erp.models import Almacen
from apps.inventario.models import LoteInventario
from apps.inventario.serializers.inventario.inventarioAlmacen import (
    InventarioAlmacenViewSerializer,
    #InventarioProductoViewSerializer
)



class InventarioTodosAlmacenesView(APIView):
    """
    Vista para consultar inventario de todos los almacenes FIJOS activos.
    
    Retorna TODOS los almacenes fijos (tipo=FIJO, is_cedis=False), incluso aquellos 
    sin inventario del producto buscado. Los almacenes sin inventario tendrán 
    un array vacío en 'productos'.
    
    Los productos dentro de cada almacén están ordenados por cantidad descendente 
    (mayor cantidad primero).
    
    Requiere obligatoriamente: producto_id O search
    """
    
    @extend_schema(
        summary="Consultar inventario en todos los almacenes fijos",
        description="""
        Obtiene el inventario de **todos los almacenes fijos activos** del sistema.
        
        **Características:**
        - Incluye TODOS los almacenes fijos, incluso sin inventario
        - Solo almacenes tipo FIJO (excluye CEDIS)
        - Productos ordenados por cantidad descendente dentro de cada almacén
        - Requiere filtro obligatorio para optimizar rendimiento
        
        **Parámetros obligatorios:**
        Debe proporcionar al menos uno:
        - `producto_id`: Para buscar un producto específico
        - `search`: Para buscar productos por nombre o código
        
        **Respuesta incluye:**
        - `total_almacenes`: Total de almacenes fijos en el sistema
        - `almacenes_con_inventario`: Almacenes que tienen el producto buscado
        - `almacenes_sin_inventario`: Almacenes sin el producto buscado
        - `data`: Array de almacenes con sus productos
        
        **Ejemplos de uso:**
        - `?producto_id=123` - Buscar producto con ID 123 en todos los almacenes
        - `?search=harina` - Buscar productos que contengan "harina"
        - `?search=HAR-001` - Buscar por código de producto
        """,
        parameters=[
            OpenApiParameter(
                name='producto_id',
                type=int,
                location=OpenApiParameter.QUERY,
                description='ID del producto para filtrar inventario. Ejemplo: 123',
                required=False
            ),
            OpenApiParameter(
                name='search',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Búsqueda por nombre o código del producto (case-insensitive). Ejemplo: "harina" o "HAR-001"',
                required=False
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=InventarioAlmacenViewSerializer(many=True),
                description='Inventario consultado exitosamente. Retorna todos los almacenes fijos con sus productos.'
            ),
            400: OpenApiResponse(
                description='Parámetros inválidos. Debe proporcionar producto_id o search.'
            ),
            401: OpenApiResponse(
                description='No autenticado. Token JWT requerido.'
            ),
            403: OpenApiResponse(
                description='No autorizado. Sin permisos para consultar inventario.'
            ),
        },
        tags=['Inventario - Consultas']
    )
    def get(self, request):
        """
        Obtiene el inventario de todos los almacenes FIJOS activos.
        
        - Trae TODOS los almacenes fijos (incluso si no tienen inventario)
        - Filtra por producto_id o búsqueda (obligatorio)
        - Agrupa por almacén y producto
        - Suma cantidades totales
        - Ordena por cantidad descendente dentro de cada almacén
        """
        # Validar parámetros obligatorios
        producto_id = request.query_params.get('producto_id')
        search = request.query_params.get('search')
        
        if not producto_id and not search:
            return Response(
                {
                    "success": False,
                    "message": "Debe proporcionar 'producto_id' o 'search' para optimizar la consulta",
                    "errors": {
                        "producto_id": "Requerido si no se proporciona 'search'",
                        "search": "Requerido si no se proporciona 'producto_id'"
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 1. Obtener TODOS los almacenes fijos activos
        almacenes_fijos = Almacen.objects.filter(
            status_model=BaseModel.STATUS_MODEL_ACTIVE,
            tipo=Almacen.TIPO_FIJO,
            #is_cedis=False
        ).select_related('encargado')
        
        # 2. Inicializar diccionario con todos los almacenes fijos
        almacenes_dict = {}
        for almacen in almacenes_fijos:
            encargado_nombre = ''
            if almacen.encargado:
                encargado_nombre = almacen.encargado.full_name()
            
            almacenes_dict[almacen.id] = {
                'almacen_id': almacen.id,
                'almacen_nombre': almacen.nombre,
                'encargado_nombre': encargado_nombre,
                'productos': []
            }
        
        # 3. Construir queryset de inventario optimizado
        lotes_queryset = LoteInventario.objects.filter(
            cantidad__gt=0,
            status_model=BaseModel.STATUS_MODEL_ACTIVE,
            almacen__status_model=BaseModel.STATUS_MODEL_ACTIVE,
            almacen__tipo=Almacen.TIPO_FIJO,
            #almacen__is_cedis=False
        ).select_related(
            'producto',
            'producto__unidad_sat',
            'almacen'
        )
        
        # 4. Aplicar filtros de producto
        if producto_id:
            try:
                producto_id = int(producto_id)
                lotes_queryset = lotes_queryset.filter(producto_id=producto_id)
            except (ValueError, TypeError):
                return Response(
                    {
                        "success": False,
                        "message": "El parámetro 'producto_id' debe ser un número entero válido"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
        elif search:
            lotes_queryset = lotes_queryset.filter(
                models.Q(producto__nombre__icontains=search) |
                models.Q(producto__codigo__icontains=search)
            )
        
        # 5. Agrupar por almacén y producto, sumar cantidades (optimizado en SQL)
        inventario_agrupado = lotes_queryset.values(
            'almacen_id',
            'producto_id',
            'producto__nombre',
            'producto__codigo',
            'producto__unidad_sat__nombre',
            'producto__unidad_sat__clave'
        ).annotate(
            cantidad_disponible=models.Sum('cantidad')
        ).order_by('almacen_id', '-cantidad_disponible')  # Por almacén, luego mayor cantidad
        
        # 6. Agregar productos al almacén correspondiente
        for item in inventario_agrupado:
            almacen_id = item['almacen_id']
            
            # Solo agregar si el almacén está en nuestro diccionario (almacenes fijos)
            if almacen_id in almacenes_dict:
                almacenes_dict[almacen_id]['productos'].append({
                    'producto_id': item['producto_id'],
                    'producto_nombre': item['producto__nombre'],
                    'producto_clave': item['producto__codigo'] or '',
                    'producto_unidad': item['producto__unidad_sat__nombre'] or '',
                    'producto_unidad_clave': item['producto__unidad_sat__clave'] or '',
                    'cantidad_disponible': int(item['cantidad_disponible'])
                })
        
        # 7. Convertir a lista (incluye almacenes sin productos)
        almacenes_list = list(almacenes_dict.values())
        
        serializer = InventarioAlmacenViewSerializer(almacenes_list, many=True)
        
        return Response(
            {
                "success": True,
                "total_almacenes": len(almacenes_list),
                "almacenes_con_inventario": sum(1 for a in almacenes_list if a['productos']),
                "almacenes_sin_inventario": sum(1 for a in almacenes_list if not a['productos']),
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )


class InventarioAlmacenView(APIView):
    """
    Vista para consultar inventario de un almacén específico.
    Ordenado por cantidad descendente.
    Requiere obligatoriamente: producto_id O search
    """
    
    @extend_schema(
        summary="Consultar inventario de un almacén específico",
        description="""
        Obtiene el inventario de un almacén específico por su ID.
        
        **Características:**
        - Consulta un solo almacén
        - Productos ordenados por cantidad descendente
        - Requiere filtro obligatorio para optimizar rendimiento
        
        **Parámetros obligatorios:**
        Debe proporcionar al menos uno:
        - `producto_id`: Para buscar un producto específico
        - `search`: Para buscar productos por nombre o código
        
        **Ejemplos de uso:**
        - `/inventario-almacen/5/?producto_id=123`
        - `/inventario-almacen/5/?search=harina`
        """,
        parameters=[
            OpenApiParameter(
                name='producto_id',
                type=int,
                location=OpenApiParameter.QUERY,
                description='ID del producto para filtrar inventario. Ejemplo: 123',
                required=False
            ),
            OpenApiParameter(
                name='search',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Búsqueda por nombre o código del producto. Ejemplo: "harina"',
                required=False
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=InventarioAlmacenViewSerializer,
                description='Inventario consultado exitosamente.'
            ),
            400: OpenApiResponse(
                description='Parámetros inválidos o almacén no encontrado.'
            ),
            404: OpenApiResponse(
                description='Almacén no encontrado.'
            ),
        },
        tags=['Inventario - Consultas']
    )
    def get(self, request, almacen_id):
        """
        Obtiene el inventario de un almacén específico.
        """
        # Validar parámetros obligatorios
        producto_id = request.query_params.get('producto_id')
        search = request.query_params.get('search')
        
        if not producto_id and not search:
            return Response(
                {
                    "success": False,
                    "message": "Debe proporcionar 'producto_id' o 'search' para optimizar la consulta",
                    "errors": {
                        "producto_id": "Requerido si no se proporciona 'search'",
                        "search": "Requerido si no se proporciona 'producto_id'"
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar que el almacén existe
        try:
            almacen = Almacen.objects.get(
                id=almacen_id, 
                status_model=BaseModel.STATUS_MODEL_ACTIVE
            )
        except Almacen.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "message": f"Almacén con ID {almacen_id} no encontrado"
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Construir queryset optimizado
        lotes_queryset = LoteInventario.objects.filter(
            almacen_id=almacen_id,
            cantidad__gt=0,
            status_model=BaseModel.STATUS_MODEL_ACTIVE
        ).select_related(
            'producto',
            'producto__unidad_sat'
        )
        
        # Aplicar filtros
        if producto_id:
            try:
                producto_id = int(producto_id)
                lotes_queryset = lotes_queryset.filter(producto_id=producto_id)
            except (ValueError, TypeError):
                return Response(
                    {
                        "success": False,
                        "message": "El parámetro 'producto_id' debe ser un número entero válido"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
        elif search:
            lotes_queryset = lotes_queryset.filter(
                models.Q(producto__nombre__icontains=search) |
                models.Q(producto__codigo__icontains=search)
            )
        
        # Agrupar por producto y sumar cantidades (optimizado en SQL)
        productos_agrupados = lotes_queryset.values(
            'producto_id',
            'producto__nombre',
            'producto__codigo',
            'producto__unidad_sat__nombre',
            'producto__unidad_sat__clave'
        ).annotate(
            cantidad_disponible=models.Sum('cantidad')
        ).order_by('-cantidad_disponible')  # Mayor cantidad primero
        
        # Formatear respuesta
        productos_list = [
            {
                'producto_id': item['producto_id'],
                'producto_nombre': item['producto__nombre'],
                'producto_clave': item['producto__codigo'] or '',
                'producto_unidad': item['producto__unidad_sat__nombre'] or '',
                'producto_unidad_clave': item['producto__unidad_sat__clave'] or '',
                'cantidad_disponible': int(item['cantidad_disponible'])
            }
            for item in productos_agrupados
        ]
        
        # Preparar data para serializer
        data = {
            'almacen_id': almacen.id,
            'almacen_nombre': almacen.nombre,
            'encargado_nombre': almacen.encargado.get_full_name() if almacen.encargado else '',
            'productos': productos_list
        }
        
        serializer = InventarioAlmacenViewSerializer(data)
        return Response(
            {
                "success": True,
                "total_productos": len(productos_list),
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )
