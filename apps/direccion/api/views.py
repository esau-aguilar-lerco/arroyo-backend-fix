from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import viewsets,permissions, status

from apps.direccion.models import CodigoPostal, Colonia, Municipio, Estado
from apps.direccion.serializers.estado import EstadoSerializer
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse



class EstadoListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        estados = Estado.objects.all().order_by('nombre')
        serializer = EstadoSerializer(estados, many=True)
        return Response({
            'code': 202,
            'estados': serializer.data,
            'message': 'Listado de estados',
            'status': 'success'
        }, status=status.HTTP_200_OK)


@extend_schema(
    summary="Desglose de dirección",
    description="API endpoint to retrieve detailed address breakdown (desglose de dirección) based on query parameters.",
    parameters=[
        OpenApiParameter(
            name="codigo_postal",
            description="Postal code to filter colonias (neighborhoods) and municipios (municipalities).",
            required=False,
            type=str,
            location=OpenApiParameter.QUERY,
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=None,
            description="""
            Ejemplo de respuesta:
            {
                "code": 202,
                "data": [
                    {
                        "codigo_postal_id": 1,
                        "codigo_postal": "12345",
                        "colonia_id": 2,
                        "colonia": "Centro",
                        "municipio_id": 3,
                        "municipio": "Ciudad",
                        "estado_id": 4,
                        "estado": "Estado"
                    }
                ],
                "message": "Desglose de dirección exitoso",
                "status": "success"
            }
            """
        )
    }
)
class DesgloseDireccionAPIView(APIView):
   
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        codigo_postal = request.GET.get('codigo_postal')
        colonias_data = []

        if codigo_postal:
            try:
                codigo = CodigoPostal.objects.get(codigo_postal=codigo_postal)
                colonias_qs = Colonia.objects.select_related('municipio', 'codigo_postal').filter(
                    codigo_postal=codigo
                ).order_by('d_asenta')
            except CodigoPostal.DoesNotExist:
                return Response({ 'code': 202,'data': [],})

            colonias_data = [
                {
                    'codigo_postal_id': colonia.codigo_postal.id,
                    'codigo_postal': colonia.codigo_postal.codigo_postal,
                    'colonia_id': colonia.id,
                    'colonia': colonia.d_asenta,
                    'municipio_id': colonia.municipio_id,
                    'municipio': colonia.municipio.nombre,
                    'estado_id': colonia.municipio.estado_id,
                    'estado': colonia.municipio.estado.nombre
                } for colonia in colonias_qs
            ]

        respuesta = {
            'code': 202,
            'data': colonias_data,
            'message': 'Desglose de dirección exitoso',
            'status': 'success'
        }
        return Response(respuesta, status=status.HTTP_200_OK)