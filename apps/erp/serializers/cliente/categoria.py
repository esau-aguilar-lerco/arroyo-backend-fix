from rest_framework import serializers
from apps.erp.models import CategoriaCliente

from apps.base.serializer import  BaseSerializer


class CategoriaClienteSerializer(BaseSerializer):
    class Meta:
        model = CategoriaCliente
        fields = '__all__'


class CategoriaClienteMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoriaCliente
        fields = ['id', 'nombre', 'limite_credito_min', 'limite_credito_max']