# Arroyo Backend Fix — Historial de cambios (por commit) + Cruce de alcance

> Fuente del histórico: `git log --reverse --pretty=format:"%h|%ad|%s" --date=short`  
> Este documento organiza los commits por **bloques funcionales** y cruza el alcance original (**Excel inicial: 21 puntos**) contra los commits.

---

## 1) Recopilación de cambios por commit (histórico completo)

### 1.1 Inicialización y housekeeping
- **2026-02-04** · `da99192` · Project upload
- **2026-02-05** · `48aeb59` · security: ignorar .env
- **2026-02-05** · `adf6b4f` · last fix *(mensaje genérico; usar diff si se requiere como evidencia)*
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

## 2) Cruce: 21 puntos solicitados vs commits
Leyenda: **directo** (match claro), **parcial** (relación probable por módulo/flujo), **sin evidencia** (sin commit explícito por mensaje en el histórico).

### Punto 1 — Notas de venta de crédito / imprimir (Homero)
- `82bbef8` · crédito-cliente sujeto a crédito · **parcial**

### Punto 2 — Cierre de ruta / reporte cierre ($)
- `d19c37e` · corte PDF backend · **directo**

### Punto 3 — Notificaciones de productos a vencer
- **sin evidencia** *(existen commits de Notificaciones, pero no mencionan “vencer” explícitamente)*

### Punto 4 — Consulta de inventario abierta
- `1b1f422` · validar reparto por ruta + consulta global inventario · **directo**
- `44d3c1a` · Inventario Almacen Consulta Api · **directo**

### Punto 6 — Contado vs crédito (gestión pedidos/rutas)
- `ad4a7e4` · NPF | 30, 18, 19, 23 · **directo**
- `a5478e8` · ventas-caja compat + referencia · **parcial**

### Punto 7 — Productos con precio (gestión pedidos)
- `e878229` · visibilidad de precios + precio por tipo cliente (app) · **parcial**
- `6a6aa35` · exponer precios calculados · **parcial**
- `8fc78b5` · pedidos embarque + totalizadores · **parcial**

### Punto 8 — Diferencias CEDIS vs concentrado por usuario
- `ad4a7e4` · NPF | 30, 18, 19, 23 · **directo**
- `1b1f422` · reparto por ruta + consulta inventario · **parcial**

### Punto 9 — Transformación: merma no generaba
- `ad4a7e4` · NPF | 30, 18, 19, 23 · **directo**

### Punto 10 — Agrupar por proveedor (no líneas de crédito)
- `c5bea97` · agrupado por proveedor · **directo**

### Punto 11 — Comandera: pagado/adeudo/cambio
- `a9848bd` · ventas comanda en listado · **parcial**
- `c50b991` · filtro fase · **parcial**
- `a5478e8` · compat fase app + referencia · **parcial**

### Punto 12 — Referencia en pago a proveedores
- `c5bea97` · referencia en pagos proveedor · **directo**

### Punto 13 — Inventario no sincroniza al entrar abastecimientos (Homero)
- `9db7327` · estabiliza entradas/abastecimiento · **directo**
- `ad4a7e4` · NPF | 30, 18, 19, 23 · **directo**

### Punto 14 — Aprobar abastecimiento CEDIS (punto de venta)
- `8c48f17` · decimales + origen CEDIS · **directo**

### Punto 15 — 'insidencias' → 'incidencias'
- `bce8c87` · renombre completo · **directo**

### Punto 16 — Saldo en OC al eliminar producto
- `6d55003` · totales con gastos + override admin OC · **parcial**

### Punto 17 — Compra directa: entrada duplica cantidad
- `67d3ff3` · condición de carrera / duplicado · **directo**

### Punto 18 — Tipificación de incidencias
- `6278945` · tipificación vs descripción (bloqueo) · **directo**

### Punto 19 — Gastos en total de OC
- `6d55003` · totales con gastos · **directo**

### Punto 20 — Histórico de compras
- **sin evidencia** *(existe `30e21f0` histórico por producto_id; no asegura “compras”)*

### Punto 21 — Quitar almacén origen
- `8c48f17` · decimales + origen CEDIS · **parcial**

---

## 3) Cambios fuera de los 21 puntos (bloques no mapeados)
Conjunto de commits que no se justifica directamente con el Excel inicial; típicamente corresponde a extensiones de alcance (app, embarque/reparto, idempotencia, PDF, pricing, prelación).

### 3.1 Prelación + idempotencia (pagos)
- `d522e79`, `ac64b4a`, `7aaa172`, `3335156`

