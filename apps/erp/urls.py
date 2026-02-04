from rest_framework import routers
from django.urls import path
#VISTAS 
from apps.erp.api.view import (  EmpresaMiniViewSet, EmpresaViewSet,
    ProductoViewSet,ProductoMiniViewSet,ProductoInventarioAPIView, CategoriaViewSet,CategoriaMiniViewSet,    #PRODUCTOS Y CATEGORIAS 
    ProveedorViewSet, ProveedorMiniViewSet,
    ClienteViewSet, ClienteMiniViewSet,InformacionClienteViewSet,
    AlmacenViewSet,AlmacenMiniViewSet,
    SucursalViewSet,SucursalMiniViewSet,
    OrdenCompraViewSet, OrdenCompraMiniViewSet, OrdenCompraCompletaListView,  #ÓRDENES DE COMPRA
    CompraViewSet, CompraMiniViewSet,  #COMPRAS
    RutasViewSet, RutasMiniViewSet)  #RUTAS

from apps.erp.api.unidad_vehicular_view import UnidadVehicularViewSet, UnidadVehicularMiniViewSet
from apps.erp.api.ventas_view import (
    VentaViewSet, VentaMiniViewSet, 
    #VentaDetalleViewSet, VentaDetalleLoteViewSet,
    
)
from apps.erp.api.embarque_view import (
    EmbarqueListCreateAPIView,
    listar_preventas_con_detalles_carga,
    EmbarqueRepartoListRetrieveAPIView,
    iniciar_reparto,finalizar_reparto,
    obtener_caja_movimientos_embarque,
    checkin_producto_embarque
)
from apps.erp.api.reparto_view import entrega_producto_ruta
from apps.erp.api.insidencias import InsidenciaListRetrieveAPIView, atender_insidencia_lote
from apps.erp.api.notificacion import NotificacionViewSet
from apps.erp.api.gastos_compra_view import GastosCompraViewSet
from apps.contabilidad.api.views import RegimenFiscalViewSet, UnidadSatViewSet


#cajas
from apps.erp.api.caja.caja import CajaViewSet, CajaMiniViewSet
from apps.erp.api.caja.apertura import AperturaCajaMiniViewSet,AperturaCajaViewSet
from apps.erp.api.caja.movomientos import MovimientoCajaViewSet, TransaccionCajaViewSet

#categorias cliente
from apps.erp.api.cliente.categoria import CategoriaClienteViewSet, CategoriaClienteMiniViewSet

rutas = routers.DefaultRouter()
rutas.register(r'contabilidad/regimen-fiscal', RegimenFiscalViewSet, basename='regimenfiscal')
rutas.register(r'contabilidad/unidades-sat', UnidadSatViewSet, basename='unidadsat')

rutas.register(r'empresas', EmpresaViewSet, 'empresa')
rutas.register(r'empresas-mini', EmpresaMiniViewSet, 'empresa-mini')

rutas.register(r'categorias', CategoriaViewSet, 'categoria')
rutas.register(r'categorias-mini', CategoriaMiniViewSet, 'categoria-mini')

rutas.register(r'proveedores', ProveedorViewSet, 'proveedor')
rutas.register(r'proveedores-mini', ProveedorMiniViewSet, 'proveedor-mini')

rutas.register(r'productos', ProductoViewSet, 'producto')
rutas.register(r'productos-mini', ProductoMiniViewSet, 'producto-mini')
#rutas.register(r'productos-inventario', ProductoInventarioAPIView, 'producto-inventario')

rutas.register(r'clientes', ClienteViewSet, 'cliente')
rutas.register(r'clientes-mini', ClienteMiniViewSet, 'cliente-mini')
rutas.register(r'clientes-info', InformacionClienteViewSet, 'cliente-info')
rutas.register(r'clientes-categorias-mini', CategoriaClienteMiniViewSet, 'cliente-categoria-mini')
rutas.register(r'clientes-categorias', CategoriaClienteViewSet, 'cliente-categoria')

rutas.register(r'almacenes', AlmacenViewSet, 'almacen')
rutas.register(r'almacenes-mini', AlmacenMiniViewSet, 'almacen-mini')

