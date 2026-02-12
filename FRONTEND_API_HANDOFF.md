# Frontend API Handoff (Arroyo)

Documento de integración Frontend <-> Backend para los flujos operativos críticos.

## 1) Configuración base

- Base URL: `environment.url` (ejemplo: `https://pruebas.lercomx.com/api/`)
- Auth: `Authorization: Bearer <access_token>`
- Header recomendado:
  - `Accept: application/json`
  - `Content-Type: application/json` (solo en `POST/PUT/PATCH`)

## 2) Módulo Compras

### 2.1 Crear/Listar/Detalle de compras

- `GET /api/compras/?limit={n}&offset={n}&search={txt}`
  - Params: `limit`, `offset`, `search` (opcionales)
  - Respuesta: lista paginada de compras (`id`, `codigo`, `estado`, `proveedor_obj`, `total`, etc.)
  - Front: `src/app/services/compra.service.ts:33`
  - Uso: pantalla lista de compras.

- `POST /api/compras/`
  - Body: compra con `proveedor`, `detalles[]`, `metodosPago[]`, `nota`, `fecha_salida`, `is_app`, etc.
  - Respuesta: compra creada (incluye `id`, `codigo`, `detalles`, `pagos_detalle`)
  - Front: `src/app/services/compra.service.ts:53`
  - Uso: formulario de compra.

- `GET /api/compras/{id}/`
  - Respuesta: detalle completo de compra + pagos + gastos.
  - Front: `src/app/services/compra.service.ts:64`
  - Uso: vista detalle de compra.

### 2.2 Gastos adicionales de compra

- `GET /api/gastos-compra/?compra={id}`
  - Respuesta: gastos asociados a compra.
  - Front: `src/app/services/compra.service.ts:68`
  - Uso: desglose en detalle de compra.

- `POST /api/gastos-compra/crear-multiples/`
  - Body:
    ```json
    {
      "gastos": [
        { "compra": 300, "descripcion": "flete", "monto": 1000, "concepto": "FLETE" }
      ]
    }
    ```
  - Respuesta: gastos creados.
  - Front: `src/app/services/compra.service.ts:60`

### 2.3 Entrada de nueva mercancía (abastecimiento)

- `GET /api/compras/?estado=EN CAMINO&limit={n}&offset={n}&search={txt}`
  - Front: `src/app/services/nueva-mercancia.service.ts:24`
  - Uso: seleccionar compras pendientes de entrada.

- `POST /api/entradas-abastecimiento/`
  - Body:
    ```json
    {
      "compra": 300,
      "nota": "texto opcional",
      "items": [
        { "producto": 161, "cantidad": "50.000", "ubicacion_rack": 1 }
      ]
    }
    ```
  - Respuesta (`success true`): `movimiento_principal`, `compra`, `almacen_destino`, `resumen`, `productos_abastecidos`, `metadatos`.
  - Front: `src/app/services/nueva-mercancia.service.ts:28`
  - Uso: confirmar entrada física.

## 3) Módulo Inventario

### 3.1 Consulta paginada por almacén

- `GET /api/inventario/almacen/consulta/?limit={n}&offset={n}&almacen_id={id}&search={txt}&producto_id={id}&incluir_lotes={bool}`
  - Respuesta paginada:
    - `count`, `next`, `previous`
    - `results.almacen_id`, `results.total_productos`, `results.total_lotes`, `results.productos[]`
  - Front: `src/app/services/consulta-inventario.service.ts:24`
  - Uso: pantalla principal de consulta inventario.

### 3.2 Detalle por producto (global y por almacén)

- `GET /api/inventario/producto/?producto_id={id}`
  - Respuesta: resumen global + `almacenes[]` + `lotes_detalle[]`.
  - Front: `src/app/services/consulta-inventario.service.ts:28`
  - Uso: vista producto inventario.

### 3.3 Inventario por almacén para selección de lotes/productos

- `GET /api/inventario/almacen/?producto_id={id}&almacen_id={id?}&incluir_lotes={true|false}`
  - Respuesta: `productos[]` con lotes cuando aplica.
  - Front: `src/app/services/utils.service.ts:110`
  - Uso: formularios de venta, traspaso, embarque, etc.

