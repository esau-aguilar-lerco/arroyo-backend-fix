from rest_framework import serializers
from apps.erp.models import Caja,Sucursal,Rutas

from apps.base.serializer import BaseSerializer, FlexiblePKRelatedField, SerializerRelatedField


class CajaSerializer(BaseSerializer):
    sucursal = SerializerRelatedField(
        queryset=Sucursal.objects.filter(status_model=Sucursal.STATUS_MODEL_ACTIVE),
        help_text=f"ID de la sucursal o dic (id: <id>) requerido si es tipo {Caja.SUCURSAL}",
        required=False,
        allow_null=True
    )
    sucursal_name = serializers.SerializerMethodField()
    ruta = SerializerRelatedField(
        queryset=Rutas.objects.filter(status_model=Rutas.STATUS_MODEL_ACTIVE),
        required=False,
        allow_null=True,
        help_text=f"ID de la ruta o dic (id: <id>) requerido si es tipo {Caja.RUTA}",
    )
    ruta_name = serializers.SerializerMethodField()
    class Meta:
        model = Caja
        fields = ['id', 'nombre','tipo',
                  'sucursal', 'sucursal_name', 'ruta', 'ruta_name',
                  'created_at', 'updated_at', 'created_by', 'updated_by', 'status_model']
        read_only_fields = ['id', 
                            'sucursal_name', 'ruta_name',
                            'created_at', 'updated_at', 'created_by', 'updated_by', 'status_model']

    def get_sucursal_name(self, obj):
        return obj.sucursal.nombre if obj.sucursal else "N/A"

    def get_ruta_name(self, obj):
        return obj.ruta.nombre if obj.ruta else "N/A"

    def validate(self, data):
        tipo = data.get('tipo', None)
        sucursal = data.get('sucursal', None)
        ruta = data.get('ruta', None)

        if tipo == Caja.SUCURSAL and not sucursal:
            raise serializers.ValidationError({
                    'sucursal': f'La sucursal es obligatoria cuando el tipo es {Caja.SUCURSAL}.'
                })
        if tipo == Caja.RUTA and not ruta:
            raise serializers.ValidationError({
                    'ruta': f'La ruta es obligatoria cuando el tipo es {Caja.RUTA}.'
                })
        return data

class CajaMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Caja
        fields = ['id', 'nombre']