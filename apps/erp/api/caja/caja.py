from rest_framework import viewsets, mixins
from rest_framework.response import Response
from rest_framework import status


from apps.erp.models import Caja
from apps.erp.serializers.caja.caja import CajaSerializer, CajaMiniSerializer

from apps.base.serachFilter import MinimalSearchFilter




class CajaViewSet(viewsets.ModelViewSet):
    queryset = Caja.objects.filter(status_model='ACTIVE')
    serializer_class = CajaSerializer
    #permission_classes = []
    filter_backends = [MinimalSearchFilter]
    search_fields = ['nombre', 'id']

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        #instance.horas_caducidad = instance.horas_caducidad / 24
        if self.is_respuesta_404():
            return self.respuesta_404()

        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        if self.is_respuesta_404():
            return self.respuesta_404()

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if self.is_respuesta_404():
            return self.respuesta_404()

        instance.status_model = Caja.STATUS_MODEL_DELETE
        instance.save(update_fields=['status_model'])
        return Response({'detail':'Eliminado correctamente'},status=status.HTTP_200_OK)


    def is_respuesta_404(self):
        instance = self.get_object()
        return instance.status_model == Caja.STATUS_MODEL_DELETE

    def respuesta_404(self):
        return Response(
            {"detail": "No encontrado."},
            status=status.HTTP_404_NOT_FOUND
        )


class CajaMiniViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Caja.objects.filter(status_model=Caja.STATUS_MODEL_ACTIVE)
    serializer_class = CajaMiniSerializer
    #permission_classes = []  # Permitir acceso sin autenticación    
    pagination_class = None  # Desactivar paginación
    search_fields = ['nombre', 'id']
    filter_backends = [MinimalSearchFilter]
    