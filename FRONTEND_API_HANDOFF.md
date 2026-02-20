# Frontend API Handoff (Ionic) - Entregas en Ruta

Este documento describe exactamente como consumir los endpoints de reparto/carga que se ajustaron en esta rama.

## 1) Base URL y autenticacion

- Base API: `{{API_URL}}/api`
- Auth: JWT Bearer token
- Header requerido:

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

Referencia de auth:
- `POST /api/token/`
- `POST /api/token/refresh/`

## 2) Credito (clientes/proveedores) - edicion/cancelacion de abonos globales

Estos endpoints se deben usar desde:
- `#/dash/abono-cliente`
- `#/dash/abono-proveedor`
- modales de "Editar/Cancelar pago"

### 2.1 Cliente - editar abono

- `PUT /api/pagos-credito/editar-abono/`

#### Body

```json
{
  "pago_id": 9,
  "cantidad_pagar": "1300.00",
  "pagos": [
    {
      "metodo_pago": 1,
      "monto": "1300.00",
      "referencia": "TRX-1300"
    }
  ]
}
```

Compatibilidad legacy:
- también acepta `pago_anterior_id` en lugar de `pago_id`.
- `credito` es opcional; si no se manda, backend lo infiere por `pago_id`.

#### Response 200

```json
{
  "detail": "Abono actualizado exitosamente.",
  "data": { "...credito actualizado..." }
}
```

#### Response 400 (ejemplos)

```json
{"detail":"El pago especificado no existe.","error_code":"ERROR_EDITAR_ABONO"}
```

```json
{"detail":"Debe proporcionar pago_id (o pago_anterior_id para compatibilidad).","error_code":"ERROR_EDITAR_ABONO"}
```

---

### 2.2 Cliente - cancelar abono

- `POST /api/pagos-credito/cancelar-abono/`

#### Body

```json
{
  "pago_id": 9,
  "motivo": "Error de captura"
}
```

`motivo` es opcional.

#### Response 200

```json
{
  "detail": "Abono cancelado exitosamente.",
  "data": {
    "pago_id_cancelado": 9,
    "credito_id": 342,
    "monto_revertido": 1300.0,
    "nuevo_adeudo": 915.3
  }
}
```

---

### 2.3 Proveedor - editar abono (NUEVO)

- `PUT /api/pagos-credito-proveedor/editar-abono/`

#### Body

```json
{
  "pago_id": 25,
  "cantidad_pagar": "500.00",
  "pagos": [
    {
      "metodo_pago": 2,
      "monto": "500.00",
      "referencia": "TRX-500-EDIT"
    }
  ]
}
```

Compatibilidad:
- acepta `pago_anterior_id`.
- `credito` opcional (se infiere por `pago_id`).

#### Response 200

```json
{
  "detail": "Abono actualizado exitosamente.",
  "data": { "...credito proveedor actualizado..." }
}
```

---

### 2.4 Proveedor - cancelar abono (NUEVO)

- `POST /api/pagos-credito-proveedor/cancelar-abono/`

#### Body

```json
{
  "pago_id": 25,
  "motivo": "Pago duplicado"
}
```

#### Response 200

```json
{
  "detail": "Abono cancelado exitosamente.",
  "data": {
    "pago_id_cancelado": 25,
    "credito_id": 61,
    "proveedor": "EL BALLENERO",
    "monto_revertido": 500.0,
    "nuevo_adeudo": 69500.0
  }
}
```

---

### 2.5 Reglas de UI para el frontend

- No construir payloads por "nota de crédito"; usar `pago_id` del registro de pago.
- En modales de edición, precargar:
  - `monto` actual del pago
  - `metodo_pago` actual
  - `referencia` actual
- Al confirmar:
  - deshabilitar botón mientras la request está en progreso
  - refrescar:
    - tabla de operaciones de pago
    - estadísticos (`total_pagado`, `adeudo`)
    - detalle de créditos
- En caso de error, mostrar `detail` y no solo status code.

## 3) Endpoint actualizado: pedidos en fase PROGRAMADO

### `GET /api/embarques/preventas-detalles/`

Sirve para listar preventas pendientes de carga para la ruta (ahora soporta `fase=PROGRAMADO` como alias de `PRE VENTA`).

### Query params

- `ruta_id` (opcional, `int`):
  - si no se manda, backend toma la ruta asignada al usuario autenticado.
  - si el usuario no tiene ruta asignada, responde `400`.
- `fase` (opcional, `string`):
  - usar `PROGRAMADO` para la app.
  - backend lo normaliza internamente a `PRE VENTA`.
- `solo_productos` (opcional, `true|false`):
  - `false` (default): devuelve preventas + productos.
  - `true`: devuelve productos agrupados.

### Ejemplo de consumo recomendado

```http
GET /api/embarques/preventas-detalles/?fase=PROGRAMADO
```

### Response 200 (modo preventas)

