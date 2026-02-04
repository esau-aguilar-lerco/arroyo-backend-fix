from apps.base.auth.basePermiso import model_permission

# Uso:
EmpresaPermission = model_permission('empresa')
ClientePermission = model_permission('cliente')
ProveedorPermission = model_permission('proveedor')
ProductoPermission = model_permission('producto')
AlmacenPermission = model_permission('almacen')
SucursalPermission = model_permission('sucursal')
OrdenCompraPermission = model_permission('orden_compra')
CompraPermission = model_permission('compra')
UnidadVehicularPermission = model_permission('unidad_vehicular')
RutasPermission = model_permission('rutas')
PreVentaPermission = model_permission('pre_venta')
# Para casos especiales:
# CompraPermission = model_permission('compra', custom_permissions={
#     'aprobar': 'erp.can_approve_compra',
#     'rechazar': 'erp.can_reject_compra'
# })