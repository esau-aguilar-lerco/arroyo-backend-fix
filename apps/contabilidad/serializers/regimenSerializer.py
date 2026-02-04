from rest_framework import serializers
from apps.base.serializer import BaseSerializer 
from apps.contabilidad.models import RegimenFiscal

class RegimenFiscalSerializer(BaseSerializer):
    class Meta:
        model = RegimenFiscal
        fields = '__all__'

class RegimenFiscalMiniSerializer(BaseSerializer):
    class Meta:
        model = RegimenFiscal
        fields = ('id', 'codigo', 'nombre')

class RegimenFiscalDetailSerializer(BaseSerializer):
    class Meta:
        model = RegimenFiscal
        fields = ('id', 'codigo', 'nombre')
        read_only_fields = ('codigo', 'nombre')



class RegimenFiscalRelatedField(serializers.PrimaryKeyRelatedField):
    """PrimaryKeyRelatedField que acepta tanto un entero (pk) como un dict {"id": pk}.

    - to_internal_value: si recibe dict, extrae 'id' y valida la existencia.
    - to_representation: mantiene el comportamiento por defecto (retorna el pk).
    """
    def to_internal_value(self, data):
        # Aceptar payload como {"id": 1}
        if isinstance(data, dict):
            pk = data.get('id')
            if pk is None:
                raise serializers.ValidationError({"regimen_fiscal": "Se requiere el campo 'id' dentro de regimen_fiscal."})
            return super().to_internal_value(pk)
        return super().to_internal_value(data)