```json
{
  "preventas": [
    {
      "id": 124,
      "codigo": "PREV-00000124",
      "is_total_cargado": false,
      "estatus_pedido": "PROGRAMADO",
      "cliente": {
        "id": 9,
        "nombre_completo": "Cliente Demo"
      },
      "ruta": {
        "id": 3,
        "nombre": "Ruta Norte",
        "codigo": "RUTA-NTE"
      },
      "productos": [
        {
          "producto_id": 55,
          "nombre": "Garrafon 20L",
          "codigo": "GAR-20",
          "unidad": "Pieza",
          "unidad_clave": "H87",
          "cantidad": 4,
          "cantidad_total": 4,
          "cantidad_cargada": 0,
          "cantidad_entregada": 0,
          "cantidad_logistica": 0,
          "cantidad_inventario": 180.0,
          "is_cargado": false
        }
      ]
    }
  ]
}
```

Response 200 (modo `solo_productos=true`):

```json
{
  "productos": [
    {
      "producto_id": 55,
      "nombre": "Garrafon 20L",
      "precio_unitario": "45.00",
      "codigo": "GAR-20",
      "unidad": "Pieza",
      "unidad_clave": "H87",
      "cantidad_total": 18
    }
  ]
}
```

### Errores comunes

- `400 {"detail": "ruta_id es un parámetro requerido"}`
- `400 {"detail": "ruta_id debe ser un número entero"}`
- `400 {"detail": "ruta_id no encontrada o inactiva"}`
- `400 {"detail": "No hay almacén de pedidos configurado para la ruta."}`

## 4) Endpoint actualizado: entrega de producto en ruta

### `POST /api/reparto/entrega-producto/`

No es endpoint nuevo; es el endpoint existente, extendido para:
- validar responsable de ruta/encargado de embarque,
- registrar movimientos de inventario por entrega,
- registrar devoluciones como traspaso,
- levantar incidencia por devoluciones u observaciones.

### Body (request)

```json
{
  "venta": 124,
  "observaciones": "Cliente reporta 1 dañado",
  "productos": [
    {
      "producto": 55,
      "cantidad_entregada": "3.000000",
      "devolucion": "1.000000",
      "observacion": "1 pieza rota"
    },
    {
      "producto": 56,
      "cantidad": "2.000000"
    }
  ]
}
```

### Contrato por producto

- `producto` (`int`, requerido): id del producto.
- `cantidad` (`decimal`, opcional): compatibilidad con front anterior.
- `cantidad_entregada` (`decimal`, opcional recomendado): cantidad realmente entregada.
- `devolucion` (`decimal`, opcional, default `0`): cantidad devuelta.
- `observacion` (`string`, opcional): observación por línea.

Regla obligatoria:
- Debe venir al menos uno: `cantidad` o `cantidad_entregada`.

Reglas de validación importantes:
- `venta` debe ser preventa (`was_preventa=True`).
- Solo el responsable de la ruta puede confirmar (si ruta tiene `asignado`).
- Si el embarque tiene `encargado`, debe coincidir con el usuario autenticado.
- El producto debe pertenecer a la venta.
- No se permiten negativos.
- `cantidad_entregada + devolucion <= cantidad pedida`.
- Si `devolucion > 0`, se requiere motivo (`observacion` en la línea o `observaciones` global).
- Para devoluciones, la ruta debe tener almacén de tara configurado.
- Debe existir stock suficiente en almacén de pedidos de ruta.

### Response 200

```json
{
  "success": true,
  "message": "Entrega registrada para venta PREV-00000124",
  "venta_id": 124,
  "venta_codigo": "PREV-00000124",
  "productos_procesados": 2,
  "incidencia_id": 89
}
```

Notas:
- `incidencia_id` será `null` si no hubo devoluciones ni observaciones globales.
- Si existe, el front puede mostrar un badge/alerta: "Se creó incidencia".
- Si una línea se entrega parcialmente, esa línea queda `is_entregado=false` y la venta puede quedar pendiente.

### Errores 400

Error de esquema:

```json
{
  "detail": "Datos inválidos",
  "errors": {
    "productos": [
      {
        "non_field_errors": [
          "Debe enviar 'cantidad' o 'cantidad_entregada'."
        ]
      }
    ]
  }
}
```

Error de negocio:

```json
{
  "detail": "Error al registrar entrega: Solo el responsable de la ruta puede confirmar entregas."
}
```

## 4.1) Endpoint de check-in con compatibilidad legacy

### `POST /api/embarques-reparto/checkin-producto/`

Se mantiene compatibilidad con el flujo web actual y con flujo estricto app:

- `auto_iniciar_reparto=true` (default):
  - mantiene comportamiento legacy,
  - al terminar check-in cambia el embarque a `REPARTO` y registra `fecha_salida`.
- `auto_iniciar_reparto=false`:
  - solo registra check-in/carga,
  - conserva el embarque en `PROGRAMADO`,
  - el inicio de ruta se hace luego con `POST /api/embarques-reparto/iniciar/`.

Body mínimo:

