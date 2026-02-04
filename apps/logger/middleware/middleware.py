# apps/logging/middleware.py
import time
import json
import threading
from django.utils.deprecation import MiddlewareMixin  # opcional si quieres compatibilidad
from ..models import RequestLog

# Lista de rutas a ignorar (estáticos, health checks, admin, etc.)
DEFAULT_EXCLUDE_PATHS = (
    '/static/',
    '/media/',
    '/favicon.ico',
    '/health',
    '/metrics',
    '/admin/',
    '/api/redoc/',
    '/api/schema/',
)

# Cabeceras y campos del body que debes filtrar por seguridad
SENSITIVE_HEADERS = {"HTTP_AUTHORIZATION", "AUTHORIZATION", "COOKIE"}
SENSITIVE_BODY_KEYS = {"password", "token", "access_token", "credit_card", "card_number"}


def _get_headers_from_meta(meta):
    headers = {}
    for k, v in meta.items():
        if not isinstance(k, str):
            continue
        # cabeceras HTTP_*
        if k.startswith("HTTP_"):
            header_name = k[5:].replace("_", "-").title()
            headers[header_name] = v
    # Añadir algunos campos comunes
    if meta.get("CONTENT_TYPE"):
        headers["Content-Type"] = meta.get("CONTENT_TYPE")
    if meta.get("CONTENT_LENGTH"):
        headers["Content-Length"] = meta.get("CONTENT_LENGTH")
    return headers


def _filter_sensitive_headers(headers):
    # elimina o enmascara cabeceras sensibles
    filtered = {}
    for k, v in headers.items():
        if any(s.lower() in k.lower() for s in ("authorization", "cookie")):
            filtered[k] = "FILTERED"
        else:
            filtered[k] = v
    return filtered


def _filter_sensitive_body(parsed_body):
    # intenta enmascarar campos en JSON / dicts
    if isinstance(parsed_body, dict):
        out = {}
        for k, v in parsed_body.items():
            if k.lower() in SENSITIVE_BODY_KEYS:
                out[k] = "FILTERED"
            else:
                # si es anidado
                out[k] = _filter_sensitive_body(v)
        return out
    if isinstance(parsed_body, list):
        return [_filter_sensitive_body(i) for i in parsed_body]
    return parsed_body


def _safe_decode_body(request):
    try:
        raw = request.body  # bytes
    except Exception:
        return None
    if not raw:
        return None
    # intenta decodificar
    try:
        text = raw.decode('utf-8')
    except Exception:
        try:
            text = raw.decode('latin-1')
        except Exception:
            # fallback base64 si es binario (opcional)
            import base64
            return {"__base64__": base64.b64encode(raw).decode('ascii')}
    # si es JSON intenta parsear y filtrar
    ct = request.META.get("CONTENT_TYPE", "")
    if "application/json" in ct:
        try:
            parsed = json.loads(text)
            parsed = _filter_sensitive_body(parsed)
            return parsed
        except Exception:
            return text  # cadena JSON inválida, guardar raw
    # para form data simple -> dejarlo tal cual (o parsear request.POST en views)
    return text


class RequestLoggingMiddleware:
    """
    Middleware moderno (callable) que registra solicitudes.
    Añádelo en settings.MIDDLEWARE (mejor al inicio).
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # configuración opcional
        self.exclude_paths = DEFAULT_EXCLUDE_PATHS

    def s__call__(self, request):
        path = request.path
        # excluir rutas innecesarias
        if any(path.startswith(p) for p in self.exclude_paths):
            return self.get_response(request)

        start = time.time()

        # leer body de forma segura
        body = _safe_decode_body(request)
        headers = _get_headers_from_meta(request.META)
        headers = _filter_sensitive_headers(headers)
        # método y querystring
        method = request.method
        query_string = request.META.get('QUERY_STRING', '')

        response = None
        status_code = None
        try:
            response = self.get_response(request)
            status_code = getattr(response, "status_code", None)
            return response
        finally:
            # se ejecuta siempre, incluso si la vista lanzó excepción
            elapsed_ms = int((time.time() - start) * 1000)

            # Preparar datos a guardar. Por cuestiones de rendimiento podrías
            # guardarlo en background o con Celery (recomendado en producción).
            def save_log():
                try:
                    RequestLog.objects.create(
                        method=method,
                        path=path,
                        query_string=query_string,
                        remote_addr=request.META.get('REMOTE_ADDR') or request.META.get('HTTP_X_FORWARDED_FOR'),
                        headers=headers,
                        body=body if isinstance(body, (str, dict, list)) else str(body),
                        content_type=request.META.get("CONTENT_TYPE"),
                        status_code=status_code,
                        response_time_ms=elapsed_ms,
                        user=getattr(request, "user", None) if getattr(request, "user", None) and request.user.is_authenticated else None
                    )
                except Exception:
                    # evitar que fallen las requests por errores de logging
                    import logging
                    logging.getLogger(__name__).exception("Error guardando RequestLog")

            # Opción 1: guardar en background con un thread (rápido, no recomendado para alta carga)
            t = threading.Thread(target=save_log, daemon=True)
            t.start()

            # Opción 2 (alternativa): guardar síncrono
            # save_log()
    
    def __call__(self, request):
        path = request.path

        # saltar rutas excluidas
        if any(path.startswith(p) for p in self.exclude_paths):
            return self.get_response(request)

        start = time.time()
        method = request.method
        query_string = request.META.get('QUERY_STRING', '')
        
        body = request.body.decode('utf-8', errors='ignore') if request.body else ''
        headers = {k: v for k, v in request.META.items() if k.startswith('HTTP_')}
        response = self.get_response(request)
        duration = int((time.time() - start) * 1000)

        # guardar en segundo plano para no frenar la petición
        threading.Thread(
            target=lambda: RequestLog.objects.create(
                method=method,
                query_string=query_string,
                path=path,
                headers=headers,
                remote_addr=request.META.get('REMOTE_ADDR') or request.META.get('HTTP_X_FORWARDED_FOR'),
                body=body[:5000],  # limitar tamaño por seguridad
                status_code=response.status_code,
                response_time_ms=duration,
                user=getattr(request, "user", None) if getattr(request, "user", None) and request.user.is_authenticated else None
            ),
            daemon=True
        ).start()

        return response