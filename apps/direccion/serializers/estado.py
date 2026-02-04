from rest_framework import serializers
from apps.direccion.models import Estado

class EstadoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Estado
        fields = ['id', 'nombre', 'clave']