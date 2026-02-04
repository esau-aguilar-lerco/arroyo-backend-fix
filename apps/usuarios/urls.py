from django.urls import include, path
from rest_framework import routers
from apps.usuarios.api.usuarios import UsuarioViewSet, UsuarioMiniViewSet, DetalleUsuario
from apps.usuarios.api.auth_views import GroupViewSet, PermissionViewSet

router = routers.DefaultRouter()
router.register(r'usuarios', UsuarioViewSet, basename='usuario')
router.register(r'usuarios-mini', UsuarioMiniViewSet, basename='usuario-mini')

# Rutas para gestión de grupos y permisos
router.register(r'grupos', GroupViewSet, basename='grupo')
router.register(r'permisos', PermissionViewSet, basename='permiso')

urlpatterns = [
    path('', include(router.urls)),
    path('mi-data/', DetalleUsuario.as_view(), name='mi-data'),
]