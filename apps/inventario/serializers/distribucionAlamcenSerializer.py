from rest_framework import serializers

from rest_framework.validators import UniqueValidator, UniqueTogetherValidator
from apps.base.serializer import BaseSerializer, SerializerRelatedField
from drf_spectacular.utils import extend_schema_field


#MODELS
from apps.base.models import BaseModel
from apps.inventario.models import Piso, Zona, Rack, LoteInventario
from apps.erp.models import Almacen
#SERIALIZERS
from apps.erp.serializers.almacen_serializer import AlmacenDetalleViewSerializer



class RackSerializer(BaseSerializer):

    zona = SerializerRelatedField(
        queryset=Zona.objects.filter(status_model=BaseModel.STATUS_MODEL_ACTIVE),
        required=True,
        allow_null=False,
        help_text="ID de la zona (solo activos, puede ser un entero o {\"id\": <pk>})"
    )

    class Meta:
        model = Rack
        fields = [
            "id", "created_at", "updated_at", "created_by", "updated_by",
            "status_model", "zona", "nombre", "descripcion"
        ] 


class RackMiniSerializer(serializers.ModelSerializer):
    """Serializer ligero para racks sin relaciones complejas"""
    zona = serializers.IntegerField(source='zona.id', read_only=True)
    class Meta:
        model = Rack
        fields = ["id", "nombre", "descripcion","zona"]



class ZonaSerializer(BaseSerializer):
    piso = SerializerRelatedField(
        queryset=Piso.objects.filter(status_model=BaseModel.STATUS_MODEL_ACTIVE),
        required=True,
        allow_null=False,
        help_text="ID del piso (solo activos, puede ser un entero o {\"id\": <pk>})"
    )
    
    racks = RackSerializer(many=True, read_only=True)

    class Meta:
        model = Zona
        fields = [
            "id", "created_at", "updated_at", "created_by", "updated_by",
            "status_model", "piso", "nombre", "descripcion", "racks"
        ]

class ZonaMiniSerializer(serializers.ModelSerializer):
    """Serializer ligero para zonas con información básica de racks"""
    piso = serializers.IntegerField(source='piso.id', read_only=True)
    racks = RackMiniSerializer(many=True, read_only=True)

    class Meta:
        model = Zona
        fields = ["id", "nombre", "descripcion", "racks", "piso"]



class PisoSerializer(BaseSerializer):

    class Meta:
        model = Piso
        fields = [
            "id", "created_at", "updated_at", "created_by", "updated_by",
            "status_model", "almacen", "almacen_obj", "nombre", "descripcion",
            "zonas"
        ]

    zonas = ZonaSerializer( many=True, read_only=True)

    almacen = SerializerRelatedField(
        queryset=Almacen.objects.filter(status_model=BaseModel.STATUS_MODEL_ACTIVE),
        required=True,
        allow_null=False,
        help_text="ID del almacén (solo activos, puede ser un entero o {\"id\": <pk>})"
    )

    almacen_obj = serializers.SerializerMethodField(
        help_text="Detalles del almacén"
    )

   

    @extend_schema_field(AlmacenDetalleViewSerializer)
    def get_almacen_obj(self, obj):
        if obj.almacen:
            return AlmacenDetalleViewSerializer(obj.almacen).data
        return None

    def validate(self, attrs):
        almacen = attrs.get('almacen') or getattr(self.instance, 'almacen', None)
        if almacen and not getattr(almacen, "is_cedis", False):
            raise serializers.ValidationError("El almacén seleccionado no es CEDIS.")
        return attrs

class PisoMiniSerializer(serializers.ModelSerializer):
    """Serializer ligero para pisos con información básica de zonas"""
    zonas = ZonaMiniSerializer(many=True, read_only=True)
    almacen_nombre = serializers.CharField(source='almacen.nombre', read_only=True)
    empresa_nombre = serializers.CharField(source='almacen.empresa.nombre', read_only=True)
    almacen = SerializerRelatedField(
        queryset=Almacen.objects.filter(status_model=BaseModel.STATUS_MODEL_ACTIVE),
        required=True,
        allow_null=False,
        help_text="ID del almacén (solo activos, puede ser un entero o {\"id\": <pk>})"
    )

    
    
    class Meta:
        model = Piso
        fields = ["id", "nombre", "descripcion", "almacen_nombre", "empresa_nombre", "zonas", "almacen"]





















class LoteInventarioSerializer(BaseSerializer):
    class Meta:
        model = LoteInventario
        fields = '__all__'
