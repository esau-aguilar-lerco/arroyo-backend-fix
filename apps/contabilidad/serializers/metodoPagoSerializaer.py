from rest_framework import serializers

from apps.contabilidad.models import MetodoPago




class MetodoPagoMiniSerializer(serializers.ModelSerializer):
    """
    Serializer mini para métodos de pago
    """
    class Meta:
        model = MetodoPago
        fields = ['id', 'nombre','is_credito']

class MetodoPagoMiniSerializer(serializers.ModelSerializer):
    """
    Serializer mini para método de pago (solo lectura)
    """
    class Meta:
        model = MetodoPago
        fields = ('id', 'nombre')
        read_only_fields = ('id', 'nombre',)
