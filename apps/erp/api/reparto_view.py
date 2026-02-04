from rest_framework import status, serializers
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from django.db import transaction

from drf_spectacular.utils import extend_schema, inline_serializer

from apps.erp.serializers.reparto.entregaProductoSerializer import EntragaProductoRutaSerializer


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
                'productos_entregados': serializers.IntegerField(),
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
    serializer = EntragaProductoRutaSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {'detail': 'Datos inválidos', 'errors': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    try:
        with transaction.atomic():
            
            venta_actualizada = serializer.save()
            
            
            return Response({
                'success': True,
                'message': f'Entrega registrada para venta {venta_actualizada.codigo}',
                'venta_id': venta_actualizada.id,
                'venta_codigo': venta_actualizada.codigo,
            }, status=status.HTTP_200_OK)
            
    except Exception as e:
        return Response(
            {'detail': f'Error al registrar entrega: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
