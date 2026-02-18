from rest_framework import status, serializers
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from django.db import transaction

from drf_spectacular.utils import extend_schema, inline_serializer

from apps.erp.serializers.reparto.entregaProductoSerializer import EntragaProductoRutaSerializer
from apps.inventario.services.idempotencia import (
    IdempotenciaError,
    adquirir_operacion,
    completar_operacion,
    construir_request_hash,
    fallar_operacion,
    resolver_idempotency_key,
)


@extend_schema(
    summary="Registrar entrega de productos en ruta",
    description="Registra la entrega de productos de una venta/preventa durante el reparto en ruta",
    request=EntragaProductoRutaSerializer,
    responses={
        200: inline_serializer(
            name='EntregaProductoResponse',
            fields={
                'success': serializers.BooleanField(),
                'message': serializers.CharField(),
                'venta_id': serializers.IntegerField(),
                'productos_procesados': serializers.IntegerField(),
                'incidencia_id': serializers.IntegerField(allow_null=True),
            }
        ),
        400: "Error en los datos proporcionados",
        404: "Venta no encontrada"
    },
    tags=['Reparto']
)
@api_view(['POST'])
def entrega_producto_ruta(request):
    """
    Registra la entrega de productos de una venta durante el reparto.
    Recibe la venta y los productos con sus cantidades entregadas.
    """
    serializer = EntragaProductoRutaSerializer(data=request.data, context={'request': request})
    
    if not serializer.is_valid():
        return Response(
            {'detail': 'Datos inválidos', 'errors': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    venta_validada = serializer.validated_data.get('venta')
    request_hash = construir_request_hash(request.data)
    try:
        idempotency_key = resolver_idempotency_key(request, request_hash)
        idempotencia = adquirir_operacion(
            scope='REPARTO_ENTREGA_PRODUCTO',
            entity_id=venta_validada.id if venta_validada else 'unknown',
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            user=request.user,
        )
    except IdempotenciaError as exc:
        return Response(
            {'detail': exc.detail, 'code': exc.code},
            status=exc.http_status,
        )

    if idempotencia.replay:
        return Response(
            idempotencia.replay_payload,
            status=idempotencia.replay_status or status.HTTP_200_OK
        )

    try:
        with transaction.atomic():
            
            resultado = serializer.save()
            venta_actualizada = resultado['venta']
            incidencia_model = resultado.get('incidencia')
            response_payload = {
                'success': True,
                'message': f'Entrega registrada para venta {venta_actualizada.codigo}',
                'venta_id': venta_actualizada.id,
                'venta_codigo': venta_actualizada.codigo,
                'productos_procesados': resultado.get('productos_procesados', 0),
                'incidencia_id': incidencia_model.id if incidencia_model else None,
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
            {
                'detail': f'Error al registrar entrega: {str(e)}',
                'code': 'REPARTO_ENTREGA_ERROR',
            },
            status=status.HTTP_400_BAD_REQUEST
        )
