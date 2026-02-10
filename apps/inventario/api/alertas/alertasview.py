from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.inventario.services.alertasvencimiento import (
    lotes_por_vencer,
    _usuarios_con_permiso_notificaciones,
)

class ProductosPorVencerAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _usuarios_con_permiso_notificaciones().filter(id=request.user.id).exists():
            return Response([])
        data = lotes_por_vencer()
        return Response(data)
