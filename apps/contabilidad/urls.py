from rest_framework.routers import DefaultRouter
from .api.views import MetodoPagoViewSet, RegimenFiscalViewSet, UnidadSatViewSet

router = DefaultRouter()
#router.register(r'regimen-fiscal', RegimenFiscalViewSet, basename='regimenfiscal')
#router.register(r'unidades-sat', UnidadSatViewSet, basename='unidadsat')
router.register(r'metodos-pago', MetodoPagoViewSet, basename='metodopago')

urlpatterns = router.urls
