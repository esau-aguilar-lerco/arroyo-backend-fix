from rest_framework import routers
from django.urls import path


from apps.inventario.api.alertas.alertasview import ProductosPorVencerAPIView

from apps.inventario.api.view import (
    PisoViewSet, ZonaViewSet, RackViewSet, PisoPorAlmacenAPIView,
    MovimientoSalidaViewSet, MovimientoTraspasoAPIView,
    InventarioAlmacenAPIView,
    InventarioAlmacenConsultaAPIView,

    InventarioProductoAPIView,
    InventarioProductoCedisAPIView,
    EntradaListViewSet,
    AbastecimientoCreateView,
    MisEntradasListViewSet,
    ProcesarEntradaView,
)

#transformaciones
from apps.inventario.api.trasnformacion.transformacion_views import TransformacionViewSet

from apps.inventario.api.inventarioViews.inventarioAlmacenViews import (
    InventarioAlmacenView,
    InventarioTodosAlmacenesView
)

from apps.inventario.api.traspaso.solicitudTraspasoViews import SolicitudTraspasoViewSet

from apps.inventario.api.productos_solicitud_view import ProductosSolicitudViewSet

#EMBARQUES
from apps.inventario.api.embarque.embarqueRutaView import EmbarqueRutaViewSet

router = routers.DefaultRouter()

"""
==============================================================================================
                            PARA LA DISTRIBUCION DE CDIS
==============================================================================================
"""
router.register(r'piso', PisoViewSet, basename='piso')
router.register(r'zona', ZonaViewSet, basename='zona')
router.register(r'rack', RackViewSet, basename='rack')
#router.register(r'ubicacion', UbicacionRackViewSet, basename='ubicacion')




"""
==============================================================================================
                            MOVIMENTOS DE SALIDA
==============================================================================================
"""
router.register(r'movimiento/salida', MovimientoSalidaViewSet, basename='movimiento-salida')


"""
==============================================================================================
                            SOLICITUDES DE PRODUCTOS
==============================================================================================
"""
router.register(r'productos-solicitud', ProductosSolicitudViewSet, basename='productos-solicitud')
router.register(r'mis-entradas', MisEntradasListViewSet, basename='mis-entradas')

"""
==============================================================================================
                            SOLICITUDES DE TRASPASO
==============================================================================================
"""
router.register(r'solicitudes-traspaso', SolicitudTraspasoViewSet, basename='solicitudes-traspaso')



router.register(r'embarques-ruta', EmbarqueRutaViewSet, basename='embarques-ruta')


router.register(r'transformaciones', TransformacionViewSet, basename='transformaciones-inventario')

# Endpoint documentado para buscar pisos por almacen
urlpatterns = [
	path('pisos-por-almacen/', PisoPorAlmacenAPIView.as_view(), name='pisos-por-almacen'),
    # Movimientos de traspaso (list y detail)
    path('movimiento/traspaso-list/', MovimientoTraspasoAPIView.as_view(), name='movimientos-por-filtro-list'),
    path('movimiento/traspaso-list/<int:pk>/', MovimientoTraspasoAPIView.as_view(), name='movimientos-por-filtro-detail'),


    #=============================================
    #   BUSQUEDA DE PRODUCTOS EN EL INVENTARIO
    #=============================================
    path('inventario/almacen/', InventarioAlmacenAPIView.as_view(), name='inventario-por-almacen'),
    path('inventario/almacen/consulta/', InventarioAlmacenConsultaAPIView.as_view(), name='inventario-por-almacen'),
    path('inventario/producto/', InventarioProductoAPIView.as_view(), name='inventario-por-producto'),
    path('inventario/rack/', InventarioProductoCedisAPIView.as_view(), name='inventario-por-rack'),

    #=============================================
    #   CONSULTA OPTIMIZADA DE INVENTARIO
    #=============================================
    #path('inventario-almacen/<int:almacen_id>/', InventarioAlmacenView.as_view(), name='inventario-almacen-optimizado'),
    path('inventario-almacenes/', InventarioTodosAlmacenesView.as_view(), name='inventario-todos-almacenes'),

    #=============================================
    #   ENTRADAS DE INVENTARIO
    #=============================================
    path('entradas-list-tipo/', EntradaListViewSet.as_view(), name='entradas-inventario'),
    path('entradas-abastecimiento/', AbastecimientoCreateView.as_view(), name='entradas-abastecimiento'),
    path('entradas-traspaso/', ProcesarEntradaView.as_view(), name='procesar-entrada'),
    #path('embarques-ruta/', EmbarqueRutaViewSet.as_view(), name='embarques-ruta'),
    
    
    path('alertas/productos-por-vencer/', ProductosPorVencerAPIView.as_view()),

    #=============================================
    #   TRANSFORMACIONES DE INVENTARIO
    #==============================================
    #path('transformaciones/', TransformacionViewSet.as_view(), name='transformaciones-inventario'),
   ]
    

urlpatterns += router.urls