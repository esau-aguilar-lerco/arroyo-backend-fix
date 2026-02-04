from rest_framework import mixins, viewsets,generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action 
from apps.usuarios.models import Usuario
from apps.usuarios.serializers.usuarios import UsuarioSerializer, UsuarioMiniSerializer,UsuarioListSerializer,MiDataResponseSerializer 
from apps.base.serachFilter import MinimalSearchFilter

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes,OpenApiResponse,OpenApiExample
class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all().order_by('-id')
    #serializer_class = UsuarioSerializer
    filter_backends = [MinimalSearchFilter]  # Permite buscar por campos mínimos usando el parámetro 'search'
    search_fields = ['username', 'email', 'id', 'nombre']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return UsuarioListSerializer
        return UsuarioSerializer
    
    #permission_classes = [permissions.IsAuthenticated]
    #permission_classes = [permissions.AllowAny]

    def destroy(self, request, *args, **kwargs):
        # Cancelar/eliminar la operación de borrado
        model = self.get_object()
        model.is_active = False
        model.save()
        return Response({'detail': 'Desactivado correctamente.'}, status=200)

class UsuarioMiniViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
        serializer_class = UsuarioMiniSerializer
        filter_backends = [MinimalSearchFilter]  # Permite buscar por campos mínimos usando el parámetro 'search'
        pagination_class = None
        search_fields = ['username', 'email', 'id', 'nombre']

        def get_queryset(self):
            queryset = Usuario.objects.filter(is_active=True).order_by('-id')
            role = self.request.query_params.get('role', None)

            if role:
                # Filtra si el usuario tiene asignado ese rol en grupos
                role = role.strip().upper()
                queryset = queryset.filter(groups__name=role)

            return queryset

        @extend_schema(
            parameters=[
                OpenApiParameter(
                    name="role",
                    type=OpenApiTypes.STR,
                    description="Filtra usuarios que pertenezcan al grupo especificado",
                    required=False,
                    location=OpenApiParameter.QUERY,
                ),
                OpenApiParameter(
                    name="search",
                    type=OpenApiTypes.STR,
                    description="Buscar usuarios por campos mínimos (ej: nombre, username, email)",
                    required=False,
                    location=OpenApiParameter.QUERY,
                ),
            ]
        )
        def list(self, request, *args, **kwargs):
            return super().list(request, *args, **kwargs)

@extend_schema(
    summary="Obtener datos del usuario autenticado",
    description="Retorna información del usuario actual incluyendo permisos y estado de superusuario",
    responses={200: MiDataResponseSerializer, 401: OpenApiResponse(description="No autenticado")},
    examples=[
        OpenApiExample(
            'Usuario normal',
            value={
                "username": "usuario123",
                "email": "usuario@example.com",
                "full_name": "Juan Pérez",
                "permisos": [
                    "auth.view_user",
                    "inventario.add_producto",
                    "erp.view_cliente"
                ],
                "is_superuser": False,
                "is_staff": False,
                "is_active": True
            },
            response_only=True
        ),
        OpenApiExample(
            'Superusuario',
            value={
                "username": "admin",
                "email": "admin@example.com",
                "full_name": "Administrador Sistema",
                "permisos": [],
                "is_superuser": True,
                "is_staff": True,
                "is_active": True
            },
            response_only=True
        )
    ],
    tags=["usuarios"]
)
class DetalleUsuario(generics.RetrieveAPIView):
    """
    Vista optimizada para obtener los datos del usuario autenticado.
    """
    serializer_class = MiDataResponseSerializer
    #permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        """Retorna el usuario actual."""
        #print("Usuario autenticado:", self.request.user)
        return self.request.user

    def retrieve(self, request, *args, **kwargs):
        usuario = self.get_object()
        permisos = usuario.get_all_permissions()

        data = {
            'username': usuario.username,
            'email': usuario.email,
            'full_name': usuario.full_name(),
            'permisos': list(permisos),
            'is_superuser': usuario.is_superuser,
            'is_staff': usuario.is_staff,
            'is_active': usuario.is_active,
            'caja_abierta': True if usuario.get_mi_caja() is not None else False,
            'mi_almacen_nombre': usuario.almacen.nombre if usuario.almacen else '',
            'mi_almacen_id' : usuario.almacen.id if usuario.almacen else None,
        }
        serializer = self.get_serializer(data)
        return Response(serializer.data)
    
        """
        Obtener datos del usuario autenticado
        """
        usuario = request.user
        permisos = usuario.get_all_permissions()
        
        data = {
            'username': usuario.username,
            'email': usuario.email,
            'full_name': usuario.get_full_name(),
            'permisos': list(permisos),
            'is_superuser': usuario.is_superuser,
            'is_staff': usuario.is_staff,
            'is_active': usuario.is_active,
        }
        
        return Response(data, status=status.HTTP_200_OK)