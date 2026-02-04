from rest_framework.views import APIView
from rest_framework.response import Response
from apps.inventario.services.alertasvencimiento import productos_por_vencer

class ProductosPorVencerAPIView(APIView):
    def get(self, request):
        data = productos_por_vencer()
        return Response(data)