### 3.4 Histórico diario de movimientos (nuevo para front)

- `GET /api/movimiento/historico-diario/?almacen_id={id}&producto_id={id?}&fecha_inicio=YYYY-MM-DD&fecha_fin=YYYY-MM-DD`
  - Params obligatorios: `almacen_id`
  - Respuesta:
    - `resumen_diario[]` (fecha, tipo, totales)
    - `detalle[]` (movimiento por producto con referencia)
    - `total_registros`
  - Front sugerido:
    - Servicio nuevo: `src/app/services/movimiento-historico.service.ts`
    - Página nueva: `src/app/pages/movimientos-historico/`
  - Uso: histórico diario por almacén/producto.

## 4) Módulo Embarque / Reparto

### 4.1 Listado de preventas para carga

- `GET /api/embarques/preventas-detalles/?ruta_id={id}`
  - Opcionales: `fase`, `solo_productos=true`
  - Respuesta: `preventas[]` con `productos[]`, `cantidad_inventario`, `cantidad_cargada`, `falta_inventario`.
  - Front: `src/app/services/pedido-embarque.service.ts:21`
  - Uso: Paso 1 de carga de ruta.

### 4.2 Crear embarque/carga de ruta

- `POST /api/embarques-crear/`
  - Body:
    ```json
    {
      "ruta": 1,
      "pedidos": [
        {
          "venta": 492,
          "productos": [{ "producto": 90, "cantidad": "40.20000", "check": true }]
        }
      ],
      "productos_tara": []
    }
    ```
  - Respuesta: `{ "success": true, "embarque_id": 19, "fase": "CARGA" }`
  - Front: `src/app/services/reparto.service.ts:42`
  - Uso: confirmar carga.

### 4.3 Lista y detalle de repartos

- `GET /api/embarques-reparto/?limit={n}&offset={n}&search={txt}&ruta_id={id}&fase={fase}&encargado_id={id}`
  - Opcional: `sin_paginacion=true`
  - Front: `src/app/services/reparto.service.ts:34`

- `GET /api/embarques-reparto/{id}/?include_ventas={true|false}`
  - Front: `src/app/services/reparto.service.ts:38`

### 4.4 Inicio/fin de reparto

- `POST /api/embarques-reparto/iniciar/`
  - Body: `{ "embarque_id": 13, "nota": "opcional" }`
  - Front: `src/app/services/reparto.service.ts:46`

- `POST /api/embarques-reparto/finalizar/`
  - Body: `{ "reparto_id": 13 }` o `{ "embarque_id": 13 }`
  - Front: `src/app/services/reparto.service.ts:50`

### 4.5 Caja y cierre de reparto

- `GET /api/embarques-reparto/caja-movimientos/?embarque_id={id}`
  - Respuesta: resumen de caja, transacciones y ventas ligadas al embarque.
  - Front: `src/app/services/reparto.service.ts:55`
  - Uso: botón imprimir cierre / corte.

### 4.6 Pedidos del usuario en fase REPARTO

- `GET /api/embarques-reparto/pedidos-usuario/`
  - Opcional: `embarque_id`
  - Respuesta: embarque activo del usuario + pedidos/productos.
  - Front sugerido:
    - Servicio: `src/app/services/reparto.service.ts` (método nuevo)
    - Pantalla reparto operativo (perfil ruta/ventas).

### 4.7 Entrega producto en reparto

- `POST /api/reparto/entrega-producto/`
  - Body: depende de `EntragaProductoRutaSerializer` (venta, detalle/lote, cantidad entregada, etc.)
  - Uso: cambiar estatus de entrega real.
  - Front: módulo reparto detalle.

## 5) Módulo Incidencias

- `GET /api/incidencias/?limit={n}&offset={n}&search={txt}&resuelta={true|false}`
  - Front: `src/app/services/incidencia.service.ts:21`

- `GET /api/incidencias/{id}/`
  - Front: `src/app/services/incidencia.service.ts:24`

