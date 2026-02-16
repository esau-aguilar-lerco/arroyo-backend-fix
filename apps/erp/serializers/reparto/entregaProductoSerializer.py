from rest_framework import serializers

from apps.erp.models import Venta, Producto
from apps.erp.helpers.entrega_reparto import registrar_entrega_productos


class ProductosEntregaSerializer(serializers.Serializer):
    producto = serializers.PrimaryKeyRelatedField(queryset=Producto.objects.all())
    cantidad = serializers.DecimalField(max_digits=18, decimal_places=6, required=False)
    cantidad_entregada = serializers.DecimalField(max_digits=18, decimal_places=6, required=False)
    devolucion = serializers.DecimalField(max_digits=18, decimal_places=6, required=False, default=0)
    observacion = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs):
        if attrs.get('cantidad') is None and attrs.get('cantidad_entregada') is None:
            raise serializers.ValidationError("Debe enviar 'cantidad' o 'cantidad_entregada'.")
        return attrs


class EntragaProductoRutaSerializer(serializers.Serializer):
    venta = serializers.PrimaryKeyRelatedField(queryset=Venta.objects.filter(was_preventa=True))
    productos = ProductosEntregaSerializer(many=True)
    observaciones = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def create(self, validated_data):
        venta = validated_data['venta']
        productos = validated_data['productos']
        observaciones = validated_data.get('observaciones')

        usuario = None
        request = self.context.get('request')
        if request:
            usuario = request.user

        return registrar_entrega_productos(
            venta=venta,
            productos_entregados=productos,
            usuario=usuario,
            observaciones=observaciones,
        )
