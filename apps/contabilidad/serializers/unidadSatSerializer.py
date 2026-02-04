from apps.base.serializer import BaseSerializer
from apps.contabilidad.models import UnidadSat

class UnidadSatSerializer(BaseSerializer):
    class Meta:
        model = UnidadSat
        fields = '__all__'

class UnidadSatMiniSerializer(BaseSerializer):
    class Meta:
        model = UnidadSat
        fields = ('id', 'clave', 'nombre', 'name')
        read_only_fields = ('name','clave', 'nombre', 'id')