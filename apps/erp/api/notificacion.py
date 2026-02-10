# notifications/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from apps.erp.models import Notificacion
from apps.erp.serializers.notificacion.notificacion import NotificacionSerializer


class NotificacionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API para listar notificaciones no leídas y marcarlas como leídas.
    """
    serializer_class = NotificacionSerializer
    
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None  # Desactiva la paginación
    
    def _tiene_permiso_notificaciones(self, user):
        if user.is_superuser:
            return True
        return (
            user.groups.filter(name='Compras').exists() or
            user.user_permissions.filter(codename='can_create_orden_compra').exists()
        )

    def get_queryset(self):
        """
        Lista solo notificaciones no leídas.
        Los superusuarios ven todas, los usuarios solo las suyas.
        """
        user = self.request.user
        if not self._tiene_permiso_notificaciones(user):
            return Notificacion.objects.none()
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

        if not self._tiene_permiso_notificaciones(request.user):
            return Response({'error': 'No tienes permiso para ver notificaciones.'},
                            status=status.HTTP_403_FORBIDDEN)

        if not request.user.is_superuser and notificacion.usuario != request.user:
            return Response({'error': 'No tienes permiso para modificar esta notificación.'},
                            status=status.HTTP_403_FORBIDDEN)

        # Marca como leída
        notificacion.marcar_como_leida()

        return Response({'message': 'Notificación marcada como leída.'},
                        status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=['post'],
        url_path='marcar-todas-leidas',
        url_name='marcar-todas-leidas'
    )
    def marcar_todas_leidas(self, request):
        """
        Marca todas las notificaciones no leídas como leídas.
        ---
        **Ejemplo:**
        ```
        POST /api/notificaciones/marcar-todas-leidas/
        ```
        """
        user = request.user
        if not self._tiene_permiso_notificaciones(user):
            return Response({'error': 'No tienes permiso para ver notificaciones.'},
                            status=status.HTTP_403_FORBIDDEN)
        queryset = Notificacion.objects.filter(leida=False)
        if not user.is_superuser:
            queryset = queryset.filter(usuario=user)

        updated = queryset.update(
            leida=True,
            leida_el=timezone.now(),
            leida_por=user
        )

        return Response(
            {'message': f'{updated} notificación(es) marcadas como leídas.'},
            status=status.HTTP_200_OK
        )