```json
{
  "embarque": 25,
  "ventas": [
    {
      "venta": 510,
      "productos": [
        {"producto": 13, "check": true},
        {"producto": 155, "check": true}
      ]
    }
  ],
  "productos_tara": [],
  "auto_iniciar_reparto": false
}
```

Respuesta relevante:
- `fase`
- `auto_iniciar_reparto`

## 5) Flujo sugerido para Ionic

## Paso 1. Obtener embarque activo del chofer (programado o en reparto)

- Llamar `GET /api/embarques-reparto/pedidos-usuario/` sin parámetros.
- Comportamiento:
  - si existe `REPARTO` activo para ese usuario/ruta, devuelve ese.
  - si no existe, devuelve el más reciente en `PROGRAMADO`.
- Para forzar fase específica:
  - `GET /api/embarques-reparto/pedidos-usuario/?fase=PROGRAMADO`
  - `GET /api/embarques-reparto/pedidos-usuario/?fase=REPARTO`

## Paso 2. Listar pedidos programados (pantalla de carga)

- Llamar `GET /api/embarques/preventas-detalles/?fase=PROGRAMADO`.
- Renderizar tarjetas por preventa.
- Usar `productos[*].cantidad` como base para captura de entrega/devolución.

## Paso 3. Capturar entrega por pedido

Por cada producto capturar:
- `cantidad_entregada`
- `devolucion` (opcional)
- `observacion` (opcional)

Reglas UI recomendadas:
- validar en cliente que `entregada + devolucion <= cantidad`.
- si `devolucion > 0`, exigir `observacion`.

## Paso 4. Confirmar entrega

- Enviar `POST /api/reparto/entrega-producto/`.
- Si `success=true`, retirar pedido de lista o refrescar listado.
- Si llega `incidencia_id`, mostrar estado de incidencia creada.

## Paso 5. Resolver incidencias de devolución (admin/operativo)

### `POST /api/incidencias/atender-lote/`

Permite cerrar el lote de incidencia y opcionalmente mover inventario por resolución:
- `REASIGNACION` (reubica a almacén destino)
- `RETORNO_ALMACEN` (retorna a concentrado o destino indicado)

Body ejemplo:

```json
{
  "lotes": [
    {
      "incidencia_lote_id": 55,
      "tipificacion": "Producto danado",
      "nota": "Se reubica a inventario ruta",
      "accion": "REASIGNACION",
      "almacen_destino_id": 37
    }
  ]
}
```

Notas:
- `accion` y `almacen_destino_id` son opcionales (compatibles con flujo anterior).
- Si `accion=RETORNO_ALMACEN` y no envías `almacen_destino_id`, usa `CONCENTRADO DE RUTAS`.

## Paso 6. Manejo de reintentos

- Evitar doble tap en botón "Confirmar entrega".
- Si falla por red, permitir reintento manual.
- No hacer retry automático ciego porque el endpoint sí genera movimientos.

## 6) Implementacion base en Ionic/Angular

JWT interceptor (recomendado para no repetir headers):

```ts
// auth.interceptor.ts
import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { AuthStorageService } from './auth-storage.service';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthStorageService);
  const token = auth.getAccessToken();

  if (!token) return next(req);

  const cloned = req.clone({
    setHeaders: { Authorization: `Bearer ${token}` }
  });
  return next(cloned);
};
```

```ts
// reparto-api.service.ts
import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

export interface ProductoEntregaPayload {
  producto: number;
  cantidad?: string;
  cantidad_entregada?: string;
  devolucion?: string;
  observacion?: string;
}

export interface EntregaPayload {
  venta: number;
  observaciones?: string;
  productos: ProductoEntregaPayload[];
}

export interface EntregaResponse {
  success: boolean;
  message: string;
  venta_id: number;
  venta_codigo: string;
  productos_procesados: number;
  incidencia_id: number | null;
}

@Injectable({ providedIn: 'root' })
export class RepartoApiService {
  private baseUrl = `${environment.apiUrl}/api`;

  constructor(private http: HttpClient) {}

  getPedidosProgramados(rutaId?: number): Observable<any> {
    let params = new HttpParams().set('fase', 'PROGRAMADO');
    if (rutaId) params = params.set('ruta_id', String(rutaId));
    return this.http.get(`${this.baseUrl}/embarques/preventas-detalles/`, { params });
  }

  registrarEntrega(payload: EntregaPayload): Observable<EntregaResponse> {
    return this.http.post<EntregaResponse>(`${this.baseUrl}/reparto/entrega-producto/`, payload);
  }
}
```

## 7) Checklist rapido para frontdev

- Token JWT vigente en cada request.
- Enviar decimales como string (`"1.000000"`), no como float JS.
- En entrega, siempre enviar por producto: `producto` + (`cantidad_entregada` o `cantidad`).
- Si hay devolución, enviar `devolucion`.
- Mostrar `detail` del error backend tal como llega.
- Manejar `incidencia_id` en respuesta exitosa.
