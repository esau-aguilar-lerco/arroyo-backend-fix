from rest_framework import serializers
from decimal import Decimal
from apps.inventario.models import Producto, LoteInventario
from apps.base.serializer import SerializerRelatedField
from apps.erp.models import Rutas,Almacen



class LotesMovimientoSerializer(serializers.Serializer):
    """
    Serializer para los lotes en un movimiento de inventario
    """
    lote = SerializerRelatedField(
        queryset=LoteInventario.objects.filter(status_model=LoteInventario.STATUS_MODEL_ACTIVE),
        required=True,
        allow_null=False,
        help_text="ID o dic con el id del lote"
    )
    cantidad = serializers.DecimalField(
        max_digits=15,
        decimal_places=5,
        min_value=Decimal('0.01'),
        help_text="Cantidad del lote a mover (debe ser mayor a 0)"
    )
    
class ProductosMovimientoLoteSerializer(serializers.Serializer):
    producto = SerializerRelatedField(
        queryset=Producto.objects.filter(status_model=Producto.STATUS_MODEL_ACTIVE),
        required=True,
        allow_null=False,
        help_text="ID o dic con el id del producto"
    )
    cantidad = serializers.DecimalField(
        max_digits=15,
        decimal_places=5,
        min_value=Decimal('0.01'),
        help_text="Cantidad total del producto a mover (debe ser mayor a 0)"
    )
    lotes = LotesMovimientoSerializer(
        many=True,
        required=True,
        help_text="Lista de lotes para este producto"
    )

class MovimientoEmbarqueCreateRutaSerializer(serializers.Serializer):
    
    ruta = SerializerRelatedField(
        queryset=Rutas.objects.filter(status_model=Rutas.STATUS_MODEL_ACTIVE).all(),
        help_text="ID de la ruta o dic {id: <id>}",
        required=True
    )
    
    productos_embarque = ProductosMovimientoLoteSerializer(
        many=True,
        required=True,
        help_text="Lista de productos a mover en el embarque con sus respectivos lotes"
    )
    
    productos_tara = ProductosMovimientoLoteSerializer(
        many=True,
        required=False,
        help_text="Lista de productos en tara abierta con sus respectivos lotes (opcional)"
    )
    
    
    def create(self, validated_data):
        #user = self.context['request'].user
        user = self.context.get('user')
        
        
        #return super().create(validated_data)
    
    