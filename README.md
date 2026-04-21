# Arroyo Backend Fix — Historial de cambios (por commit) | Cruce de alcance

> Fuente del histórico: `git log --reverse --pretty=format:"%h|%ad|%s" --date=short`  
> Este documento organiza los commits por **bloques funcionales** y cruza el alcance original (**Excel inicial: 21 puntos**) contra los commits.

---

## 1) Recopilación de cambios por commit (histórico completo)

### 1.1 Inicialización y housekeeping
- **2026-02-04** · `da99192` · Project upload
- **2026-02-05** · `48aeb59` · security: ignorar .env
- **2026-03-03** · `ee666e2` · docs: agregar recopilación de cambios por commit y guía de pruebas Postman

### 1.2 Compras / Órdenes de compra / Gastos
- **2026-02-08** · `6d55003` · fix(compras): totales con gastos y override admin en OC
- **2026-02-11** · `0ca8ad5` · fix: flujo de compras

### 1.3 Abastecimiento / Inventario / Entradas / Histórico
- **2026-02-08** · `8c48f17` · fix(abastecimiento): decimales y origen CEDIS
- **2026-02-12** · `9db7327` · fix(inventario): estabiliza entradas/abastecimiento e inventario para flujo E2E
- **2026-02-12** · `30e21f0` · fix: histórico ahora es por producto_id (obligatorio)
- **2026-02-20** · `44d3c1a` · fix: Inventario Almacen Consulta Api
- **2026-02-25** · `5ade6a7` · fix(inventario): calcular precio_unitario por promedio ponderado de inventario

### 1.4 Incidencias / Tipificación / Nomenclatura
- **2026-02-09** · `bce8c87` · (full-fix) 'insidencia(s)' -> incidencia(s)
- **2026-02-12** · `6278945` · fix: tipificación no coincidía exactamente con descripción (bloqueo de atención)

### 1.5 Traspasos / Concurrencia / Robustez
- **2026-02-13** · `c0e612d` · fix(traspaso): evitar KeyError 'cantidad' al aprobar solicitudes
- **2026-02-13** · `4ac36d3` · fix(traspaso): corregir detalle de movimiento por id
- **2026-02-16** · `3b2c135` · add: Traspasos -> información dinámica + casos diferentes en el flujo
- **2026-02-16** · `0b995b2` · fix: FOR UPDATE -> OUTER JOIN | aprobar/rechazar
- **2026-02-17** · `5286e9d` · fix(traspaso): diferir afectación de inventario hasta recepción
- **2026-02-16** · `6e081ff` · fix: doble notificación de traspaso

### 1.6 Crédito proveedor / Agrupación / Referencia
- **2026-02-09** · `c5bea97` · feat(credito-proveedor): agrupado por proveedor y referencia en pagos
- **2026-02-13** · `40ce98e` · fix: créditos proveedor
- **2026-02-13** · `5dfeb81` · fix(api): costos por detalle en abastecimiento y estadísticas proveedor con créditos

### 1.7 Prelación (pagos) + Idempotencia
- **2026-02-13** · `d522e79` · feat: prelacion -> clientes-proveedores + agrupación
- **2026-02-15** · `ac64b4a` · feat(prelación): idempotency-key, atomic + select_for_update y trazabilidad completa en pagos de crédito
- **2026-02-15** · `7aaa172` · fix(prelación): idempotencia concurrente (IntegrityError + replay seguro) en pagos de crédito
- **2026-02-16** · `3335156` · fix: CORS error -> prelación

### 1.8 Crédito cliente (plazos / sujeto a crédito)
- **2026-02-17** · `bafa9de` · fix: plazos en crédito cliente (semanas → días)
- **2026-02-25** · `82bbef8` · fix(credito-cliente): corregir alta y habilitación de sujeto a crédito

### 1.9 Comandera / Ventas / Caja
- **2026-02-16** · `a9848bd` · feat(comanda): reflejar ventas de comandera en listado de ventas
- **2026-02-16** · `c50b991` · fix(ventas): incluir comandera terminada en filtro por fase
- **2026-02-26** · `a5478e8` · fix(ventas-caja): compatibilidad fase app y referencia nula en pagos

