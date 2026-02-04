from rest_framework import serializers

from apps.direccion.models import Estado, Municipio, CodigoPostal, Colonia
class EstadoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Estado
        fields = ['id', 'nombre']
        #read_only_fields = ['id', 'nombre']

class MunicipioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Municipio
        fields = ['id', 'nombre']
        #read_only_fields = ['id', 'nombre']

class CodigoPostalSerializer(serializers.ModelSerializer):
    class Meta:
        model = CodigoPostal
        fields = ['id', 'codigo_postal']
        #read_only_fields = ['id', 'codigo_postal']

class ColoniaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Colonia
        fields = ['id', 'd_asenta']
        #read_only_fields = ['id', 'd_asenta']