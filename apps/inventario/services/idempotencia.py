import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.inventario.models import OperacionIdempotente


class IdempotenciaError(Exception):
    code = "IDEMPOTENCY_ERROR"
    http_status = 400

    def __init__(self, detail):
        super().__init__(detail)
        self.detail = detail


class IdempotenciaConflict(IdempotenciaError):
    code = "IDEMPOTENCY_CONFLICT"
    http_status = 409


class IdempotenciaInProgress(IdempotenciaError):
    code = "IDEMPOTENCY_IN_PROGRESS"
    http_status = 409


class IdempotenciaInvalidKey(IdempotenciaError):
    code = "IDEMPOTENCY_KEY_INVALID"
    http_status = 400


@dataclass
class IdempotenciaAcquireResult:
    operacion: OperacionIdempotente
    replay: bool
    replay_payload: dict | None = None
    replay_status: int | None = None


def _normalizar(valor):
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, dict):
        return {k: _normalizar(v) for k, v in sorted(valor.items())}
    if isinstance(valor, (list, tuple)):
        return [_normalizar(v) for v in valor]
    return valor


def construir_request_hash(payload):
    payload_normalizado = _normalizar(payload)
    raw = json.dumps(payload_normalizado, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def resolver_idempotency_key(request, request_hash):
    key = (
        request.headers.get("Idempotency-Key")
        or request.headers.get("X-Idempotency-Key")
        or request.data.get("idempotency_key")
    )
    if key is None or str(key).strip() == "":
        # Fallback automático para no romper clientes legacy.
        key = f"auto-{request_hash[:48]}"
    key = str(key).strip()
    if len(key) > 120:
        raise IdempotenciaInvalidKey("Idempotency-Key excede 120 caracteres.")
    return key


def adquirir_operacion(scope, entity_id, idempotency_key, request_hash, user=None):
    entity_id = str(entity_id)
    with transaction.atomic():
        try:
            # Savepoint interno para poder seguir consultando si el create
            # falla por UNIQUE sin romper la transacción externa.
            with transaction.atomic():
                operacion = OperacionIdempotente.objects.create(
                    scope=scope,
                    entity_id=entity_id,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    estado=OperacionIdempotente.ESTADO_IN_PROGRESS,
                    created_by=user,
                    updated_by=user,
                )
            return IdempotenciaAcquireResult(operacion=operacion, replay=False)
        except IntegrityError:
            try:
                operacion = (
                    OperacionIdempotente.objects
                    .select_for_update()
                    .get(
                        scope=scope,
                        entity_id=entity_id,
                        idempotency_key=idempotency_key,
                        status_model=OperacionIdempotente.STATUS_MODEL_ACTIVE,
                    )
                )
            except OperacionIdempotente.DoesNotExist:
                raise IdempotenciaConflict(
                    "Idempotency-Key en conflicto y operación no recuperable."
                )

            if operacion.request_hash != request_hash:
                raise IdempotenciaConflict(
                    "Idempotency-Key ya fue usado con un payload diferente."
                )

            if (
                operacion.estado == OperacionIdempotente.ESTADO_COMPLETED
                and operacion.response_payload
            ):
                payload = dict(operacion.response_payload)
                payload["idempotent_replay"] = True
                payload.setdefault("code", "IDEMPOTENT_REPLAY")
                return IdempotenciaAcquireResult(
                    operacion=operacion,
                    replay=True,
                    replay_payload=payload,
                    replay_status=operacion.http_status or 200,
                )

            if operacion.estado == OperacionIdempotente.ESTADO_IN_PROGRESS:
                raise IdempotenciaInProgress(
                    "La operación con este Idempotency-Key está en progreso."
                )

            # Si estaba FAILED (o incompleta), permitir reintento controlado.
            operacion.estado = OperacionIdempotente.ESTADO_IN_PROGRESS
            operacion.error_message = None
            operacion.response_payload = None
            operacion.http_status = None
            operacion.completed_at = None
            operacion.updated_by = user
            operacion.save(
                update_fields=[
                    "estado",
                    "error_message",
                    "response_payload",
                    "http_status",
                    "completed_at",
                    "updated_by",
                    "updated_at",
                ]
            )
            return IdempotenciaAcquireResult(operacion=operacion, replay=False)


def completar_operacion(operacion_id, response_payload, http_status=200, user=None):
    with transaction.atomic():
        operacion = OperacionIdempotente.objects.select_for_update().get(id=operacion_id)
        operacion.estado = OperacionIdempotente.ESTADO_COMPLETED
        operacion.response_payload = response_payload
        operacion.http_status = http_status
        operacion.completed_at = timezone.now()
        operacion.error_message = None
        operacion.updated_by = user
        operacion.save(
            update_fields=[
                "estado",
                "response_payload",
                "http_status",
                "completed_at",
                "error_message",
                "updated_by",
                "updated_at",
            ]
        )


def fallar_operacion(operacion_id, error_message, http_status=400, user=None):
    with transaction.atomic():
        operacion = OperacionIdempotente.objects.select_for_update().get(id=operacion_id)
        operacion.estado = OperacionIdempotente.ESTADO_FAILED
        operacion.error_message = str(error_message)
        operacion.http_status = http_status
        operacion.completed_at = timezone.now()
        operacion.updated_by = user
        operacion.save(
            update_fields=[
                "estado",
                "error_message",
                "http_status",
                "completed_at",
                "updated_by",
                "updated_at",
            ]
        )