### 1.10 Embarques / Reparto / Ruta-app (flujo operativo + robustez)
- **2026-02-10** · `a92ccca` · fix: estabiliza flujo de embarque/reparto y cantidades reales en API
- **2026-02-11** · `29769c7` · fix: estabiliza flujo de embarque y stock por origen real
- **2026-02-11** · `941e05a` · fix: final-embarque
- **2026-02-19** · `e50ddda` · fix(embarque): evitar TransactionManagementError al crear embarque
- **2026-02-23** · `afe4ac4` · fix: flujo embarque
- **2026-02-23** · `8fc78b5` · fix: pedidos embarque + totalizadores
- **2026-02-19** · `f0e10d1` · fix(reparto): forzar ruta de usuario y priorizar CDR en tara abierta
- **2026-02-19** · `3e23242` · fix(reparto): robustecer iniciar/finalizar con manejo seguro de idempotencia
- **2026-02-19** · `7a5dbef` · fix(idempotencia): evitar TransactionManagementError en iniciar/finalizar reparto
- **2026-02-20** · `76ec81b` · fix: carga de rutas PROGRAMADO -> REPARTO
- **2026-02-16** · `ce60e34` · feat(embarque): reemplazar fase CARGA por PROGRAMADO
- **2026-02-26** · `a3d1c8e` · feat(reparto): agregar historial de ventas entregadas para app
- **2026-02-26** · `fbae729` · fix: ejecución de movimientos estaba en orden inverso: TARA → PEDIDOS
- **2026-02-26** · `f3da5ff` · fix: entrega estaba tomando cantidad_entregada como si fuera nueva salida completa cada vez
- **2026-02-26** · `d76ce1f` · fix(reparto): entregar desde lotes asignados por venta y evitar sobreconsumo
- **2026-02-26** · `6429612` · fix(reparto): resolver embarque activo por venta y consolidar lotes asignados
- **2026-02-26** · `cb9d4a1` · fix: línea de embarque quedó ligada a lote incorrecto
- **2026-02-26** · `fc3aae1` · fix: inventario en embarque (17 -> 30)
- **2026-02-26** · `fafe206` · feat(reparto): historial app sin paginación y pedidos activos filtrables
- **2026-02-27** · `e2c53b6` · fix(ventas-app): evitar doble descuento de lotes y ventas sin stock
- **2026-02-27** · `d19c37e` · feat(reparto): generar corte PDF backend y soporte inline
- **2026-02-27** · `ecd90ef` · fix: normalización de nombre de usuario para el PDF

### 1.11 Pricing (reglas globales / exposición / alineación)
- **2026-02-24** · `5e47b1d` · fix(pricing): aplicar reglas globales de venta y normalizar precio_tipo cliente
- **2026-02-25** · `6a6aa35` · fix(pricing): exponer precios calculados y alinear reglas en inventario
- **2026-02-25** · `7dd8713` · fix(precios): unificar costo arroyo ponderado en compras y solicitudes
- **2026-02-25** · `e878229` · fix(rutas): habilitar visibilidad de precios y precio por tipo cliente en app

### 1.12 Pull Requests / merges (administrativo)
- **2026-02-16** · `b0a4959` · Merge pull request #1 (comanda)
- **2026-02-16** · `a030025` · Merge pull request #2 (comanda)
- **2026-02-16** · `c98b572` · Merge pull request #3 (app)
- **2026-02-16** · `f5eb286` · Merge pull request #4 (app)

---

## 2) Commit destacado: `ad4a7e4` (NPF | 30, 18, 19, 23)

### 2.1 Archivos tocados
- `.gitignore`
- `apps/erp/api/embarque_view.py`
- `apps/erp/migrations/0086_compra_fecha_vencimiento.py`
- `apps/erp/models.py`
- `apps/erp/serializers/ventas_serializer.py`
- `apps/inventario/api/traspaso/solicitudTraspasoViews.py`
- `apps/inventario/helpers/transformacion/movimientos_transformacion.py`
- `apps/inventario/models.py`
- `apps/inventario/services/entradas.py`
- `apps/usuarios/api/auth_views.py`

### 2.2 Cambios funcionales (resumen)
- Gestión de pedidos/rutas: `listar_preventas_con_detalles_carga` resuelve el almacén desde la ruta (`almacen_embarque`) y no desde `user.almacen`
- Ventas (serializer): inclusión de `condicion_pago` para distinguir contado/crédito en listados
- Transformaciones/merma: asignación FIFO automática de lotes en merma cuando no llegan lotes explícitos + validaciones de stock
- Abastecimiento/entradas: validaciones de costo unitario + vencimiento + selección de producto por id
- Inventario lote/compra: robustez en cálculo de vencimiento
- Traspaso: `select_for_update` + validación de inventario insuficiente

---

## 3) Guía corta de pruebas (Postman / curl)

### 3.1 Autenticación
- `POST /api/token/` (JWT)

### 3.2 Prelación (pagos crédito)
- `POST /api/pagos-credito/*/prelacion/` + header `Idempotency-Key`

Ejemplo:
```bash
curl -X POST "$BASE_URL/<base_proveedor>/prelacion/"   -H "Authorization: Bearer $TOKEN"   -H "Content-Type: application/json"   -H "Idempotency-Key: <uuid>"   -d '{"proveedor":123,"cantidad_pagar":"1500.00","metodo_pago":"TRANSFERENCIA","referencia":"FOLIO-ABC-123"}'
```

### 3.3 Docs
- `GET /api/docs/`

### 3.4 Historial de ventas entregadas (app)
- `GET /api/embarques-reparto/historial-ventas/`

---

## Referencias
- Documento interno. (s. f.). *Precio de venta*