### 3.2 App / embarque / reparto / ruta-app (flujo completo)
- `a92ccca`, `29769c7`, `941e05a`, `e50ddda`, `f0e10d1`, `3e23242`, `7a5dbef`, `76ec81b`, `afe4ac4`, `8fc78b5`, `a3d1c8e`, `fafe206`, `e2c53b6`, etc.

### 3.3 PDF (corte)
- `d19c37e`, `ecd90ef`

### 3.4 Pricing / reglas / exposición de precios
- `5e47b1d`, `6a6aa35`, `7dd8713`, `5ade6a7`, `e878229`

### 3.5 Traspasos (robustez/concurrencia)
- `c0e612d`, `4ac36d3`, `3b2c135`, `0b995b2`, `5286e9d`

---

## 4) Commit destacado: `ad4a7e4` (NPF | 30, 18, 19, 23)

### 4.1 Archivos tocados
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

### 4.2 Cambios funcionales (resumen)
- Gestión de pedidos/rutas: `listar_preventas_con_detalles_carga` resuelve el almacén desde la ruta (`almacen_embarque`) y no desde `user.almacen`
- Ventas (serializer): inclusión de `condicion_pago` para distinguir contado/crédito en listados
- Transformaciones/merma: asignación FIFO automática de lotes en merma cuando no llegan lotes explícitos + validaciones de stock
- Abastecimiento/entradas: validaciones de costo unitario + vencimiento + selección de producto por id
- Inventario lote/compra: robustez en cálculo de vencimiento
- Traspaso: `select_for_update` + validación de inventario insuficiente

### 4.3 Cruce con puntos del Excel
- **directo**: 6, 8, 9, 13
- **no principal**: 18 y 19 (más representados por `6278945` y `6d55003`)

---

## 5) Guía corta de pruebas (Postman / curl)

### 5.1 Autenticación
- `POST /api/token/` (JWT)

### 5.2 Prelación (pagos crédito)
- `POST /api/pagos-credito/*/prelacion/` + header `Idempotency-Key`

Ejemplo:
```bash
curl -X POST "$BASE_URL/<base_proveedor>/prelacion/"   -H "Authorization: Bearer $TOKEN"   -H "Content-Type: application/json"   -H "Idempotency-Key: <uuid>"   -d '{"proveedor":123,"cantidad_pagar":"1500.00","metodo_pago":"TRANSFERENCIA","referencia":"FOLIO-ABC-123"}'
```

### 5.3 Docs
- `GET /api/docs/`

### 5.4 Historial de ventas entregadas (app)
- `GET /api/embarques-reparto/historial-ventas/`

---

## 6) Tabla de alcance (Excel vs extras)

| Bloque | Incluido en Excel 21 puntos | Commits clave | Nota |
|---|---:|---|---|
| Correcciones de compras/OC (gastos/override/flujo) | Sí | `6d55003`, `0ca8ad5` | Impacta totales y consistencia |
| Abastecimiento/origen CEDIS/decimales | Sí (14/21 parcial) | `8c48f17` | Origen/decimales y ajustes asociados |
| Tipificación incidencias | Sí | `6278945` | Desbloqueo por mismatch tipificación/desc |
| Renombre insidencia→incidencia | Sí | `bce8c87` | Normalización de nomenclatura |
| Compra directa duplicada (condición de carrera) | Sí | `67d3ff3` | Bug crítico de inventario/entradas |
| Consulta de inventario abierta | Sí | `1b1f422`, `44d3c1a` | Endpoints/consulta global |
| Prelación + idempotencia (pagos) | No (EXTRA) | `d522e79`, `ac64b4a`, `7aaa172`, `3335156` | Endpoint nuevo + robustez concurrente |
| Flujo embarque/reparto/ruta-app | No (EXTRA) | `a92ccca`, `29769c7`, `e50ddda`, `3e23242`, `7a5dbef`, etc. | Módulo operativo adicional |
| PDF (corte) | No (EXTRA) | `d19c37e`, `ecd90ef` | Generación y normalización |
| Pricing global (reglas, exposición, ponderados) | No (EXTRA) | `5e47b1d`, `6a6aa35`, `7dd8713`, `5ade6a7`, `e878229` | Lógica core de precios |
| Abonos globales editar/cancelar por pago_id | No (EXTRA) | `7c55280`, `fa6ffa3` | Administración de pagos globales |
| App/API handoff (Ionic) | No (EXTRA) | `d69b522`, merges app | Contratos para consumo móvil |

---

## Referencias
- Documento interno. (s. f.). *Precio de venta* [PDF proporcionado por el usuario].