rutas.register(r'sucursales', SucursalViewSet, 'sucursal')
rutas.register(r'sucursales-mini', SucursalMiniViewSet, 'sucursal-mini')

rutas.register(r'ordenes-compra', OrdenCompraViewSet, 'orden-compra')
rutas.register(r'ordenes-compra-mini', OrdenCompraMiniViewSet, 'orden-compra-mini')

rutas.register(r'compras', CompraViewSet, 'compra')
rutas.register(r'compras-mini', CompraMiniViewSet, 'compra-mini')
rutas.register(r'gastos-compra', GastosCompraViewSet, 'gasto-compra')

rutas.register(r'rutas', RutasViewSet, 'ruta')
rutas.register(r'rutas-mini', RutasMiniViewSet, 'ruta-mini')

rutas.register(r'unidades-vehiculares', UnidadVehicularViewSet, 'unidad-vehicular')
rutas.register(r'unidades-vehiculares-mini', UnidadVehicularMiniViewSet, 'unidad-vehicular-mini')

rutas.register(r'ventas', VentaViewSet, 'venta')
rutas.register(r'ventas-mini', VentaMiniViewSet, 'venta-mini')
#rutas.register(r'venta-detalles', VentaDetalleViewSet, 'venta-detalle')
#rutas.register(r'venta-detalle-lotes', VentaDetalleLoteViewSet, 'venta-detalle-lote')
rutas.register(r'notificaciones', NotificacionViewSet, basename='notificacion')

rutas.register(r'cajas', CajaViewSet, 'caja')
rutas.register(r'cajas-mini', CajaMiniViewSet, 'caja-mini')
rutas.register(r'aperturas-caja', AperturaCajaViewSet, 'apertura-caja')
rutas.register(r'aperturas-caja-mini', AperturaCajaMiniViewSet, 'apertura-caja-mini')
rutas.register(r'movimientos-caja', MovimientoCajaViewSet, basename='movimientos-caja')
rutas.register(r'transacciones-caja', TransaccionCajaViewSet, basename='transacciones-caja')
urlpatterns = [
    #path('libro/buscar/',LibroViewSet.as_view({'get':'buscar'}), name='buscar-libro'),
    path('producto-inventario/', ProductoInventarioAPIView.as_view(), name='producto-inventario'),
    
    path('ordenes-compra-completa/', OrdenCompraCompletaListView.as_view(), name='ordenes-compra-completa'),
    # URLs de embarque
    path('embarques-crear/', EmbarqueListCreateAPIView.as_view(), name='embarque-list-create'),
    #path('embarques/resumen/', EmbarqueResumenAPIView.as_view(), name='embarque-resumen'),
    #path('embarques/<int:ruta_id>/', EmbarqueDetailAPIView.as_view(), name='embarque-detail'),
    
    
    path('embarques/preventas-detalles/', listar_preventas_con_detalles_carga, name='listar_preventas_con_detalles_carga'),
    # Embarques de reparto - listar y detalle
    path('embarques-reparto/',           EmbarqueRepartoListRetrieveAPIView.as_view(), name='embarque-reparto-list'),
    path('embarques-reparto/<int:pk>/',  EmbarqueRepartoListRetrieveAPIView.as_view(), name='embarque-reparto-detail'),
    path('embarques-reparto/iniciar/',   iniciar_reparto, name='embarque-iniciar-reparto'),
    path('embarques-reparto/finalizar/', finalizar_reparto, name='embarque-finalizar-reparto'),
    path('embarques-reparto/caja-movimientos/', obtener_caja_movimientos_embarque, name='embarque-caja-movimientos'),
    path('embarques-reparto/checkin/', checkin_producto_embarque, name='embarque-checkin-producto'),
    # Reparto - entrega de productos
    path('reparto/entrega-producto/', entrega_producto_ruta, name='reparto-entrega-producto'),
    # Insidencias
    path('incidencias/', InsidenciaListRetrieveAPIView.as_view(), name='insidencia-list'),
    path('incidencias/<int:pk>/', InsidenciaListRetrieveAPIView.as_view(), name='insidencia-detail'),
    path('incidencias/atender-lote/', atender_insidencia_lote, name='insidencia-atender-lote'),
]

urlpatterns += rutas.urls