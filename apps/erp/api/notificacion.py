# notifications/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.erp.models import Notificacion
from apps.erp.serializers.notificacion.notificacion import NotificacionSerializer


class NotificacionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API para listar notificaciones no leídas y marcarlas como leídas.
    """
    serializer_class = NotificacionSerializer
    
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None  # Desactiva la paginación

    def get_queryset(self):
        """
        Lista solo notificaciones no leídas.
        Los superusuarios ven todas, los usuarios solo las suyas.
        """
        user = self.request.user
        if user.is_superuser:
            return Notificacion.objects.filter(leida=False).order_by('-creada_el')
        return Notificacion.objects.filter(usuario=user, leida=False).order_by('-creada_el')

    @action(
        detail=True,
        methods=['patch'],
        url_path='marcar-leida',
        url_name='marcar-leida'
    )
    def marcar_leida(self, request, pk=None):
        """
        Marca una notificación como leída.
        ---
        **Ejemplo:**
        ```
        PATCH /api/notificaciones/{id}/marcar-leida/
        ```
        No requiere cuerpo en la solicitud.
        """
        try:
            notificacion = Notificacion.objects.get(pk=pk)
        except Notificacion.DoesNotExist:
            return Response({'error': 'Notificación no encontrada.'},
                            status=status.HTTP_404_NOT_FOUND)

        ## Verifica que el usuario tenga permiso
        #if not request.user.is_superuser and notificacion.usuario != request.user:
        #    return Response({'error': 'No tienes permiso para modificar esta notificación.'},
        #                    status=status.HTTP_403_FORBIDDEN)

        # Marca como leída
        notificacion.marcar_como_leida()

        return Response({'message': 'Notificación marcada como leída.'},
                        status=status.HTTP_200_OK)
