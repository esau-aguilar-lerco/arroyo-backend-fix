from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q, Count
from rest_framework import status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, inline_serializer
from rest_framework import serializers

from ..models import Usuario
from ..serializers.auth_serializer import (
    GroupSerializer, GroupMiniSerializer, PermissionSerializer, 
     ContentTypeSerializer
)


class GroupViewSet(ModelViewSet):
    """
    ViewSet para gestionar grupos de Django y asignar permisos
    
    Permite:
    - Listar todos los grupos del sistema
    - Crear nuevos grupos con permisos
    - Actualizar grupos existentes
    - Eliminar grupos
    - Asignar/remover permisos específicos
    - Asignar/remover usuarios
    """
    queryset = Group.objects.prefetch_related('permissions', 'user_set').all()
    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name', 'id']
    ordering = ['name']

    def get_serializer_class(self):
        """Usar serializer mini para listas"""
        if self.action == 'list':
            return GroupMiniSerializer
        return GroupSerializer

    def get_queryset(self):
        """Aplicar filtros personalizados"""
        queryset = super().get_queryset()
        
        # Filtrar por permisos específicos
        permission_id = self.request.query_params.get('permission')
        if permission_id:
            try:
                queryset = queryset.filter(permissions__id=int(permission_id))
            except (ValueError, TypeError):
                pass
        
        # Filtrar grupos con/sin usuarios
        has_users = self.request.query_params.get('has_users')
        if has_users == 'true':
            queryset = queryset.annotate(user_count=Count('user')).filter(user_count__gt=0)
        elif has_users == 'false':
            queryset = queryset.annotate(user_count=Count('user')).filter(user_count=0)
        
        return queryset

    @extend_schema(
        summary="Listar grupos",
        description="""
        Obtiene una lista de todos los grupos del sistema con filtros opcionales.
        
        **Filtros disponibles:**
        - `permission`: Filtrar grupos que tengan un permiso específico
        - `has_users`: Filtrar grupos con/sin usuarios (true/false)
        - `search`: Buscar por nombre del grupo
        """,
        parameters=[
            OpenApiParameter(
                name='permission',
                type=int,
                location=OpenApiParameter.QUERY,
                description='ID del permiso para filtrar grupos',
                required=False,
                examples=[
                    OpenApiExample('Permiso específico', value=123),
                ]
            ),
            OpenApiParameter(
                name='has_users',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Filtrar grupos con/sin usuarios',
                required=False,
                enum=['true', 'false'],
                examples=[
                    OpenApiExample('Solo con usuarios', value='true'),
                    OpenApiExample('Solo sin usuarios', value='false'),
                ]
            ),
            OpenApiParameter(
                name='search',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Buscar por nombre del grupo',
                required=False,
                examples=[
                    OpenApiExample('Buscar administradores', value='admin'),
                ]
            ),
        ],
        responses={200: GroupMiniSerializer(many=True)},
        tags=['Grupos y Permisos']
    )
    def list(self, request, *args, **kwargs):
        """Lista todos los grupos"""
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Crear grupo",
        description="Crea un nuevo grupo y opcionalmente asigna permisos",
        request=GroupSerializer,
        responses={
            201: GroupSerializer,
            400: inline_serializer(
                name='ValidationError',
                fields={'detail': serializers.CharField()}
            )
        },
        tags=['Grupos y Permisos']
    )
    def create(self, request, *args, **kwargs):
        """Crear un nuevo grupo"""
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Obtener detalles del grupo",
        description="Obtiene los detalles completos de un grupo específico",
        responses={
            200: GroupSerializer,
            404: inline_serializer(
                name='NotFound',
                fields={'detail': serializers.CharField()}
            )
        },
        tags=['Grupos y Permisos']
    )
    def retrieve(self, request, *args, **kwargs):
        """Obtener grupo específico"""
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Actualizar grupo",
        description="Actualiza un grupo y sus permisos asignados",
        request=GroupSerializer,
        responses={
            200: GroupSerializer,
            400: inline_serializer(
                name='ValidationError',
                fields={'detail': serializers.CharField()}
            ),
            404: inline_serializer(
                name='NotFound',
                fields={'detail': serializers.CharField()}
            )
        },
        tags=['Grupos y Permisos']
    )
    def update(self, request, *args, **kwargs):
        """Actualizar grupo completo"""
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary="Actualizar permisos del grupo",
        description="Actualiza solo los permisos asignados a un grupo",
        request=GroupSerializer,
        responses={
            200: GroupSerializer,
            400: inline_serializer(
                name='ValidationError',
                fields={'detail': serializers.CharField()}
            ),
            404: inline_serializer(
                name='NotFound',
                fields={'detail': serializers.CharField()}
            )
        },
        tags=['Grupos y Permisos']
    )
    def partial_update(self, request, *args, **kwargs):
        """Actualizar grupo parcialmente"""
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary="Eliminar grupo",
        description="Elimina un grupo del sistema",
        responses={
            204: None,
            404: inline_serializer(
                name='NotFound',
                fields={'detail': serializers.CharField()}
            )
        },
        tags=['Grupos y Permisos']
    )
    def destroy(self, request, *args, **kwargs):
        """Eliminar grupo"""
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        summary="Asignar permisos específicos",
        description="Agrega permisos específicos a un grupo sin reemplazar los existentes",
        request=inline_serializer(
            name='AsignarPermisosRequest',
            fields={
                'permission_ids': serializers.ListField(
                    child=serializers.IntegerField(),
                    help_text="Lista de IDs de permisos a agregar"
                )
            }
        ),
        responses={
            200: GroupSerializer,
            400: inline_serializer(
                name='ValidationError',
                fields={'detail': serializers.CharField()}
            )
        },
        tags=['Grupos y Permisos']
    )
    @action(detail=True, methods=['post'])
    def asignar_permisos(self, request, pk=None):
        """Asignar permisos adicionales a un grupo"""
        group = self.get_object()
        permission_ids = request.data.get('permission_ids', [])
        
        if not permission_ids:
            return Response(
                {'detail': 'La lista permission_ids es requerida'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar que los permisos existen
        permissions = Permission.objects.filter(id__in=permission_ids)
        if permissions.count() != len(permission_ids):
            return Response(
                {'detail': 'Algunos permisos no existen'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Agregar permisos al grupo (no reemplaza, solo agrega)
        group.permissions.add(*permissions)
        
        # Retornar grupo actualizado
        serializer = self.get_serializer(group)
        return Response({
            'message': f'Permisos asignados al grupo {group.name} exitosamente',
            'permissions_added': len(permission_ids),
            'total_permissions': group.permissions.count(),
            'data': serializer.data
        })

    @extend_schema(
        summary="Remover permisos específicos",
        description="Remueve permisos específicos de un grupo",
        request=inline_serializer(
            name='RemoverPermisosRequest',
            fields={
                'permission_ids': serializers.ListField(
                    child=serializers.IntegerField(),
                    help_text="Lista de IDs de permisos a remover"
                )
            }
        ),
        responses={
            200: GroupSerializer,
            400: inline_serializer(
                name='ValidationError',
                fields={'detail': serializers.CharField()}
            )
        },
        tags=['Grupos y Permisos']
    )
    @action(detail=True, methods=['post'])
    def remover_permisos(self, request, pk=None):
        """Remover permisos específicos de un grupo"""
        group = self.get_object()
        permission_ids = request.data.get('permission_ids', [])
        
        if not permission_ids:
            return Response(
                {'detail': 'La lista permission_ids es requerida'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Remover permisos del grupo
        permissions = Permission.objects.filter(id__in=permission_ids)
        group.permissions.remove(*permissions)
        
        # Retornar grupo actualizado
        serializer = self.get_serializer(group)
        return Response({
            'message': f'Permisos removidos del grupo {group.name} exitosamente',
            'permissions_removed': len(permission_ids),
            'total_permissions': group.permissions.count(),
            'data': serializer.data
        })

   

class PermissionViewSet(ReadOnlyModelViewSet):
    """
    ViewSet de solo lectura para consultar permisos disponibles
    """
    queryset = Permission.objects.select_related('content_type').all().exclude(content_type__model='logentry')
    serializer_class = PermissionSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'codename']
    ordering_fields = ['name', 'codename', 'content_type__app_label']
    ordering = ['content_type__app_label', 'name']

    def get_queryset(self):
        """Aplicar filtros personalizados"""
        queryset = super().get_queryset()
        
        # Filtrar por app
        app_label = self.request.query_params.get('app')
        if app_label:
            queryset = queryset.filter(content_type__app_label=app_label)
        
        # Filtrar por modelo
        model = self.request.query_params.get('model')
        if model:
            queryset = queryset.filter(content_type__model=model)
        
        return queryset

    @extend_schema(
        summary="Listar permisos disponibles",
        description="Obtiene una lista de todos los permisos disponibles en el sistema",
        parameters=[
            OpenApiParameter(
                name='app',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Filtrar permisos por app (ej: inventario, erp)',
                required=False,
                examples=[
                    OpenApiExample('Permisos de inventario', value='inventario'),
                    OpenApiExample('Permisos de ERP', value='erp'),
                ]
            ),
            OpenApiParameter(
                name='model',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Filtrar permisos por modelo específico',
                required=False,
                examples=[
                    OpenApiExample('Permisos de productos', value='producto'),
                    OpenApiExample('Permisos de compras', value='compra'),
                ]
            ),
        ],
        responses={200: PermissionSerializer(many=True)},
        tags=['Grupos y Permisos']
    )
    def list(self, request, *args, **kwargs):
        """Lista todos los permisos disponibles"""
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Obtener detalles del permiso",
        description="Obtiene los detalles de un permiso específico",
        responses={
            200: PermissionSerializer,
            404: inline_serializer(
                name='NotFound',
                fields={'detail': serializers.CharField()}
            )
        },
        tags=['Grupos y Permisos']
    )
    def retrieve(self, request, *args, **kwargs):
        """Obtener permiso específico"""
        return super().retrieve(request, *args, **kwargs)

    
        # 🔹 NUEVA ACCIÓN PERSONALIZADA
    @action(detail=False, methods=['get'], url_path='grouped')
    def grouped_permissions(self, request):
        """
            Retorna los permisos agrupados por modelo (content_type.model)
        """
        queryset = self.get_queryset()
        #permisos de gestion de rutas
        PERMISOS_GESTION_RUTAS = {
            'can_ver_pedidos_embarque': 'Ver Pedidos / Embarque',
            'can_cargar_pedidos': 'Carga de rutas',
        }
        
        # Permisos especiales que se agruparán aparte
        PERMISOS_ENTRADA = {
            'can_view_entradas_inventario_compras': 'Visualizar compras por entrar',
            'can_crear_entradas_inventario_compras': 'Dar entradas de nueva mercancía',
            'can_crear_entradas_inventario_abastecimiento': 'Dar entradas de abastecimiento',
        }
        PERMISOS_TRASPASOS = {
            'can_view_traspaso': 'Ver abastecimiento',
            'can_crear_traspaso': 'Crear Abastecimiento',
            'can_crear_solicitud_traspaso': 'Crear Solicitud de Traspaso ',
            'can_view_solicitud_traspaso': 'Ver Solicitud de Traspaso',
            'can_rechazar_solicitud_traspaso': 'Rechazar Solicitud de Traspaso ',
        }
        
        PERM_INVETARIO ={
            'can_consultar_inventario': 'Consultar Inventario',
            'can_view_detalle_cedis':  'Ver Detalle la estructura de CEDIS',
        }
        
        PERM_ESRTTRUCTURA_CEDIS = [
            'can_view_piso',
            'can_update_piso',
            'can_create_piso',
            'can_delete_piso',
            'can_view_zona',
            'can_update_zona',
            'can_create_zona',
            'can_delete_zona',
            'can_view_rack',
            'can_update_rack',
            'can_create_rack',
            'can_delete_rack',
        ]
        
        grouped = {}
        permisos_entrada = []
        permisos_gestion_rutas = []
        permisos_traspasos = []
        permisos_inventario = []
        permisos_estructura_cedis = []
        
        # ✅ Optimización 1: Usar select_related para evitar N+1 queries
        # (Ya está aplicado en get_queryset(), pero lo dejamos explícito)
        permisos = queryset.select_related('content_type').only(
            'id', 'codename', 'name', 
            'content_type__model', 'content_type__app_label'
        )
        
        # ✅ Optimización 2: Un solo loop para clasificar permisos
        for perm in permisos:
            #if perm.content_type.model in ["loteinventario",'movimientoinventario']:
            #    continue
            # Si es un permiso especial de entrada, guardarlo aparte
            
            if perm.codename in PERMISOS_GESTION_RUTAS:
                permisos_gestion_rutas.append({
                    'id': perm.id,
                    'codename': perm.codename,
                    'name': PERMISOS_GESTION_RUTAS[perm.codename].upper(),
                    'app_label': perm.content_type.app_label
                })
                continue
            
            if perm.codename in PERMISOS_ENTRADA:
                permisos_entrada.append({
                    'id': perm.id,
                    'codename': perm.codename,
                    'name': PERMISOS_ENTRADA[perm.codename].upper(),
                    'app_label': perm.content_type.app_label
                })
                continue
            
            if perm.codename in PERM_ESRTTRUCTURA_CEDIS:
                permisos_estructura_cedis.append({
                    'id': perm.id,
                    'codename': perm.codename,
                    'name': perm.name,
                    'app_label': perm.content_type.app_label
                })
                continue
            
            
            if perm.codename in PERMISOS_TRASPASOS:
                permisos_traspasos.append({
                    'id': perm.id,
                    'codename': perm.codename,
                    'name': PERMISOS_TRASPASOS[perm.codename].upper(),
                    'app_label': perm.content_type.app_label
                })
                continue
            
            if perm.codename in PERM_INVETARIO:
                permisos_inventario.append({
                    'id': perm.id,
                    'codename': perm.codename,
                    'name': PERM_INVETARIO[perm.codename].upper(),
                    'app_label': perm.content_type.app_label
                })
                continue
            
            # Agrupar permisos normales por modelo
            model = perm.content_type.model
            if model not in grouped:
                if model in ["loteinventario",'movimientoinventario']:
                    continue
                #if model in ['creditocliente']:
                #    model = 'Créditos de Clientes'
                #if  model in ['creditoproveedor','Créditos de Proveedores']:
                #    model = 'Créditos de Proveedores'
                grouped[model] = []
                
              # Ignorar permisos de LoteInventario
            grouped[model].append({
                'id': perm.id,
                'codename': perm.codename,
                'name': perm.name,
                'app_label': perm.content_type.app_label
            })
        
        # ✅ Optimización 3: Agregar permisos de entrada solo si existen
        if permisos_estructura_cedis:
            # Ordenar por codename antes de agregar
            permisos_estructura_cedis.sort(key=lambda x: x['codename'])
            grouped['Configuración de CEDIS'] = permisos_estructura_cedis
            
        if permisos_entrada:
            # Ordenar por codename antes de agregar
            permisos_entrada.sort(key=lambda x: x['codename'])
            grouped['Entrada de producto'] = permisos_entrada
            
        if permisos_gestion_rutas:
            # Ordenar por codename antes de agregar
            permisos_gestion_rutas.sort(key=lambda x: x['codename'])
            grouped['Gestión de Rutas'] = permisos_gestion_rutas
            
        if permisos_traspasos:
            # Ordenar por codename antes de agregar
            permisos_traspasos.sort(key=lambda x: x['codename'])
            grouped['Traspasos entre almacenes'] = permisos_traspasos
            
        if permisos_inventario:
            # Ordenar por codename antes de agregar
            permisos_inventario.sort(key=lambda x: x['codename'])
            grouped['Inventario'] = permisos_inventario
        
        # ✅ Optimización 4: Ordenar todos los grupos en una sola pasada
        for permisos_list in grouped.values():
            permisos_list.sort(key=lambda x: x['codename'])
        
        return Response(grouped)


