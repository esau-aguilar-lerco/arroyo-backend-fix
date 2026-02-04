from rest_framework import viewsets, mixins
from apps.erp.models import CategoriaCliente
from apps.erp.serializers.cliente.categoria import CategoriaClienteSerializer,CategoriaClienteMiniSerializer
from apps.base.serachFilter import MinimalSearchFilter

class CategoriaClienteViewSet(viewsets.ModelViewSet):
    queryset = CategoriaCliente.objects.filter(status_model=CategoriaCliente.STATUS_MODEL_ACTIVE)
    serializer_class = CategoriaClienteSerializer
    filterset_fields = ['nombre']
    filter_backends = [MinimalSearchFilter]
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.status_model = CategoriaCliente.STATUS_MODEL_DELETE
        instance.save(update_fields=['status_model'])
        return Response({'detail':'Eliminado correctamente'},status=status.HTTP_200_OK)

class CategoriaClienteMiniViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = CategoriaCliente.objects.filter(status_model=CategoriaCliente.STATUS_MODEL_ACTIVE)
    serializer_class = CategoriaClienteMiniSerializer
    #permission_classes = []  # Permitir acceso sin autenticación
    pagination_class = None  # Desactivar paginación
    search_fields = ['nombre', 'id']
    filter_backends = [MinimalSearchFilter]
    
    
    