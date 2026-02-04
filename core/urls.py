
from django.contrib import admin
from django.urls import path, include,re_path
from django.conf.urls.static import static
from django.conf import settings
from core.views import root_view

from rest_framework import permissions

#from drf_yasg.views import get_schema_view
#from drf_yasg import openapi

#from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView

#schema_view = get_schema_view(
#    openapi.Info(
#        title="APIS ARROYO VERSIÓN 2",
#        default_version='v1',
#        description="Documentación de la API",
#        contact=openapi.Contact(email="tucorreo@dominio.com"),
#        license=openapi.License(name="MIT"),
#    ),
#    public=True,
#    permission_classes=[permissions.AllowAny],
#)


urlpatterns = [
    path('', root_view, name='root'),
   # URL de administración
    path('admin/', admin.site.urls),
    # URL de autenticación JWT
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),  # Obtener token de acceso
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),  # Refrescar token de acceso
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),  # Verificar token de acceso
   
       # ===============================
    # 📘 DOCUMENTACIÓN API (AQUÍ)
    # ===============================
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),


    # URL de la aplicación de direcciones
    path('api/direccion/', include('apps.direccion.urls')),
    path('api/', include('apps.credito.urls')),
    # URL de la aplicación de usuarios
    path('api/',include('apps.usuarios.urls')),
    # URL de la aplicación ERP
    path('api/', include('apps.erp.urls')),
    #URL DE INVENTARIOS
    path('api/', include('apps.inventario.urls')),
    path('api/', include('apps.contabilidad.urls')),



]+ static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) \
 + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

