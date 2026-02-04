

from django.db.models import Q, Count
from rest_framework import status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ViewSet
from drf_spectacular.utils import extend_schema, OpenApiParameter, inline_serializer
from rest_framework import serializers

from apps.inventario.serializers.rutas.movimentoTraspaso import MovimientoEmbarqueCreateRutaSerializer



class EmbarqueRutaViewSet(ViewSet):
    
    @extend_schema(
        request=MovimientoEmbarqueCreateRutaSerializer,
        responses={
            201: inline_serializer(
                name="EmbarqueRutaCreateResponse",
                fields={
                    "message": serializers.CharField(),
                    "data": serializers.DictField()
                }
            )
        },
        summary="Crear embarque de ruta",
        description="Crea un movimiento de embarque basado en la ruta y los productos proporcionados."
    )
    def create(self, request):
        """
        POST /api/embarques-ruta/
        Crea un nuevo embarque
        """
        serializer = MovimientoEmbarqueCreateRutaSerializer(
            data=request.data,
            context={'request': request, 'user': request.user}
        )
        serializer.is_valid(raise_exception=True)
        
        # Llamar al método create del serializer
        resultado = serializer.save()
        
        return Response(
            {
                "message": "Embarque creado exitosamente",
                "data": resultado
            },
            status=status.HTTP_201_CREATED
        )