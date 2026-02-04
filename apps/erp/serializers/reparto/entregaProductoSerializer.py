from rest_framework import serializers
from apps.erp.models import Venta, Producto

from apps.erp.helpers.entrega_reparto import registrar_entrega_productos

class ProductosEntregaSerializer(serializers.Serializer):
    producto = serializers.PrimaryKeyRelatedField(queryset=Producto.objects.all())
    cantidad = serializers.DecimalField(max_digits=18, decimal_places=6)

class EntragaProductoRutaSerializer(serializers.Serializer):
    venta = serializers.PrimaryKeyRelatedField(queryset=Venta.objects.filter(was_preventa=True))
    productos = ProductosEntregaSerializer(many=True)
    
    
    
    
    def create(self, validated_data):
        venta = validated_data['venta']
        productos = validated_data['productos']
        
        venta_actualizada = registrar_entrega_productos(venta, productos)
        return venta_actualizada
