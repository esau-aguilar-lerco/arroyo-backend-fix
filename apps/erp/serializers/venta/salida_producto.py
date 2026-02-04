from rest_framework import serializers
#models
from apps.erp.models import Venta, Producto

#serializers
from apps.base.serializer import SerializerRelatedField

class SalidaProductoSerializer(serializers.Serializer):
    producto = SerializerRelatedField(queryset=Producto.objects.all(), help_text="ID del producto o dic {id: <id>}", required=True)
    cantidad = serializers.DecimalField(max_digits=20, decimal_places=2, required=True, help_text="Cantidad del producto")
    
class SalidaProductoVentaSerializer(serializers.Serializer):
    venta = SerializerRelatedField(queryset=Venta.objects.filter().all(), help_text="ID de la venta o dic {id: <id>}", required=True)
    productos_salida = SalidaProductoSerializer(many=True, required=True, help_text="Lista de productos a salir en la venta")