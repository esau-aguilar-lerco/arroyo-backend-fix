from rest_framework import status, permissions, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from django.http import HttpResponse
from django.db import transaction
from django.db.models import Sum, Q, Count
from django.core.exceptions import ValidationError
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from io import BytesIO
from datetime import datetime

from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from apps.base.models import BaseModel
from apps.erp.models import Venta, VentaDetalle, Rutas, Almacen
from apps.erp.serializers.embarque.embarque_serializer import (
    EmbarqueSerializer, EmbarqueMiniSerializer, VentasEmbarqueSubidaRutaSerializer
)
from apps.inventario.services.idempotencia import (
    IdempotenciaError,
    adquirir_operacion,
    completar_operacion,
    construir_request_hash,
    fallar_operacion,
    resolver_idempotency_key,
)


"""
============================================================================================
                            VIEWS DE APIS DE EMBARQUE
============================================================================================
"""
def _resolve_ruta_from_payload(payload):
    ruta_data = payload.get('ruta')
    ruta_id = None
    if isinstance(ruta_data, dict):
        ruta_id = ruta_data.get('id')
    elif isinstance(ruta_data, int):
        ruta_id = ruta_data
    elif isinstance(ruta_data, str) and ruta_data.isdigit():
        ruta_id = int(ruta_data)

    if not ruta_id:
        return None

    return (
        Rutas.objects
        .select_related('asignado__almacen', 'almacen_embarque')
        .filter(id=ruta_id, status_model=BaseModel.STATUS_MODEL_ACTIVE)
        .first()
    )


def _resolve_ruta_for_user(request, payload):
    """
    Para usuarios operativos de ruta, evita inconsistencias del front:
    siempre usa su ruta asignada activa y no la ruta enviada en payload.
    """
    user = request.user
    if user and user.is_authenticated and not user.is_superuser and not user.is_staff:
        ruta_usuario = (
            Rutas.objects
            .select_related('asignado__almacen', 'almacen_embarque')
            .filter(asignado=user, status_model=BaseModel.STATUS_MODEL_ACTIVE)
            .order_by('-id')
            .first()
        )
        if ruta_usuario:
            return ruta_usuario
    return _resolve_ruta_from_payload(payload)


def _get_almacen_origen_carga(ruta=None, user=None, explicit_almacen=None):
    if explicit_almacen:
        return explicit_almacen

    concentrado = Almacen.objects.filter(
        nombre__iexact='CONCENTRADO DE RUTAS',
        status_model=BaseModel.STATUS_MODEL_ACTIVE
    ).first()
    if concentrado:
        return concentrado

    if ruta and ruta.asignado and ruta.asignado.almacen:
        return ruta.asignado.almacen
    if user and user.almacen:
        return user.almacen
    if ruta and ruta.almacen_embarque:
        return ruta.almacen_embarque
    return None


def _resolve_embarque_programado_for_user(user):
    """
    Obtiene el embarque PROGRAMADO más reciente para el usuario autenticado.
    Se usa como fallback cuando app no envía embarque_id.
    """
    if not user or not user.is_authenticated:
        return None

    return (
        EmbarqueReparto.objects
        .select_related('ruta')
        .filter(
            status_model=BaseModel.STATUS_MODEL_ACTIVE,
            fase__in=EmbarqueReparto.fases_programado_compat(),
        )
        .filter(Q(encargado=user) | Q(ruta__asignado=user))
        .order_by('-id')
        .first()
    )


def _idempotencia_error_response(exc):
    return Response(
        {
            'detail': exc.detail,
            'code': exc.code,
        },
        status=exc.http_status,
    )


def _safe_fallar_operacion(operacion_id, error_message, http_status, user):
    """
    Evita que un fallo secundario al registrar idempotencia oculte el error real
    de negocio (por ejemplo, transacción marcada para rollback).
    """
    try:
        fallar_operacion(
            operacion_id=operacion_id,
            error_message=error_message,
            http_status=http_status,
            user=user,
        )
    except Exception as fallar_error:
        print(f"⚠️ [IDEMPOTENCIA] No se pudo registrar fallo de operación: {fallar_error}")


def _to_decimal(value):
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _fmt_money(value):
    amount = _to_decimal(value)
    return f"${amount:,.2f}"


def _fmt_datetime(value):
    if value is None:
        return "-"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)


def _build_corte_reparto_lines(response_data):
    corte = response_data.get('corte_reparto') or {}
    encabezado = corte.get('encabezado') or {}
    ventas_corte = corte.get('ventas_corte') or []
    creditos_abonos = corte.get('creditos_abonos') or []
    formas_pago = corte.get('formas_pago') or []
    totales = corte.get('totales') or {}
    abonos_detalle = response_data.get('abonos_detalle') or []
    firmas = corte.get('firmas') or {}

    lines = []
    lines.append("CORTE DE REPARTO")
    lines.append("=" * 130)
    lines.append(
        f"Reparto: #{encabezado.get('reparto_id', '-')}"
        f"   Ruta: {encabezado.get('ruta_codigo', '-') or '-'} - {encabezado.get('ruta_nombre', '-') or '-'}"
    )
    lines.append(
        f"Unidad: {encabezado.get('unidad_codigo', '-') or '-'} - {encabezado.get('unidad_nombre', '-') or '-'}"
        f"   Placas: {encabezado.get('unidad_placas', '-') or '-'}"
    )
    lines.append(
        f"Encargado ruta: {encabezado.get('encargado_nombre', '-') or '-'}"
        f"   Cajero cierre: {encabezado.get('empleado_caja_nombre', '-') or '-'}"
    )
    lines.append(
        f"Fecha salida: {_fmt_datetime(encabezado.get('fecha_reparto'))}"
        f"   Fecha cierre: {_fmt_datetime(encabezado.get('fecha_cierre'))}"
    )
    lines.append("")

    lines.append("VENTAS")
    lines.append("-" * 130)
    lines.append(f"{'VENTA #ID':<18} {'CLIENTE':<42} {'TOTAL':>12} {'PAGO':>12} {'CREDITO':>8} {'SALDO':>12}")
    lines.append("-" * 130)
    if ventas_corte:
        for row in ventas_corte:
            venta_id = row.get('venta_id')
            codigo = row.get('venta_codigo') or '-'
            cliente = row.get('cliente_nombre') or '-'
            total = _fmt_money(row.get('total'))
            pago = _fmt_money(row.get('pago'))
            credito = row.get('credito') or 'NO'
            saldo = _fmt_money(row.get('saldo'))
            lines.append(
                f"#{venta_id} {codigo}"[:18].ljust(18)
                + f" {cliente[:42]:<42} {total:>12} {pago:>12} {credito:>8} {saldo:>12}"
            )
    else:
        lines.append("Sin ventas registradas para este corte.")
    lines.append("")

    lines.append("CREDITOS / ABONOS")
    lines.append("-" * 130)
    lines.append(
        f"{'CREDITO #ID':<12} {'CLIENTE':<28} {'TRANSFER':>12} {'CHEQUE':>10} {'DEPOSITO':>10} {'OTROS':>10} {'ABONO':>12} {'SALDO':>12}"
    )
    lines.append("-" * 130)
    if creditos_abonos:
        for row in creditos_abonos:
            credito_id = row.get('credito_id') or '-'
            cliente = row.get('cliente_nombre') or '-'
            transferencia = _fmt_money(row.get('transferencia'))
            cheque = _fmt_money(row.get('cheque'))
            deposito = _fmt_money(row.get('deposito'))
            otros = _fmt_money(row.get('otros'))
            abono = _fmt_money(row.get('abono_total'))
            saldo = _fmt_money(row.get('saldo'))
            lines.append(
                f"#{credito_id}"[:12].ljust(12)
                + f" {cliente[:28]:<28} {transferencia:>12} {cheque:>10} {deposito:>10} {otros:>10} {abono:>12} {saldo:>12}"
            )
    else:
        lines.append("Sin abonos a credito registrados.")
    lines.append("")

    lines.append("DETALLE DE MOVIMIENTOS DE ABONO")
    lines.append("-" * 130)
    lines.append(f"{'FECHA':<18} {'CLIENTE':<28} {'CREDITO':<10} {'METODO':<18} {'MONTO':>12} {'REFERENCIA':<16} {'USUARIO':<24}")
    lines.append("-" * 130)
    if abonos_detalle:
        for row in abonos_detalle:
            fecha = _fmt_datetime(row.get('created_at'))
            cliente = row.get('cliente_nombre') or '-'
            credito = f"#{row.get('credito_id')}" if row.get('credito_id') else '-'
            metodo = row.get('metodo_pago_nombre') or '-'
            monto = _fmt_money(row.get('monto'))
            referencia = (row.get('referencia') or '-')[:16]
            usuario = (row.get('created_by_nombre') or '-')[:24]
            lines.append(
                f"{fecha[:18]:<18} {cliente[:28]:<28} {credito:<10} {metodo[:18]:<18} {monto:>12} {referencia:<16} {usuario:<24}"
            )
    else:
        lines.append("Sin detalle de abonos para este corte.")
    lines.append("")

    lines.append("FORMAS DE PAGO (VENTAS + ABONOS)")
    lines.append("-" * 130)
    lines.append(f"{'METODO':<30} {'VENTAS':>14} {'ABONOS':>14} {'TOTAL':>14}")
    lines.append("-" * 130)
    if formas_pago:
        for row in formas_pago:
            metodo = row.get('metodo_pago_nombre') or '-'
            ventas_total = _fmt_money(row.get('ventas'))
            abonos_total = _fmt_money(row.get('abonos'))
            total = _fmt_money(row.get('total'))
            lines.append(f"{metodo[:30]:<30} {ventas_total:>14} {abonos_total:>14} {total:>14}")
    else:
        lines.append("Sin movimientos por metodo de pago.")
    lines.append("")

    lines.append("TOTALES")
    lines.append("-" * 130)
    lines.append(f"Total ventas:          {_fmt_money(totales.get('total_ventas'))}")
    lines.append(f"Total cobrado ventas:  {_fmt_money(totales.get('total_cobrado_ventas'))}")
    lines.append(f"Total abonos:          {_fmt_money(totales.get('total_abonos'))}")
    lines.append(f"Total abonos efectivo: {_fmt_money(totales.get('total_abonos_efectivo'))}")
    lines.append(f"Total general:         {_fmt_money(totales.get('total_general'))}")
    lines.append("")
    lines.append("FIRMAS")
    lines.append("-" * 130)
    lines.append(f"Gerente ruta: {firmas.get('gerente_ruta') or '________________________'}")
    lines.append(f"Cajero cierre: {firmas.get('cajero_cierre') or '________________________'}")
    lines.append("")
    lines.append(f"Generado: {_fmt_datetime(datetime.now())}")
    return lines


