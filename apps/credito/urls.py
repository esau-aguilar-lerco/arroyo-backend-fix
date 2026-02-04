from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.credito.api.views import CreditoClienteViewSet, CreditoClienteMiniViewSet, PagosCreditoViewSet
from apps.credito.api.views_proveedor import CreditoProveedorViewSet, CreditoProveedorMiniViewSet, PagosCreditoProveedorViewSet

# Router para los ViewSets
router = DefaultRouter()
router.register(r'creditos', CreditoClienteViewSet, basename='credito')
router.register(r'creditos-mini', CreditoClienteMiniViewSet, basename='credito-mini')
router.register(r'pagos-credito', PagosCreditoViewSet, basename='pago-credito')
router.register(r'creditos-proveedor', CreditoProveedorViewSet, basename='credito-proveedor')
router.register(r'creditos-proveedor-mini', CreditoProveedorMiniViewSet, basename='credito-proveedor-mini')
router.register(r'pagos-credito-proveedor', PagosCreditoProveedorViewSet, basename='pago-credito-proveedor')

urlpatterns = [
    
]
urlpatterns += router.urls