- `POST /api/incidencias/atender-lote/`
  - Body:
    ```json
    {
      "lotes": [
        { "incidencia_lote_id": 10, "tipificacion": "DAÑADO", "nota": "texto" }
      ]
    }
    ```
  - Front: `src/app/services/incidencia.service.ts:29`

## 6) Módulo Crédito Proveedor

### 6.1 Listado agrupado y detalle

- `GET /api/creditos-proveedor/?limit={n}&offset={n}&search={txt}&agrupado=true`
  - Front: `src/app/services/credito-proveedor.service.ts:32`

- `GET /api/creditos-proveedor/estadisticas/`
  - Front: `src/app/services/credito-proveedor.service.ts:21`

- `GET /api/creditos-proveedor/estadisticas-proveedor/{proveedor_id}/`
  - Front: `src/app/services/credito-proveedor.service.ts:40`

- `GET /api/creditos-proveedor/?proveedor={id}&limit={n}&offset={n}`
  - Front: `src/app/services/credito-proveedor.service.ts:44`

### 6.2 Pagos / abonos

- `GET /api/pagos-credito-proveedor/por-proveedor/{id}/?limit={n}&offset={n}`
  - Front: `src/app/services/credito-proveedor.service.ts:48`

- `POST /api/pagos-credito-proveedor/`
  - Body esperado (singular):
    ```json
    {
      "credito": 4,
      "cantidad_pagar": "1000.0000",
      "pagos": [
        { "metodo_pago": 1, "monto": "1000.0000", "referencia": "TRX-123" }
      ]
    }
    ```
  - Respuesta: crédito actualizado y cambio calculado si aplica.
  - Front: `src/app/services/credito-proveedor.service.ts:57`

## 7) Módulo Notificaciones

- `GET /api/notificaciones/`
  - Front: `src/app/services/notificacion.service.ts:77`

- `PATCH /api/notificaciones/{id}/marcar-leida/`
  - Front: `src/app/services/notificacion.service.ts:125`

- `POST /api/notificaciones/marcar-todas-leidas/`
  - Front: `src/app/services/notificacion.service.ts:135`

## 8) Hallazgos de Front pendientes (importantes)

1. En entrada de mercancía sigue mostrando `Total estimado` en vez de folio de compra.
   - Archivo: `src/app/pages/nueva-mercancia/entrada-mercancia/entrada-mercancia.component.html:34`
   - Requerido: mostrar `compra.codigo`.

2. Referencia de pago no está obligatoria al agregar pago.
   - Archivos:
     - `src/app/components/form-compra/form-compra.component.ts:330`
     - `src/app/components/form-compra/form-compra.component.html:248`
   - Requerido: bloquear `agregarPago()` cuando `referencia` vacía para métodos no-efectivo (o para todos, según regla de negocio).

3. Orden compra agrupa producto repetido y puede ocultar líneas con distinto precio.
   - Archivo: `src/app/components/form-orden/form-orden.component.ts:305`
   - Archivo: `src/app/components/form-orden/form-orden.component.ts:323`
   - Requerido: permitir líneas separadas por combinación `producto + precio`.

4. Falta integrar endpoint de histórico diario en frontend.
   - Endpoint backend ya disponible: `GET /api/movimiento/historico-diario/`
   - Requerido: servicio + pantalla/reportes.

5. Lista de embarque hoy carga repartos en fase `CARGA` de forma fija.
   - Archivo: `src/app/services/utils.service.ts:125`
   - Si negocio requiere más fases/rutas, ajustar filtro (`fase`) o hacerlo configurable.

## 9) Checklist E2E que debe pasar (Front)

1. Compra creada debe mostrar `codigo` en listado y detalle.
2. Entrada de mercancía debe reflejar inventario real en almacén destino.
3. Si cantidad recibida difiere (menor o mayor), debe crear incidencias correctas y mostrarlas.
4. Carga de ruta debe tomar inventario del almacén operativo correcto (concentrado/ruta según configuración).
5. Embarque creado debe avanzar a reparto y permitir inicio/finalización.
6. Cierre de reparto debe resolver caja-movimientos sin 404.
7. Crédito proveedor debe mostrar abonos y permitir liquidación total/parcial.
8. Notificaciones deben listar y marcar leídas (individual y masivo).