def _render_corte_pdf(response_data):
    from PIL import Image, ImageDraw, ImageFont

    lines = _build_corte_reparto_lines(response_data)
    page_width, page_height = 1654, 2339
    margin_x, margin_y = 60, 70

    font_path_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ]
    font = None
    for path in font_path_candidates:
        try:
            font = ImageFont.truetype(path, 22)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    # line spacing robusta entre diferentes fuentes
    ascent, descent = font.getmetrics() if hasattr(font, "getmetrics") else (14, 4)
    line_height = max(ascent + descent + 8, 24)
    max_lines_per_page = max((page_height - (margin_y * 2)) // line_height, 1)

    pages = []
    current_index = 0
    total_lines = len(lines)
    while current_index < total_lines:
        page = Image.new("RGB", (page_width, page_height), "white")
        draw = ImageDraw.Draw(page)
        y = margin_y
        end_index = min(current_index + max_lines_per_page, total_lines)
        for idx in range(current_index, end_index):
            draw.text((margin_x, y), lines[idx], fill="black", font=font)
            y += line_height
        pages.append(page)
        current_index = end_index

    buffer = BytesIO()
    pages[0].save(
        buffer,
        format="PDF",
        save_all=True,
        append_images=pages[1:],
        resolution=150.0,
    )
    return buffer.getvalue()

class EmbarqueListCreateAPIView(APIView):
    """
    Vista para listar embarques disponibles y crear nuevos embarques
    """
    # permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Crear nuevo embarque",
        description="Procesa preventas y productos en tara para crear un embarque",
        request=EmbarqueSerializer,
        responses={
            201: inline_serializer(
                name='EmbarqueCreateResponse',
                fields={
                    'success': serializers.BooleanField(),
                    'message': serializers.CharField(),
                    'embarque': EmbarqueSerializer(),
                    'preventas_procesadas': serializers.ListField(child=serializers.IntegerField()),
                    'productos_tara_procesados': serializers.ListField(
                        #child=ProductosTaraAbiertosSerializer()
                    ),
                }
            ),
            400: "Error en los datos proporcionados",
            500: "Error interno del servidor"
        },
        tags=['Embarque']
    )
    
    def post(self, request):
        """
        Crear un nuevo embarque procesando preventas y productos en tara
        """
        from apps.inventario.models import Almacen
        payload = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        ruta = _resolve_ruta_for_user(request, payload)
        if ruta:
            payload['ruta'] = ruta.id

        explicit_almacen = payload.get('almacen_origen', None)
        if explicit_almacen:
            # Si viene un ID, convertirlo a instancia
            if isinstance(explicit_almacen, int) or (isinstance(explicit_almacen, str) and explicit_almacen.isdigit()):
                explicit_almacen = Almacen.objects.filter(id=int(explicit_almacen)).first()
                if not explicit_almacen:
                    return Response(
                        {'detail': 'El almacén de origen no existe.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

        almacen_origen = _get_almacen_origen_carga(
            ruta=ruta,
            user=request.user,
            explicit_almacen=explicit_almacen
        )

        if not almacen_origen:
            return Response(
                {'detail': 'El almacén de origen es obligatorio para crear un embarque.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = EmbarqueSerializer(
            data=payload,
            context={'request': request, 'almacen_origen': almacen_origen}
        )

        if not serializer.is_valid():
            return Response(
                {'detail': 'Datos inválidos', 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        request_hash = construir_request_hash(payload)
        try:
            idempotency_key = resolver_idempotency_key(request, request_hash)
            idempotencia = adquirir_operacion(
                scope='EMBARQUE_CREAR',
                entity_id=ruta.id if ruta else f'user-{request.user.id}',
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                user=request.user,
            )
        except IdempotenciaError as exc:
            return _idempotencia_error_response(exc)

        if idempotencia.replay:
            return Response(
                idempotencia.replay_payload,
                status=idempotencia.replay_status or status.HTTP_200_OK
            )

        try:
            with transaction.atomic():
                embarque_data = serializer.save()
                response_payload = {
                    'success': True,
                    'embarque_id': embarque_data.id,
                    'fase': embarque_data.fase,
                    'idempotency_key': idempotency_key,
                }
                completar_operacion(
                    operacion_id=idempotencia.operacion.id,
                    response_payload=response_payload,
                    http_status=status.HTTP_201_CREATED,
                    user=request.user,
                )
                return Response(response_payload, status=status.HTTP_201_CREATED)
        except (ValidationError, serializers.ValidationError, ValueError) as e:
            _safe_fallar_operacion(
                operacion_id=idempotencia.operacion.id,
                error_message=str(e),
                http_status=status.HTTP_400_BAD_REQUEST,
                user=request.user,
            )
            return Response(
                {
                    'detail': f'Error de validación: {str(e)}',
                    'code': 'EMBARQUE_VALIDATION_ERROR',
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            import traceback
            print(f"❌ [EMBARQUE ERROR] {str(e)}")
            print(f"❌ [EMBARQUE TRACEBACK]\n{traceback.format_exc()}")
            _safe_fallar_operacion(
                operacion_id=idempotencia.operacion.id,
                error_message=str(e),
                http_status=status.HTTP_400_BAD_REQUEST,
                user=request.user,
            )
            return Response(
                {
                    'detail': f'Error interno: {str(e)}',
                    'code': 'EMBARQUE_CREATE_ERROR',
                },
                status=status.HTTP_400_BAD_REQUEST
            )


#LISTAR LAS PREVENTAS A EMBARCAR
@extend_schema(
    summary="Listar preventas con productos pendientes por cargar",
    description="Obtiene las preventas que tienen productos sin cargar, con información detallada de cada producto y su unidad SAT",
    parameters=[
        OpenApiParameter(
            name='ruta_id',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='ID de la ruta para filtrar preventas (opcional)',
            required=False
        ),
        OpenApiParameter(
            name='fase',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Filtrar por fase de la venta (incluye PROGRAMADO para pedidos pendientes de carga)',
            required=False
        ),
    ],
    responses={
        200: inline_serializer(
            name='PreventasConDetallesResponse',
            fields={
                'preventas': inline_serializer(
                    name='PreventaConDetalles',
                    fields={
                        'id': serializers.IntegerField(),
                        'codigo': serializers.CharField(),
                        'cliente': inline_serializer(
                            name='ClienteInfo',
                            fields={
                                'id': serializers.IntegerField(),
                                'nombre_completo': serializers.CharField(),
                            }
                        ),
                        'ruta': inline_serializer(
                            name='RutaInfo',
                            fields={
                                'id': serializers.IntegerField(),
                                'nombre': serializers.CharField(),
                                'codigo': serializers.CharField(),
                            }
                        ),
                        'fase': serializers.CharField(),
                        'total': serializers.DecimalField(max_digits=10, decimal_places=2),
                        'is_total_cargado': serializers.BooleanField(),
                        'estatus_pedido': serializers.CharField(help_text='PROGRAMADO cuando aún no termina la carga'),
                        'productos': inline_serializer(
                            name='ProductoDetalle',
                            fields={
                                'id': serializers.IntegerField(),
                                'unidad': serializers.CharField(help_text="Nombre de la unidad SAT"),
                                'unidad_clave': serializers.CharField(help_text="Clave de la unidad SAT"),
                                'nombre': serializers.CharField(),
                                'codigo': serializers.CharField(),
                                'cantidad_total': serializers.IntegerField(),
                                'is_cargado': serializers.BooleanField(),
                            },
                            many=True
                        ),
                    },
                    many=True
                )
            }
        ),
        400: "Error en los parámetros"
    },
    tags=['Embarque']
)
@api_view(['GET'])
def listar_preventas_con_detalles_carga(request):
    """
    Lista todas las preventas con sus detalles de productos y estado de carga.
    Si solo_productos=true, devuelve solo los productos agrupados con cantidades sumadas.
    """
    try:
        from apps.inventario.models import LoteInventario, EmbarqueReparto
        
        # Obtener parámetros de filtro
        ruta_id = request.query_params.get('ruta_id')
        fase = request.query_params.get('fase', Venta.FASE_PRE_VENTA)
        fase_normalizada = (fase or '').strip().upper()
        modo_programado = fase_normalizada in ['PROGRAMADO', EmbarqueReparto.FASE_CARGA_LEGACY]
        if modo_programado:
            fase = Venta.FASE_PRE_VENTA
        solo_productos = request.query_params.get('solo_productos', '').lower() == 'true'
        user = request.user
        ruta = None
        
        # Construir filtros base
        filtros = {
            'status_model': BaseModel.STATUS_MODEL_ACTIVE,
            'was_preventa': True,
        }
        
        if not ruta_id:
            ruta = (Rutas.objects
                    .select_related('almacen_embarque')
                    .filter(asignado=user, status_model=BaseModel.STATUS_MODEL_ACTIVE)
                    .first())
            if ruta:
                filtros['ruta_id'] = ruta.id
            else:
                return Response(
                    {'detail': 'ruta_id es un parámetro requerido'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            try:
                ruta_id = int(ruta_id)
            except ValueError:
                return Response(
                    {'detail': 'ruta_id debe ser un número entero'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            ruta = (Rutas.objects
                    .select_related('almacen_embarque')
                    .filter(id=ruta_id, status_model=BaseModel.STATUS_MODEL_ACTIVE)
                    .first())
            if not ruta:
                return Response(
                    {'detail': 'ruta_id no encontrada o inactiva'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            filtros['ruta_id'] = ruta.id

        almacen_pedidos = ruta.almacen_embarque
        almacen_origen_carga = _get_almacen_origen_carga(ruta=ruta, user=user)
        print(f"almacen de pedidos (ruta): {ruta.almacen_embarque} | almacen usuario: {user.almacen}")
        
        if not almacen_pedidos:
            return Response(
                {'detail': 'No hay almacén de pedidos configurado para la ruta.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if modo_programado:
            embarque_programado = (
                EmbarqueReparto.objects
                .filter(
                    status_model=BaseModel.STATUS_MODEL_ACTIVE,
                    ruta_id=ruta.id,
                    fase__in=EmbarqueReparto.fases_programado_compat(),
                )
                .order_by('-id')
                .first()
            )
            if not embarque_programado:
                return Response({'preventas': []}, status=status.HTTP_200_OK)

            filtros['id__in'] = embarque_programado.ventas.values_list('id', flat=True)
        else:
            filtros.update({
                'fase': fase,
                'is_total_cargado': False,
            })

        # Query optimizada
        preventas = Venta.objects.filter(
            **filtros
        ).select_related(
            'cliente',
            'ruta',
            'almacen'
        ).prefetch_related(
            'detalles__producto__unidad_sat'
        ).distinct().order_by('-created_at')
        
        # Obtener todos los productos únicos de las preventas
        productos_ids = set()
        for preventa in preventas:
            for detalle in preventa.detalles.all():
                productos_ids.add(detalle.producto_id)
        
     
        # Si solo quieren productos agrupados
        if solo_productos:
            productos_agrupados = {}
            
            for preventa in preventas:
                detalles = preventa.detalles.filter(is_cargado=False)
                
                for detalle in detalles:
                    producto_id = detalle.producto.id
                    
                    if producto_id not in productos_agrupados:
                        productos_agrupados[producto_id] = {
                            'producto_id': producto_id,
                            'nombre': detalle.producto.nombre,
                            'precio_unitario': detalle.precio_unitario,
                            'codigo': detalle.producto.codigo,
                            'unidad': detalle.producto.unidad_sat.nombre if detalle.producto.unidad_sat else 'N/A',
                            'unidad_clave': detalle.producto.unidad_sat.clave if detalle.producto.unidad_sat else 'N/A',
                            'cantidad_total': 0,
                            #'lotes': lotes_por_producto.get(producto_id, []),
                        }
                    
                    productos_agrupados[producto_id]['cantidad_total'] += detalle.cantidad
            
            return Response({'productos': list(productos_agrupados.values())}, status=status.HTTP_200_OK)
        
        # Si quieren preventas con sus productos
        preventas_data = []

        for preventa in preventas:
            if modo_programado:
                detalles = preventa.detalles.filter(cantidad_logistica__gt=0)
                if not detalles.exists():
                    detalles = preventa.detalles.all()
            else:
                detalles = preventa.detalles.filter(is_cargado=False)
            
            if not detalles:
                continue
            
            productos_data = []
            
            for detalle in detalles:
                producto_id = detalle.producto_id
                
                almacen_inventario = (
                    almacen_origen_carga
                    or preventa.almacen
                    or almacen_pedidos
                )

                cantidad_programada = detalle.cantidad_logistica if (detalle.cantidad_logistica or 0) > 0 else detalle.cantidad
                cantidad_cargada = detalle.cantidad_cargada
                if modo_programado and (cantidad_cargada is None or cantidad_cargada <= 0):
                    cantidad_cargada = cantidad_programada

                productos_data.append({
                    'producto_id': producto_id,
                    'nombre': detalle.producto.nombre,
                    'codigo': detalle.producto.codigo,
                    'unidad': detalle.producto.unidad_sat.nombre if detalle.producto.unidad_sat else 'N/A',
                    'unidad_clave': detalle.producto.unidad_sat.clave if detalle.producto.unidad_sat else 'N/A',
                    'cantidad': cantidad_programada if modo_programado else detalle.cantidad,
                    'cantidad_total': cantidad_programada if modo_programado else detalle.cantidad,
                    'precio_unitario': detalle.precio_unitario,
                    'cantidad_cargada': cantidad_cargada,
                    'cantidad_entregada': detalle.cantidad_entregada,
                    'cantidad_logistica': cantidad_programada if modo_programado else detalle.cantidad_logistica,
                    'cantidad_inventario': LoteInventario.objects.filter(
                        producto_id=producto_id,
                        almacen=almacen_inventario,
                        status_model=BaseModel.STATUS_MODEL_ACTIVE
                    ).aggregate(total_cantidad=Sum('cantidad'))['total_cantidad'] or 0.0,
                    'is_cargado': True if modo_programado else detalle.is_cargado,
                    #'lotes': lotes_por_producto.get(producto_id, []),
                })
            
            preventa_data = {
                'id': preventa.id,
                'is_total_cargado': preventa.is_total_cargado,
                'falta_inventario': preventa.falta_inventario,
                'codigo': preventa.codigo,
                'condicion_pago': preventa.condicion_pago,
                'cliente_id': preventa.cliente.id if preventa.cliente else None,
                'cliente_nombre': preventa.cliente.get_full_name if preventa.cliente else 'Sin cliente',
                'cliente': {
                    'id': preventa.cliente.id if preventa.cliente else None,
                    'nombre_completo': preventa.cliente.get_full_name if preventa.cliente else 'Sin cliente',
                },
                'ruta': {
                    'id': preventa.ruta.id if preventa.ruta else None,
                    'nombre': preventa.ruta.nombre if preventa.ruta else 'Sin ruta',
                    'codigo': preventa.ruta.codigo if preventa.ruta else 'Sin código',
                },
                'ruta_id': preventa.ruta.id if preventa.ruta else None,
                'ruta_nombre': preventa.ruta.nombre if preventa.ruta else 'Sin ruta',
                'ruta_codigo': preventa.ruta.codigo if preventa.ruta else 'Sin código',
                'estatus_pedido': 'PROGRAMADO' if modo_programado else ('PROGRAMADO' if not preventa.is_total_cargado else 'CARGADO'),
                'productos': productos_data,
            }
            
            preventas_data.append(preventa_data)
        
        return Response({'preventas': preventas_data}, status=status.HTTP_200_OK)
        
    except Exception as e:
        print(f"❌ [API ERROR] Error al listar preventas con detalles: {str(e)}")
        import traceback
        print(f"❌ [API ERROR] Traceback: {traceback.format_exc()}")
        
        return Response(
            {'detail': f'Error al listar preventas con detalles: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )



"""
============================================================================================
                            VIEWS DE APIS DE EMBARQUE LISTAR Y RETRIEVE
============================================================================================
"""
from rest_framework.pagination import LimitOffsetPagination
from apps.inventario.models import EmbarqueReparto, ProductoEmbarque
from apps.erp.serializers.embarque.embarque_serializer import EmbarqueDetailSerializer


class EmbarqueRepartoListRetrieveAPIView(APIView):
    """
    Vista para listar y obtener detalle de embarques de reparto
    """
    pagination_class = LimitOffsetPagination
    
    @extend_schema(
        summary="Listar embarques de reparto",
        description="Obtiene una lista paginada de embarques de reparto con filtros opcionales",
        parameters=[
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Buscar por nombre de ruta o nombre del encargado',
                required=False
            ),
            OpenApiParameter(
                name='ruta_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Filtrar por ID de ruta',
                required=False
            ),
            OpenApiParameter(
                name='fase',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filtrar por fase (PROGRAMADO, REPARTO, TERMINADO, CANCELADO). CARGA se acepta como alias legacy.',
                required=False
            ),
            OpenApiParameter(
                name='encargado_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Filtrar por ID del encargado',
                required=False
            ),
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Número de resultados por página',
                required=False
            ),
            OpenApiParameter(
                name='offset',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Desplazamiento para paginación',
                required=False
            ),
            OpenApiParameter(
                name='sin_paginacion',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='Si es true, devuelve todos los resultados sin paginar',
                required=False,
                default=False
            ),
        ],
        responses={
            200: EmbarqueMiniSerializer(many=True),
        },
        tags=['Embarque']
    )
    def get(self, request, pk=None):
        """
        Lista embarques o retorna el detalle de uno específico
        """
        if pk:
            return self.retrieve(request, pk)
        
        from django.db.models import Q
        
        # Filtros
        search = request.query_params.get('search', None)
        ruta_id = request.query_params.get('ruta_id', None)
        fase = request.query_params.get('fase', None)
        encargado_id = request.query_params.get('encargado_id', None)
        sin_paginacion = request.query_params.get('sin_paginacion', '').lower() == 'true'
        
        ruta_usuario = None

        # Query base optimizada
        queryset = EmbarqueReparto.objects.select_related(
            'ruta',
            'encargado'
        ).exclude(
            status_model=BaseModel.STATUS_MODEL_DELETE
        ).order_by('-created_at')
        
        # Búsqueda por nombre de ruta o encargado
        if search:
            for termino in [t for t in search.split() if t]:
                queryset = queryset.filter(
                    Q(ruta__nombre__icontains=termino) |
                    Q(ruta__codigo__icontains=termino) |
                    Q(encargado__username__icontains=termino) |
                    Q(encargado__nombre__icontains=termino) |
                    Q(encargado__apellido_paterno__icontains=termino) |
                    Q(encargado__apellido_materno__icontains=termino)
                )
        
        # Aplicar filtros
        if ruta_id:
            queryset = queryset.filter(ruta_id=ruta_id)
        else:
            # Filtrar por la ruta del usuario si no se proporciona ruta_id
            user = request.user
            ruta_usuario = Rutas.objects.filter(asignado=user, status_model=BaseModel.STATUS_MODEL_ACTIVE).first()
            if ruta_usuario:
                queryset = queryset.filter(ruta_id=ruta_usuario.id)
                
                
        if fase:
            fase_normalizada = (fase or '').strip().upper()
            if fase_normalizada == EmbarqueReparto.FASE_CARGA_LEGACY:
                fase_normalizada = EmbarqueReparto.FASE_PROGRAMADO

            if ',' in fase_normalizada:
                fases = [f.strip().upper() for f in fase_normalizada.split(',') if f.strip()]
                fases_normalizadas = []
                for fase_item in fases:
                    if fase_item == EmbarqueReparto.FASE_CARGA_LEGACY:
                        fase_item = EmbarqueReparto.FASE_PROGRAMADO
                    fases_normalizadas.append(fase_item)

                if EmbarqueReparto.FASE_PROGRAMADO in fases_normalizadas:
                    fases_normalizadas.extend(EmbarqueReparto.fases_programado_compat())

                queryset = queryset.filter(fase__in=list(dict.fromkeys(fases_normalizadas)))
            else:
                if fase_normalizada == EmbarqueReparto.FASE_PROGRAMADO:
                    queryset = queryset.filter(fase__in=EmbarqueReparto.fases_programado_compat())
                else:
                    queryset = queryset.filter(fase=fase_normalizada)

            if (
                fase_normalizada == EmbarqueReparto.FASE_PROGRAMADO
                and not ruta_id
                and ruta_usuario
            ):
                latest_programado_id = queryset.order_by('-id').values_list('id', flat=True).first()
                if latest_programado_id:
                    queryset = queryset.filter(id=latest_programado_id)
                else:
                    queryset = queryset.none()

        if encargado_id:
            queryset = queryset.filter(encargado_id=encargado_id)
        
        # Si se solicita sin paginación, devolver todos los resultados
        if sin_paginacion:
            serializer = EmbarqueMiniSerializer(queryset, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        # Paginación
        paginator = LimitOffsetPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = EmbarqueMiniSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = EmbarqueMiniSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @extend_schema(
        summary="Obtener detalle de embarque",
        description="Obtiene el detalle completo de un embarque con sus productos y lotes. Usar include_ventas=true para incluir las ventas con sus productos cargados.",
        parameters=[
            OpenApiParameter(
                name='include_ventas',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='Si es true, incluye las ventas del embarque con sus productos cargados',
                required=False,
                default=False
            )
        ],
        responses={
            200: EmbarqueDetailSerializer,
            404: "Embarque no encontrado"
        },
        tags=['Embarque']
    )
    def retrieve(self, request, pk):
        """
        Obtiene el detalle completo de un embarque
        """
        try:
            from django.db.models import Prefetch
            from apps.inventario.models import ProductoEmbarque
            
            # Obtener parámetro include_ventas
            include_ventas = request.query_params.get('include_ventas', '').lower() == 'true'
            
            # Query base con productos
            queryset = EmbarqueReparto.objects.select_related(
                'ruta',
                'encargado',
                'created_by'
            ).prefetch_related(
                Prefetch(
                    'productos',
                    queryset=ProductoEmbarque.objects.select_related(
                        'producto__unidad_sat',
                        'preventa'
                    ).prefetch_related('lotes__lote', 'preventa__detalles__producto__unidad_sat')
                )
            )
            
            # Solo agregar prefetch de ventas si se solicita
            if include_ventas:
                queryset = queryset.prefetch_related('ventas__cliente')
            
            embarque = queryset.get(pk=pk)
            
            if embarque.status_model == BaseModel.STATUS_MODEL_DELETE:
                return Response(
                    {'detail': 'Embarque no encontrado.'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            serializer = EmbarqueDetailSerializer(embarque, context={'include_ventas': include_ventas})
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except EmbarqueReparto.DoesNotExist:
            return Response(
                {'detail': 'Embarque no encontrado.'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'detail': str(e), 'error_code': 'ERROR_RETRIEVE_EMBARQUE'},
                status=status.HTTP_400_BAD_REQUEST
            )


@extend_schema(
    summary="Iniciar reparto de embarque",
    description="Actualiza la fase del embarque a REPARTO y registra la fecha de salida",
    request=inline_serializer(
        name='IniciarRepartoRequest',
        fields={
            'embarque_id': serializers.IntegerField(required=False, help_text="ID del embarque a iniciar (opcional para app, se resuelve por usuario)"),
            'encargado_id': serializers.IntegerField(required=False, help_text="ID del encargado del reparto (opcional)"),
            'nota': serializers.CharField(required=False, help_text="Nota adicional (opcional)"),
        }
    ),
    responses={
        200: inline_serializer(
            name='IniciarRepartoResponse',
            fields={
                'success': serializers.BooleanField(),
                'message': serializers.CharField(),
                'embarque_id': serializers.IntegerField(),
                'fase': serializers.CharField(),
                'fecha_salida': serializers.DateTimeField(),
            }
        ),
        400: "Error en los datos proporcionados",
        404: "Embarque no encontrado"
    },
    tags=['Embarque']
)
@api_view(['POST'])
def iniciar_reparto(request):
    """
    Inicia el reparto de un embarque actualizando su fase a REPARTO y registrando la fecha de salida
    """
    from django.utils import timezone
    
    embarque_id = request.data.get('embarque_id')
    nota = request.data.get('nota', None)

    # Compatibilidad app: si no envían embarque_id, resolver el PROGRAMADO del usuario.
    if not embarque_id:
        embarque_programado = _resolve_embarque_programado_for_user(request.user)
        if embarque_programado:
            embarque_id = embarque_programado.id

    if not embarque_id:
        return Response(
            {'detail': 'No hay embarque PROGRAMADO para el usuario actual.', 'code': 'EMBARQUE_PROGRAMADO_NOT_FOUND'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        embarque_id = int(embarque_id)
    except (TypeError, ValueError):
        return Response(
            {'detail': 'embarque_id inválido', 'code': 'EMBARQUE_ID_INVALID'},
            status=status.HTTP_400_BAD_REQUEST
        )

    payload_idempotencia = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
    payload_idempotencia['embarque_id'] = embarque_id
    request_hash = construir_request_hash(payload_idempotencia)
    try:
        idempotency_key = resolver_idempotency_key(request, request_hash)
        idempotencia = adquirir_operacion(
            scope='EMBARQUE_INICIAR_REPARTO',
            entity_id=embarque_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            user=request.user,
        )
    except IdempotenciaError as exc:
        return _idempotencia_error_response(exc)
    except Exception as exc:
        return Response(
            {
                'detail': f'Error al preparar idempotencia de iniciar reparto: {str(exc)}',
                'code': 'IDEMPOTENCY_RUNTIME_ERROR',
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    if idempotencia.replay:
        return Response(
            idempotencia.replay_payload,
            status=idempotencia.replay_status or status.HTTP_200_OK
        )
    
    try:
        embarque = EmbarqueReparto.objects.select_related('ruta').get(
            pk=embarque_id,
            status_model=BaseModel.STATUS_MODEL_ACTIVE
        )
        
        # Validar que el embarque esté en fase PROGRAMADO (legacy CARGA).
        if embarque.fase not in EmbarqueReparto.fases_programado_compat():
            _safe_fallar_operacion(
                operacion_id=idempotencia.operacion.id,
                error_message=(
                    f'El embarque debe estar en fase PROGRAMADO para iniciar reparto. '
                    f'Fase actual: {embarque.fase}'
                ),
                http_status=status.HTTP_400_BAD_REQUEST,
                user=request.user,
            )
            return Response(
                {
                    'detail': f'El embarque debe estar en fase PROGRAMADO para iniciar reparto. Fase actual: {embarque.fase}',
                    'code': 'EMBARQUE_INVALID_PHASE',
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        reparto_activo_misma_ruta = (
            EmbarqueReparto.objects
            .filter(
                status_model=BaseModel.STATUS_MODEL_ACTIVE,
                ruta_id=embarque.ruta_id,
                fase=EmbarqueReparto.FASE_REPARTO,
            )
            .exclude(id=embarque.id)
            .order_by('-id')
            .first()
        )
        if reparto_activo_misma_ruta:
            _safe_fallar_operacion(
                operacion_id=idempotencia.operacion.id,
                error_message=(
                    f'La ruta {embarque.ruta.codigo if embarque.ruta else embarque.ruta_id} '
                    f'ya tiene un reparto activo (ID {reparto_activo_misma_ruta.id}).'
                ),
                http_status=status.HTTP_400_BAD_REQUEST,
                user=request.user,
            )
            return Response(
                {
                    'detail': (
                        f'La ruta {embarque.ruta.codigo if embarque.ruta else embarque.ruta_id} '
                        f'ya tiene un reparto activo (ID {reparto_activo_misma_ruta.id}).'
                    ),
                    'code': 'REPARTO_ALREADY_ACTIVE_FOR_ROUTE',
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Actualizar fase y fecha de salida
        embarque.fase = EmbarqueReparto.FASE_REPARTO
        embarque.fecha_salida = timezone.now()
        
        # Actualizar encargado si se proporciona
        #if encargado_id:
        #    try:
        #        encargado = Usuario.objects.get(pk=encargado_id)
        #        embarque.encargado = encargado
        #    except Usuario.DoesNotExist:
        #        return Response(
        #            {'detail': 'Encargado no encontrado'},
        #            status=status.HTTP_404_NOT_FOUND
        #        )
        
        # Agregar nota si se proporciona
        if nota:
            embarque.nota = f"{embarque.nota or ''}\n[INICIO REPARTO]: {nota}".strip()
        else:
            embarque.nota = f"{embarque.nota or ''}\n[INICIO REPARTO] POR {request.user.full_name()}".strip()
        embarque.save(update_fields=['fase', 'fecha_salida', 'encargado', 'nota', 'updated_at'])
        
        # Obtener nombre del encargado
        encargado_nombre = None
        if embarque.encargado:
            encargado_nombre = embarque.encargado.full_name() if callable(embarque.encargado.full_name) else embarque.encargado.full_name
        
        response_payload = {
            'success': True,
            'message': f'Reparto iniciado exitosamente para embarque {embarque_id}',
            'embarque_id': embarque.id,
            'fase': embarque.fase,
            'fecha_salida': embarque.fecha_salida.strftime('%Y-%m-%d %H:%M:%S'),
            'ruta_nombre': embarque.ruta.nombre if embarque.ruta else None,
            'encargado_nombre': encargado_nombre,
            'idempotency_key': idempotency_key,
        }
        completar_operacion(
            operacion_id=idempotencia.operacion.id,
            response_payload=response_payload,
            http_status=status.HTTP_200_OK,
            user=request.user,
        )
        return Response(response_payload, status=status.HTTP_200_OK)
        
    except EmbarqueReparto.DoesNotExist:
        _safe_fallar_operacion(
            operacion_id=idempotencia.operacion.id,
            error_message='Embarque no encontrado',
            http_status=status.HTTP_404_NOT_FOUND,
            user=request.user,
        )
        return Response(
            {'detail': 'Embarque no encontrado', 'code': 'EMBARQUE_NOT_FOUND'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        _safe_fallar_operacion(
            operacion_id=idempotencia.operacion.id,
            error_message=str(e),
            http_status=status.HTTP_400_BAD_REQUEST,
            user=request.user,
        )
        return Response(
            {'detail': str(e), 'code': 'ERROR_INICIAR_REPARTO'},
            status=status.HTTP_400_BAD_REQUEST
        )


@extend_schema(
    summary="Finalizar reparto de embarque",
    description="Actualiza la fase del embarque a TERMINADO, finalizando el reparto",
    request=inline_serializer(
        name='FinalizarRepartoRequest',
        fields={
            'reparto_id': serializers.IntegerField(help_text="ID del embarque/reparto a finalizar"),
        }
    ),
    responses={
        200: inline_serializer(
            name='FinalizarRepartoResponse',
            fields={
                'success': serializers.BooleanField(),
                'message': serializers.CharField(),
                'reparto_id': serializers.IntegerField(),
                'fase': serializers.CharField(),
            }
        ),
        400: "Error en los datos proporcionados",
        404: "Reparto no encontrado"
    },
    tags=['Embarque']
)
@api_view(['POST'])
def finalizar_reparto(request):
    from django.utils import timezone
    reparto_id = request.data.get('reparto_id') or request.data.get('embarque_id')
    if not reparto_id:
        return Response(
            {'detail': 'reparto_id es requerido'},
            status=status.HTTP_400_BAD_REQUEST
        )

    request_hash = construir_request_hash(request.data)
    try:
        idempotency_key = resolver_idempotency_key(request, request_hash)
        idempotencia = adquirir_operacion(
            scope='EMBARQUE_FINALIZAR_REPARTO',
            entity_id=reparto_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            user=request.user,
        )
    except IdempotenciaError as exc:
        return _idempotencia_error_response(exc)
    except Exception as exc:
        return Response(
            {
                'detail': f'Error al preparar idempotencia de finalizar reparto: {str(exc)}',
                'code': 'IDEMPOTENCY_RUNTIME_ERROR',
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    if idempotencia.replay:
        return Response(
            idempotencia.replay_payload,
            status=idempotencia.replay_status or status.HTTP_200_OK
        )

    try:
        model_reparto = EmbarqueReparto.objects.filter(id=reparto_id).first()
        if not model_reparto:
            _safe_fallar_operacion(
                operacion_id=idempotencia.operacion.id,
                error_message='Reparto no encontrado',
                http_status=status.HTTP_404_NOT_FOUND,
                user=request.user,
            )
            return Response(
                {'detail': 'Reparto no encontrado', 'code': 'REPARTO_NOT_FOUND'},
                status=status.HTTP_404_NOT_FOUND
            )
            
        if model_reparto.fase != EmbarqueReparto.FASE_REPARTO:
            _safe_fallar_operacion(
                operacion_id=idempotencia.operacion.id,
                error_message=(
                    f'El reparto debe estar en fase REPARTO para finalizar. '
                    f'Fase actual: {model_reparto.fase}'
                ),
                http_status=status.HTTP_400_BAD_REQUEST,
                user=request.user,
            )
            return Response(
                {
                    'detail': f'El reparto debe estar en fase REPARTO para finalizar. Fase actual: {model_reparto.fase}',
                    'code': 'REPARTO_INVALID_PHASE',
                },
                status=status.HTTP_400_BAD_REQUEST
            )
            
        model_reparto.fase = EmbarqueReparto.FASE_TERMINADO
        model_reparto.fecha_finalizada = timezone.now()
        model_reparto.save(update_fields=['fase', 'fecha_finalizada', 'updated_at'])

        response_payload = {
            'success': True,
            'message': f'Reparto {reparto_id} finalizado exitosamente',
            'reparto_id': model_reparto.id,
            'fase': model_reparto.fase,
            'idempotency_key': idempotency_key,
        }
        completar_operacion(
            operacion_id=idempotencia.operacion.id,
            response_payload=response_payload,
            http_status=status.HTTP_200_OK,
            user=request.user,
        )
        return Response(response_payload, status=status.HTTP_200_OK)
    except Exception as e:
        _safe_fallar_operacion(
            operacion_id=idempotencia.operacion.id,
            error_message=str(e),
            http_status=status.HTTP_400_BAD_REQUEST,
            user=request.user,
        )
        return Response(
            {'detail': str(e), 'code': 'ERROR_FINALIZAR_REPARTO'},
            status=status.HTTP_400_BAD_REQUEST
        )
    


"""
============================================================================================
                            VIEWS PARA CHECKIN DE PRODUCTOS EN EMBARQUE
============================================================================================
"""

@extend_schema(
    summary="Checkin de productos en embarque",
    description="Realiza el checkin de productos de ventas en un embarque de ruta. Permite marcar los productos que se están cargando en el vehículo.",
    request=VentasEmbarqueSubidaRutaSerializer,
    responses={
        200: inline_serializer(
            name='CheckinProductoResponse',
            fields={
                'success': serializers.BooleanField(),
                'message': serializers.CharField(),
                'embarque_id': serializers.IntegerField(),
                'ventas_procesadas': serializers.IntegerField(),
                'productos_checkin': serializers.IntegerField(),
            }
        ),
        400: "Error en los datos proporcionados",
        404: "Embarque no encontrado"
    },
    tags=['Embarque']
)
@api_view(['POST'])
def checkin_producto_embarque(request):
    """
    Realiza el checkin de productos de ventas en un embarque.
    Marca los productos como cargados en el vehículo de reparto.
    """
    serializer = VentasEmbarqueSubidaRutaSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {'detail': 'Datos inválidos', 'errors': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    embarque_validado = serializer.validated_data.get('embarque')
    request_hash = construir_request_hash(request.data)
    try:
        idempotency_key = resolver_idempotency_key(request, request_hash)
        idempotencia = adquirir_operacion(
            scope='EMBARQUE_CHECKIN',
            entity_id=embarque_validado.id if embarque_validado else 'unknown',
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            user=request.user,
        )
    except IdempotenciaError as exc:
        return _idempotencia_error_response(exc)

    if idempotencia.replay:
        return Response(
            idempotencia.replay_payload,
            status=idempotencia.replay_status or status.HTTP_200_OK
        )
    
    try:
        with transaction.atomic():
            embarque = serializer.validated_data.get('embarque')
            ventas_data = serializer.validated_data.get('ventas', [])
            productos_tara = serializer.validated_data.get('productos_tara', [])
            auto_iniciar_reparto = serializer.validated_data.get('auto_iniciar_reparto', True)
            
            # Validar que el embarque esté en fase PROGRAMADO (legacy CARGA).
            if embarque.fase not in EmbarqueReparto.fases_programado_compat():
                fallar_operacion(
                    operacion_id=idempotencia.operacion.id,
                    error_message=f'El embarque debe estar en fase PROGRAMADO. Fase actual: {embarque.fase}',
                    http_status=status.HTTP_400_BAD_REQUEST,
                    user=request.user,
                )
                return Response(
                    {
                        'detail': f'El embarque debe estar en fase PROGRAMADO. Fase actual: {embarque.fase}',
                        'code': 'EMBARQUE_INVALID_PHASE',
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            
            
            productos_checkin_count = 0
            ventas_procesadas = 0
            
            for venta_data in ventas_data:
                venta = venta_data.get('venta')
                productos = venta_data.get('productos', [])
                
                for producto_data in productos:
                    producto = producto_data.get('producto')
                    check = producto_data.get('check', False)
                    
                    if check:
                        # Actualizar el detalle de venta correspondiente
                        from apps.erp.models import VentaDetalle
                        detalle = VentaDetalle.objects.filter(
                            venta=venta,
                            producto=producto
                        ).first()
                        
                        if detalle:
                            # Marcar como cargado (cantidad_cargada = cantidad)
                            detalle.cantidad_cargada = detalle.cantidad_logistica
                            detalle.is_cargado = True
                            detalle.save(update_fields=['cantidad_cargada', 'is_cargado'])
                            productos_checkin_count += 1
                
                ventas_procesadas += 1
                
                ## Verificar si todos los detalles de la venta están cargados
                #from apps.erp.models import VentaDetalle
                #detalles_sin_cargar = VentaDetalle.objects.filter(
                #    venta=venta,
                #    is_cargado=False
                #).count()
                #
                #if detalles_sin_cargar == 0:
                #    venta.is_total_cargado = True
                #    venta.save(update_fields=['is_total_cargado'])
            
            # Procesar productos de tara si existen
            tara_checkin_count = 0
            for producto_tara in productos_tara:
                producto_carga = producto_tara.get('producto_carga')
                check = producto_tara.get('check', False)
                
                if check:
                    producto_carga.is_cargado = True
                    producto_carga.save(update_fields=['is_cargado'])
                    
                    # Aquí se puede agregar lógica adicional para tara
                    tara_checkin_count += 1
                    
            if auto_iniciar_reparto:
                from django.utils import timezone
                embarque.fase = EmbarqueReparto.FASE_REPARTO
                if not embarque.fecha_salida:
                    embarque.fecha_salida = timezone.now()
                embarque.save(update_fields=['fase', 'fecha_salida', 'updated_at'])
            
            response_payload = {
                'success': True,
                'message': f'Checkin realizado exitosamente',
                'embarque_id': embarque.id,
                'ventas_procesadas': ventas_procesadas,
                'productos_checkin': productos_checkin_count,
                'productos_tara_checkin': tara_checkin_count,
                'fase': embarque.fase,
                'auto_iniciar_reparto': bool(auto_iniciar_reparto),
                'idempotency_key': idempotency_key,
            }
            completar_operacion(
                operacion_id=idempotencia.operacion.id,
                response_payload=response_payload,
                http_status=status.HTTP_200_OK,
                user=request.user,
            )
            return Response(response_payload, status=status.HTTP_200_OK)
            
    except Exception as e:
        fallar_operacion(
            operacion_id=idempotencia.operacion.id,
            error_message=str(e),
            http_status=status.HTTP_400_BAD_REQUEST,
            user=request.user,
        )
        return Response(
            {'detail': f'Error al realizar checkin: {str(e)}', 'code': 'EMBARQUE_CHECKIN_ERROR'},
            status=status.HTTP_400_BAD_REQUEST
        )


"""
============================================================================================
                            VIEWS PARA MOVIMIENTOS DE CAJA DEL EMBARQUE
============================================================================================
"""

@extend_schema(
    summary="Obtener movimientos de caja del embarque",
    description="Obtiene los movimientos de caja (transacciones) asociados a la apertura de caja de un embarque/reparto. Puede devolver JSON o PDF para impresión de cierre.",
    parameters=[
        OpenApiParameter(
            name='embarque_id',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='ID del embarque/reparto',
            required=True
        ),
        OpenApiParameter(
            name='formato',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Formato de respuesta: json (default) o pdf',
            required=False
        ),
        OpenApiParameter(
            name='disposition',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Solo para formato=pdf: attachment (default) o inline',
            required=False
        ),
    ],
    responses={
        200: "EmbarqueCajaMovimientosSerializer con ventas (JSON) o PDF de cierre",
        400: "Error: embarque_id requerido",
        404: "Embarque no encontrado o no tiene caja asignada"
    },
    tags=['Embarque']
)
@api_view(['GET'])
def obtener_caja_movimientos_embarque(request):
    """
    Endpoint para obtener los movimientos de caja asociados a un embarque,
    incluyendo las ventas realizadas durante el periodo del embarque.
    """
    from apps.erp.serializers.embarque.embarque_serializer import (
        EmbarqueCajaMovimientosSerializer,
        VentaEmbarqueCajaSerializer,
        _abonos_detalle_desde_qs,
        _resumen_abonos_por_credito,
    )
    from apps.erp.models import CajaApertura, CajaTransaccion
    
    embarque_id = request.query_params.get('embarque_id')
    formato = (request.query_params.get('formato') or 'json').strip().lower()
    disposition = (request.query_params.get('disposition') or 'attachment').strip().lower()
    
    if not embarque_id:
        return Response(
            {'detail': 'El parámetro embarque_id es requerido'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if formato not in ('json', 'pdf'):
        return Response(
            {'detail': "El parámetro formato debe ser 'json' o 'pdf'"},
            status=status.HTTP_400_BAD_REQUEST
        )
    if disposition not in ('attachment', 'inline'):
        return Response(
            {'detail': "El parámetro disposition debe ser 'attachment' o 'inline'"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Buscar el embarque
    embarque = EmbarqueReparto.objects.select_related(
        'ruta',
        'ruta__unidad',
        'encargado',
        'apertura_caja',
        'apertura_caja__usuario'
    ).filter(id=embarque_id).first()
    
    if not embarque:
        return Response(
            {'detail': 'Embarque no encontrado'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Verificar que el embarque tenga una caja asignada
    if not embarque.apertura_caja:
        return Response(
            {'detail': 'El embarque no tiene una caja asignada'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Obtener la apertura de caja con sus transacciones
    apertura_caja = CajaApertura.objects.select_related(
        'caja',
        'usuario'
    ).prefetch_related(
        'transacciones',
        'transacciones__metodo_pago'
    ).get(id=embarque.apertura_caja.id)
    
    serializer = EmbarqueCajaMovimientosSerializer(apertura_caja)
    response_data = serializer.data
    
    # Obtener las ventas asociadas explícitamente al embarque
    ventas_queryset = embarque.ventas.select_related(
        'cliente',
        'created_by'
    ).filter(
        status_model=Venta.STATUS_MODEL_ACTIVE
    ).exclude(
        fase=Venta.FASE_CANCELADA
    ).order_by('-created_at')
    
    ventas_serializer = VentaEmbarqueCajaSerializer(ventas_queryset, many=True)
    ventas_corte = []
    for venta in ventas_queryset:
        total = float(venta.total or 0)
        pagado = float(venta.total_pagado or 0)
        saldo = round(max(total - pagado, 0.0), 2)
        condicion_pago_normalizada = (venta.condicion_pago or '').upper().replace('É', 'E')
        ventas_corte.append({
            'venta_id': venta.id,
            'venta_codigo': venta.codigo,
            'cliente_id': venta.cliente_id,
            'cliente_codigo': venta.cliente.codigo if venta.cliente else None,
            'cliente_nombre': venta.cliente.get_full_name if venta.cliente else None,
            'total': round(total, 2),
            'pago': round(pagado, 2),
            'credito': 'SI' if condicion_pago_normalizada == 'CREDITO' else 'NO',
            'saldo': saldo,
            'condicion_pago': venta.condicion_pago,
            'created_at': venta.created_at,
            'created_by_id': venta.created_by_id,
            'created_by_nombre': venta.created_by.full_name() if venta.created_by else None,
        })
    
    # Calcular totales de ventas
    total_ventas = sum(float(v.total) for v in ventas_queryset)
    total_cobrado_ventas = sum(float(v.total_pagado) for v in ventas_queryset)

    # Abonos de crédito capturados durante el reparto (cash real de caja del embarque)
    abonos_caja_qs = apertura_caja.transacciones.filter(
        status_model=BaseModel.STATUS_MODEL_ACTIVE,
        tipo=CajaTransaccion.TIPO_ENTRADA,
    ).filter(
        Q(descripcion__icontains='Pago de crédito ID') |
        Q(descripcion__icontains='Pago de credito ID')
    )
    ventas_caja_qs = apertura_caja.transacciones.filter(
        status_model=BaseModel.STATUS_MODEL_ACTIVE,
        tipo=CajaTransaccion.TIPO_ENTRADA,
        descripcion__icontains='Pago de venta',
    )
    total_abonos = float(abonos_caja_qs.aggregate(total=Sum('monto')).get('total') or 0.0)
    total_abonos_efectivo = float(
        abonos_caja_qs.filter(
            metodo_pago__nombre__iexact='EFECTIVO'
        ).aggregate(total=Sum('monto')).get('total') or 0.0
    )
    abonos_por_metodo_rows = abonos_caja_qs.values('metodo_pago_id', 'metodo_pago__nombre').annotate(
        monto_total=Sum('monto'),
        cantidad_pagos=Count('id'),
    )
    ventas_por_metodo_rows = ventas_caja_qs.values('metodo_pago_id').annotate(
        monto_total=Sum('monto')
    )
    
    response_data['ventas'] = ventas_serializer.data
    response_data['ventas_corte'] = ventas_corte
    response_data['total_ventas'] = round(total_ventas, 2)
    response_data['total_cobrado_ventas'] = round(total_cobrado_ventas, 2)
    response_data['cantidad_ventas'] = ventas_queryset.count()
    response_data['recibio_abonos'] = total_abonos > 0
    response_data['total_abonos'] = round(total_abonos, 2)
    response_data['total_abonos_efectivo'] = round(total_abonos_efectivo, 2)
    abonos_detalle = _abonos_detalle_desde_qs(abonos_caja_qs)
    response_data['abonos_detalle'] = abonos_detalle
    response_data['abonos_resumen_credito'] = _resumen_abonos_por_credito(abonos_detalle)
    response_data['abonos_por_metodo'] = [
        {
            'metodo_pago_id': row['metodo_pago_id'],
            'metodo_pago_nombre': row['metodo_pago__nombre'],
            'monto_total': round(float(row.get('monto_total') or 0), 2),
            'cantidad_pagos': int(row.get('cantidad_pagos') or 0),
        }
        for row in abonos_por_metodo_rows.order_by('metodo_pago__nombre')
    ]
    from apps.contabilidad.models import MetodoPago
    metodos = list(MetodoPago.objects.filter(activo=True).values('id', 'nombre').order_by('nombre'))
    ventas_map = {row['metodo_pago_id']: float(row['monto_total'] or 0) for row in ventas_por_metodo_rows}
    abonos_map = {row['metodo_pago_id']: float(row['monto_total'] or 0) for row in abonos_por_metodo_rows}
    formas_pago = []
    for metodo in metodos:
        ventas_total = round(ventas_map.get(metodo['id'], 0.0), 2)
        abonos_total = round(abonos_map.get(metodo['id'], 0.0), 2)
        formas_pago.append({
            'metodo_pago_id': metodo['id'],
            'metodo_pago_nombre': metodo['nombre'],
            'ventas': ventas_total,
            'abonos': abonos_total,
            'total': round(ventas_total + abonos_total, 2),
        })
    response_data['formas_pago'] = formas_pago
    response_data['total_ventas_formas_pago'] = round(sum(item['ventas'] for item in formas_pago), 2)
    response_data['total_abonos_formas_pago'] = round(sum(item['abonos'] for item in formas_pago), 2)
    response_data['total_general_formas_pago'] = round(sum(item['total'] for item in formas_pago), 2)
    response_data['corte_reparto'] = {
        'encabezado': {
            'reparto_id': embarque.id,
            'ruta_id': embarque.ruta_id,
            'ruta_codigo': embarque.ruta.codigo if embarque.ruta else None,
            'ruta_nombre': embarque.ruta.nombre if embarque.ruta else None,
            'unidad_id': embarque.ruta.unidad_id if embarque.ruta else None,
            'unidad_codigo': embarque.ruta.unidad.get_clave() if embarque.ruta and embarque.ruta.unidad else None,
            'unidad_nombre': embarque.ruta.unidad.nombre if embarque.ruta and embarque.ruta.unidad else None,
            'unidad_placas': embarque.ruta.unidad.placas if embarque.ruta and embarque.ruta.unidad else None,
            'encargado_id': embarque.encargado_id,
            'encargado_nombre': embarque.encargado.full_name() if embarque.encargado else None,
            'fecha_reparto': embarque.fecha_salida or embarque.created_at,
            'fecha_cierre': embarque.fecha_finalizada,
            'empleado_caja_id': apertura_caja.usuario_id if apertura_caja else None,
            'empleado_caja_nombre': apertura_caja.usuario.full_name() if apertura_caja and apertura_caja.usuario else None,
        },
        'ventas': response_data['ventas'],
        'ventas_corte': ventas_corte,
        'creditos_abonos': response_data['abonos_resumen_credito'],
        'formas_pago': response_data['formas_pago'],
        'totales': {
            'total_ventas': response_data['total_ventas'],
            'total_cobrado_ventas': response_data['total_cobrado_ventas'],
            'total_abonos': response_data['total_abonos'],
            'total_abonos_efectivo': response_data['total_abonos_efectivo'],
            'total_general': response_data['total_general_formas_pago'],
        },
        'firmas': {
            'gerente_ruta': None,
            'cajero_cierre': apertura_caja.usuario.full_name() if apertura_caja and apertura_caja.usuario else None,
        },
    }
    
    if formato == 'pdf':
        try:
            pdf_bytes = _render_corte_pdf(response_data)
        except Exception as exc:
            return Response(
                {
                    'detail': f'Error al generar PDF de cierre: {str(exc)}',
                    'code': 'PDF_GENERATION_ERROR',
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        file_name = f"corte-reparto-{embarque.id}.pdf"
        pdf_response = HttpResponse(pdf_bytes, content_type='application/pdf')
        pdf_response['Content-Disposition'] = f'{disposition}; filename="{file_name}"'
        return pdf_response

    return Response(response_data, status=status.HTTP_200_OK)


@extend_schema(
    summary="Listado de pedidos del usuario en fase REPARTO",
    description="Devuelve el embarque activo del usuario (PROGRAMADO o REPARTO) y sus pedidos con detalle de productos cargados.",
    parameters=[
        OpenApiParameter(
            name='embarque_id',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='ID de embarque opcional. Si no se envía, se busca el REPARTO activo del usuario.',
            required=False
        ),
        OpenApiParameter(
            name='fase',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Fase opcional cuando no se envía embarque_id. Valores: PROGRAMADO o REPARTO. Si no se envía, prioriza REPARTO activo y, si no existe, PROGRAMADO.',
            required=False
        ),
        OpenApiParameter(
            name='include_terminadas',
            type=OpenApiTypes.BOOL,
            location=OpenApiParameter.QUERY,
            description='Incluye ventas ya entregadas/terminadas en el listado de pedidos (default: false).',
            required=False
        )
    ],
    responses={
        200: OpenApiTypes.OBJECT,
        404: OpenApiTypes.OBJECT
    },
    tags=['Embarque']
)
@api_view(['GET'])
def listado_pedidos_usuario_reparto(request):
    from django.db.models import Q, Prefetch
    from decimal import Decimal

    def cantidad_prioritaria(detalle):
        candidatos = [
            detalle.cantidad_logistica,
            detalle.cantidad_cargada,
            detalle.cantidad,
        ]
        for value in candidatos:
            if value is not None and Decimal(str(value)) > 0:
                return value
        return Decimal('0.000')

    try:
        embarque_id = request.query_params.get('embarque_id')
        fase_raw = (request.query_params.get('fase') or '').strip().upper()
        include_terminadas = (request.query_params.get('include_terminadas') or '').lower() == 'true'
        fase_param = None
        if fase_raw:
            fase_param = (
                EmbarqueReparto.FASE_PROGRAMADO
                if fase_raw == EmbarqueReparto.FASE_CARGA_LEGACY
                else fase_raw
            )

        queryset = EmbarqueReparto.objects.select_related(
            'ruta',
            'encargado'
        ).prefetch_related(
            Prefetch(
                'ventas',
                queryset=Venta.objects.select_related('cliente').prefetch_related('detalles__producto__unidad_sat').exclude(
                    fase=Venta.FASE_CANCELADA
                )
            ),
            Prefetch(
                'productos',
                queryset=ProductoEmbarque.objects.select_related(
                    'producto__unidad_sat',
                    'preventa',
                )
            ),
        ).filter(
            status_model=BaseModel.STATUS_MODEL_ACTIVE
        )

        if embarque_id:
            queryset = queryset.filter(id=embarque_id)
        else:
            if fase_param and fase_param not in [EmbarqueReparto.FASE_PROGRAMADO, EmbarqueReparto.FASE_REPARTO]:
                return Response(
                    {'detail': "El parámetro 'fase' solo acepta PROGRAMADO o REPARTO."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            queryset_usuario = queryset.filter(
                Q(encargado=request.user) | Q(ruta__asignado=request.user)
            )
            if fase_param == EmbarqueReparto.FASE_PROGRAMADO:
                queryset = queryset_usuario.filter(
                    fase__in=EmbarqueReparto.fases_programado_compat()
                )
            elif fase_param == EmbarqueReparto.FASE_REPARTO:
                queryset = queryset_usuario.filter(fase=EmbarqueReparto.FASE_REPARTO)
            else:
                # Flujo app: prioriza REPARTO activo; si no existe, usa PROGRAMADO.
                reparto_activo = queryset_usuario.filter(
                    fase=EmbarqueReparto.FASE_REPARTO
                ).order_by('-id').first()
                if reparto_activo:
                    queryset = queryset_usuario.filter(id=reparto_activo.id)
                else:
                    queryset = queryset_usuario.filter(
                        fase__in=EmbarqueReparto.fases_programado_compat()
                    )

        embarque = queryset.order_by('-id').first()
        if not embarque:
            return Response(
                {'detail': 'No hay embarque activo (PROGRAMADO/REPARTO) para el usuario actual.'},
                status=status.HTTP_404_NOT_FOUND
            )

        productos_por_venta = {}
        for prod_emb in embarque.productos.all():
            if prod_emb.tipo != ProductoEmbarque.PEDIDO or not prod_emb.preventa_id:
                continue
            productos_por_venta.setdefault(prod_emb.preventa_id, []).append(prod_emb)

        inventario_pedido = defaultdict(dict)
        inventario_tara = defaultdict(dict)
        productos_tara_detalle = []

        for prod_emb in embarque.productos.all():
            if not prod_emb.producto_id:
                continue

            bucket = inventario_tara if prod_emb.tipo == ProductoEmbarque.TARA else inventario_pedido
            if not bucket[prod_emb.producto_id]:
                bucket[prod_emb.producto_id] = {
                    'producto_id': prod_emb.producto_id,
                    'producto_codigo': prod_emb.producto.codigo if prod_emb.producto else None,
                    'producto_nombre': prod_emb.producto.nombre if prod_emb.producto else None,
                    'unidad_medida': (
                        prod_emb.producto.unidad_sat.nombre
                        if prod_emb.producto and prod_emb.producto.unidad_sat
                        else None
                    ),
                    'unidad_clave': (
                        prod_emb.producto.unidad_sat.clave
                        if prod_emb.producto and prod_emb.producto.unidad_sat
                        else None
                    ),
                    'cantidad': Decimal('0.000'),
                    'tipo': prod_emb.tipo,
                }

            bucket[prod_emb.producto_id]['cantidad'] += Decimal(str(prod_emb.cantidad or 0))

            if prod_emb.tipo == ProductoEmbarque.TARA:
                productos_tara_detalle.append({
                    'id': prod_emb.id,
                    'producto_id': prod_emb.producto_id,
                    'producto_codigo': prod_emb.producto.codigo if prod_emb.producto else None,
                    'producto_nombre': prod_emb.producto.nombre if prod_emb.producto else None,
                    'unidad_medida': (
                        prod_emb.producto.unidad_sat.nombre
                        if prod_emb.producto and prod_emb.producto.unidad_sat
                        else None
                    ),
                    'unidad_clave': (
                        prod_emb.producto.unidad_sat.clave
                        if prod_emb.producto and prod_emb.producto.unidad_sat
                        else None
                    ),
                    'cantidad': prod_emb.cantidad,
                    'precio_unitario': prod_emb.precio_unitario,
                    'is_cargado': prod_emb.is_cargado,
                })

        ventas_data = []
        for venta in embarque.ventas.all().order_by('-created_at'):
            if not include_terminadas and (venta.is_entregado or venta.ya_terminada or venta.fase == Venta.FASE_TERMINADA):
                continue
            detalles_venta_map = {d.producto_id: d for d in venta.detalles.all()}
            detalles_data = []
            productos_cargados = productos_por_venta.get(venta.id, [])

            if productos_cargados:
                for producto_embarque in productos_cargados:
                    detalle = detalles_venta_map.get(producto_embarque.producto_id)
                    cantidad_logistica = (
                        detalle.cantidad_logistica
                        if detalle and detalle.cantidad_logistica and detalle.cantidad_logistica > 0
                        else producto_embarque.cantidad
                    )
                    cantidad_entregada = detalle.cantidad_entregada if detalle else Decimal('0.000')
                    precio_unitario = (
                        detalle.precio_unitario
                        if detalle and detalle.precio_unitario is not None
                        else producto_embarque.precio_unitario
                    )
                    detalles_data.append({
                        'id': detalle.id if detalle else None,
                        'producto_id': producto_embarque.producto_id,
                        'producto_codigo': producto_embarque.producto.codigo if producto_embarque.producto else None,
                        'producto_nombre': producto_embarque.producto.nombre if producto_embarque.producto else None,
                        'unidad_medida': (
                            producto_embarque.producto.unidad_sat.nombre
                            if producto_embarque.producto and producto_embarque.producto.unidad_sat
                            else None
                        ),
                        'unidad_clave': (
                            producto_embarque.producto.unidad_sat.clave
                            if producto_embarque.producto and producto_embarque.producto.unidad_sat
                            else None
                        ),
                        'cantidad': cantidad_logistica,
                        'cantidad_logistica': cantidad_logistica,
                        'cantidad_cargada': producto_embarque.cantidad,
                        'cantidad_entregada': cantidad_entregada,
                        'precio_unitario': precio_unitario,
                        'subtotal': (precio_unitario or Decimal('0.000')) * (cantidad_logistica or Decimal('0.000')),
                        'is_cargado': True,
                        'is_entregado': bool(detalle.is_entregado) if detalle else False,
                    })
            else:
                for detalle in venta.detalles.all():
                    detalles_data.append({
                        'id': detalle.id,
                        'producto_id': detalle.producto_id,
                        'producto_codigo': detalle.producto.codigo if detalle.producto else None,
                        'producto_nombre': detalle.producto.nombre if detalle.producto else None,
                        'unidad_medida': detalle.producto.unidad_sat.nombre if detalle.producto and detalle.producto.unidad_sat else None,
                        'unidad_clave': detalle.producto.unidad_sat.clave if detalle.producto and detalle.producto.unidad_sat else None,
                        'cantidad': cantidad_prioritaria(detalle),
                        'cantidad_logistica': detalle.cantidad_logistica,
                        'cantidad_cargada': detalle.cantidad_cargada,
                        'cantidad_entregada': detalle.cantidad_entregada,
                        'precio_unitario': detalle.precio_unitario,
                        'subtotal': detalle.subtotal,
                        'is_cargado': detalle.is_cargado,
                        'is_entregado': detalle.is_entregado,
                    })

            ventas_data.append({
                'id': venta.id,
                'codigo': venta.codigo,
                'cliente_id': venta.cliente_id,
                'cliente_nombre': venta.cliente.get_full_name if venta.cliente else None,
                'fase': Venta.FASE_TERMINADA if venta.is_entregado else venta.fase,
                'condicion_pago': venta.condicion_pago,
                'total': venta.total,
                'total_pagado': venta.total_pagado,
                'is_entregado': venta.is_entregado,
                'is_total_cargado': venta.is_total_cargado,
                'detalles': detalles_data,
            })

        productos_pedido_inventario = sorted(
            inventario_pedido.values(),
            key=lambda x: (x.get('producto_nombre') or '')
        )
        productos_tara_inventario = sorted(
            inventario_tara.values(),
            key=lambda x: (x.get('producto_nombre') or '')
        )

        return Response({
            'embarque': {
                'id': embarque.id,
                'fase': embarque.fase,
                'ruta_id': embarque.ruta_id,
                'ruta_codigo': embarque.ruta.codigo if embarque.ruta else None,
                'ruta_nombre': embarque.ruta.nombre if embarque.ruta else None,
                'encargado_id': embarque.encargado_id,
                'encargado_nombre': embarque.encargado.full_name() if embarque.encargado else None,
                'fecha_salida': embarque.fecha_salida,
                'fecha_finalizada': embarque.fecha_finalizada,
            },
            'ventas': ventas_data,
            'total_ventas': len(ventas_data),
            'productos_tara': productos_tara_detalle,
            'inventario_reparto': {
                'productos_pedido': productos_pedido_inventario,
                'productos_tara': productos_tara_inventario,
                'totales': {
                    'lineas_pedido': len(productos_pedido_inventario),
                    'lineas_tara': len(productos_tara_inventario),
                    'cantidad_total_pedido': sum((item['cantidad'] for item in productos_pedido_inventario), Decimal('0.000')),
                    'cantidad_total_tara': sum((item['cantidad'] for item in productos_tara_inventario), Decimal('0.000')),
                }
            }
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'detail': f'Error al obtener pedidos del reparto: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )


@extend_schema(
    summary="Historial de ventas entregadas por usuario de ruta",
    description=(
        "Lista ventas/pedidos ya entregados (fase TERMINADA o is_entregado=true) "
        "para el usuario de ruta autenticado. "
        "Pensado para la pantalla móvil de Historial de Ventas."
    ),
    parameters=[
        OpenApiParameter(
            name='search',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Buscar por código de preventa, cliente o ruta',
            required=False
        ),
        OpenApiParameter(
            name='ruta_id',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='Filtrar por ruta específica',
            required=False
        ),
        OpenApiParameter(
            name='embarque_id',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='Filtrar historial por un embarque específico terminado.',
            required=False
        ),
        OpenApiParameter(
            name='scope',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Alcance del historial: 'ultimo_reparto' (default) o 'todos'.",
            required=False
        ),
        OpenApiParameter(
            name='fecha_inicio',
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description='Fecha inicial (YYYY-MM-DD) sobre fecha de actualización de la venta',
            required=False
        ),
        OpenApiParameter(
            name='fecha_fin',
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description='Fecha final (YYYY-MM-DD) sobre fecha de actualización de la venta',
            required=False
        ),
    ],
    responses={200: OpenApiTypes.OBJECT},
    tags=['Embarque']
)
@api_view(['GET'])
def historial_ventas_usuario_reparto(request):
    from datetime import datetime
    from decimal import Decimal
    from django.db.models import Q, Prefetch

    user = request.user
    is_admin = bool(getattr(user, 'is_superuser', False) or getattr(user, 'is_staff', False))

    search = (request.query_params.get('search') or '').strip()
    ruta_id_raw = (request.query_params.get('ruta_id') or '').strip()
    embarque_id_raw = (request.query_params.get('embarque_id') or '').strip()
    scope = (request.query_params.get('scope') or 'ultimo_reparto').strip().lower()
    fecha_inicio_raw = (request.query_params.get('fecha_inicio') or '').strip()
    fecha_fin_raw = (request.query_params.get('fecha_fin') or '').strip()

    ruta_id = None
    embarque_id = None
    if ruta_id_raw:
        if not ruta_id_raw.isdigit():
            return Response(
                {'detail': "El parámetro 'ruta_id' debe ser numérico."},
                status=status.HTTP_400_BAD_REQUEST
            )
        ruta_id = int(ruta_id_raw)
    if embarque_id_raw:
        if not embarque_id_raw.isdigit():
            return Response(
                {'detail': "El parámetro 'embarque_id' debe ser numérico."},
                status=status.HTTP_400_BAD_REQUEST
            )
        embarque_id = int(embarque_id_raw)

    if scope not in {'ultimo_reparto', 'todos'}:
        return Response(
            {'detail': "El parámetro 'scope' solo acepta 'ultimo_reparto' o 'todos'."},
            status=status.HTTP_400_BAD_REQUEST
        )

    fecha_inicio = None
    fecha_fin = None
    try:
        if fecha_inicio_raw:
            fecha_inicio = datetime.strptime(fecha_inicio_raw, '%Y-%m-%d').date()
        if fecha_fin_raw:
            fecha_fin = datetime.strptime(fecha_fin_raw, '%Y-%m-%d').date()
    except ValueError:
        return Response(
            {'detail': "Formato de fecha inválido. Usa YYYY-MM-DD."},
            status=status.HTTP_400_BAD_REQUEST
        )

    embarques_prefetch = EmbarqueReparto.objects.select_related(
        'ruta',
        'encargado',
    ).filter(
        status_model=BaseModel.STATUS_MODEL_ACTIVE
    ).order_by('-id')

    if not is_admin:
        embarques_prefetch = embarques_prefetch.filter(
            Q(encargado=user) | Q(ruta__asignado=user)
        )

    if ruta_id:
        embarques_prefetch = embarques_prefetch.filter(ruta_id=ruta_id)

    embarque_contexto = None
    if embarque_id:
        embarque_contexto = embarques_prefetch.filter(
            id=embarque_id,
            fase=EmbarqueReparto.FASE_TERMINADO
        ).first()
    elif scope == 'ultimo_reparto':
        embarque_contexto = embarques_prefetch.filter(
            fase=EmbarqueReparto.FASE_TERMINADO
        ).order_by('-fecha_finalizada', '-id').first()

    ventas_qs = Venta.objects.select_related(
        'cliente',
        'ruta'
    ).prefetch_related(
        Prefetch(
            'detalles',
            queryset=VentaDetalle.objects.select_related(
                'producto__unidad_sat'
            ).order_by('id')
        ),
        Prefetch(
            'embarques_ruta',
            queryset=embarques_prefetch
        ),
    ).filter(
        status_model=BaseModel.STATUS_MODEL_ACTIVE,
        was_preventa=True,
        embarques_ruta__status_model=BaseModel.STATUS_MODEL_ACTIVE,
    ).filter(
        Q(is_entregado=True) | Q(ya_terminada=True) | Q(fase=Venta.FASE_TERMINADA)
    ).distinct().order_by('-updated_at', '-id')

    if embarque_contexto:
        ventas_qs = ventas_qs.filter(embarques_ruta__id=embarque_contexto.id)
    elif embarque_id:
        return Response(
            {'detail': 'No se encontró un embarque terminado con ese ID para el usuario actual.'},
            status=status.HTTP_404_NOT_FOUND
        )

    if not is_admin:
        ventas_qs = ventas_qs.filter(
            Q(embarques_ruta__encargado=user) | Q(embarques_ruta__ruta__asignado=user)
        )

    if ruta_id:
        ventas_qs = ventas_qs.filter(ruta_id=ruta_id)

    if search:
        for termino in [t for t in search.split() if t]:
            ventas_qs = ventas_qs.filter(
                Q(codigo__icontains=termino) |
                Q(cliente__codigo__icontains=termino) |
                Q(cliente__nombre__icontains=termino) |
                Q(cliente__apellido_paterno__icontains=termino) |
                Q(cliente__apellido_materno__icontains=termino) |
                Q(ruta__nombre__icontains=termino) |
                Q(ruta__codigo__icontains=termino)
            )

    if fecha_inicio:
        ventas_qs = ventas_qs.filter(updated_at__date__gte=fecha_inicio)
    if fecha_fin:
        ventas_qs = ventas_qs.filter(updated_at__date__lte=fecha_fin)

    def _serialize_venta(venta_obj):
        embarque_rel = None
        for emb in venta_obj.embarques_ruta.all():
            if ruta_id and emb.ruta_id != ruta_id:
                continue
            embarque_rel = emb
            break

        detalles = []
        for detalle in venta_obj.detalles.all():
            cantidad_programada = detalle.cantidad_logistica or detalle.cantidad or Decimal('0.000')
            cantidad_entregada = detalle.cantidad_entregada or Decimal('0.000')
            cantidad_devolucion = Decimal(str(cantidad_programada)) - Decimal(str(cantidad_entregada))
            if cantidad_devolucion < 0:
                cantidad_devolucion = Decimal('0.000')

            detalles.append({
                'id': detalle.id,
                'producto_id': detalle.producto_id,
                'producto_codigo': detalle.producto.codigo if detalle.producto else None,
                'producto_nombre': detalle.producto.nombre if detalle.producto else None,
                'unidad_medida': (
                    detalle.producto.unidad_sat.nombre
                    if detalle.producto and detalle.producto.unidad_sat
                    else None
                ),
                'unidad_clave': (
                    detalle.producto.unidad_sat.clave
                    if detalle.producto and detalle.producto.unidad_sat
                    else None
                ),
                'cantidad': cantidad_programada,
                'cantidad_entregada': cantidad_entregada,
                'devolucion': cantidad_devolucion,
                'precio_unitario': detalle.precio_unitario,
                'subtotal': detalle.subtotal,
                'is_entregado': bool(detalle.is_entregado),
            })

        return {
            'id': venta_obj.id,
            'codigo': venta_obj.codigo,
            'fase': Venta.FASE_TERMINADA if venta_obj.is_entregado else venta_obj.fase,
            'condicion_pago': venta_obj.condicion_pago,
            'cliente_id': venta_obj.cliente_id,
            'cliente_nombre': venta_obj.cliente.get_full_name if venta_obj.cliente else None,
            'ruta_id': venta_obj.ruta_id,
            'ruta_nombre': venta_obj.ruta.nombre if venta_obj.ruta else None,
            'ruta_codigo': venta_obj.ruta.codigo if venta_obj.ruta else None,
            'total': venta_obj.total,
            'total_pagado': venta_obj.total_pagado,
            'is_entregado': bool(venta_obj.is_entregado),
            'fecha_terminada': venta_obj.updated_at,
            'embarque_id': embarque_rel.id if embarque_rel else None,
            'embarque_fase': embarque_rel.fase if embarque_rel else None,
            'productos_count': len(detalles),
            'detalles': detalles,
        }

    results = [_serialize_venta(item) for item in ventas_qs]
    return Response(
        {
            'scope': scope,
            'embarque_contexto': {
                'id': embarque_contexto.id,
                'fase': embarque_contexto.fase,
                'ruta_id': embarque_contexto.ruta_id,
                'ruta_codigo': embarque_contexto.ruta.codigo if embarque_contexto.ruta else None,
                'ruta_nombre': embarque_contexto.ruta.nombre if embarque_contexto.ruta else None,
                'fecha_salida': embarque_contexto.fecha_salida,
                'fecha_finalizada': embarque_contexto.fecha_finalizada,
            } if embarque_contexto else None,
            'count': len(results),
            'results': results,
        },
        status=status.HTTP_200_OK
    )
