from rest_framework import serializers
from apps.erp.models import Producto, Almacen
from apps.inventario.models import  LoteInventario, Transformacion
from apps.base.serializer import SerializerRelatedField
from decimal import Decimal

TRANSFORMACION = 'TRANSFORMACION'
MERMA = 'MERMA'

MOVIMIENTO_TIPOS = [
    (TRANSFORMACION, TRANSFORMACION),
    (MERMA, MERMA),
]

class LotesProductoTransformacionSerializer(serializers.Serializer):
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
        required=True,
        max_digits=15,
        decimal_places=5,
        min_value=Decimal('0.01'),
        help_text="Cantidad del lote a mover (debe ser mayor a 0)"
    )

class ProductoTransformadoMermaSerializer(serializers.Serializer):
    """
    Serializer para los productos transformados en una transformación
    """
    producto = SerializerRelatedField(
        queryset=Producto.objects.filter(status_model=Producto.STATUS_MODEL_ACTIVE),
        required=True,
        allow_null=False,
        help_text="ID o dic con el id del producto transformado"
    )
    cantidad = serializers.DecimalField(
        required=True,
        max_digits=15,
        decimal_places=5,
        min_value=Decimal('0.01'),
        help_text="Cantidad total del producto transformado (debe ser mayor a 0)"
    )


class ProductosTransformacionSerializer(serializers.Serializer):
    """
    Serializer para los productos en un movimiento de inventario
    """
    producto = SerializerRelatedField(
        queryset=Producto.objects.filter(status_model=Producto.STATUS_MODEL_ACTIVE),
        required=True,
        allow_null=False,
        help_text="ID o dic con el id del producto"
    )
    cantidad = serializers.DecimalField(
        required=True,
        max_digits=15,
        decimal_places=5,
        min_value=Decimal('0.01'),
        help_text="Cantidad total del producto a mover (debe ser mayor a 0)"
    )
    lotes = LotesProductoTransformacionSerializer(
        many=True,
        required=False,
        help_text="Lista de lotes asociados al producto"
    )
    
class TransformacionCreateSerializer(serializers.Serializer):
    """
    Serializer para una transformación de productos en inventario
    """
    almacen = SerializerRelatedField(
        queryset=Almacen.objects.filter(status_model=Almacen.STATUS_MODEL_ACTIVE),  # Se debe asignar el queryset en la vista
        required=False,
        #allow_null=False,
        help_text="ID o dic con el id del almacén donde se realiza la transformación"
    )
    tipo = serializers.ChoiceField(
        choices=MOVIMIENTO_TIPOS,
        required=True,
        help_text="Tipo de movimiento: TRANSFORMACION o MERMA"
    )
    productos_entrada = ProductosTransformacionSerializer(
        many=True,
        required=True,
        help_text="Lista de productos de entrada en la transformación"
    )
    productos_salida = ProductoTransformadoMermaSerializer(
        many=True,
        required=False,
        help_text="Producto de salida (producto nuevo) si es transformación"
    )
    
    nota = serializers.CharField(
        required=True,
        allow_blank=True,
        max_length=500,
        help_text="Nota o comentario adicional sobre la transformación"
    )
    
    #validar rl tipo si es merma no es obligatoriolos productos de salida
    def validate(self, data):
        tipo = data.get('tipo')
        productos_salida = data.get('productos_salida', [])
        if tipo == TRANSFORMACION and  len(productos_salida) == 0:
            raise serializers.ValidationError("Para una transformación, debe proporcionar al menos un producto de salida.")
        
        return data
    
    def create(self, validated_data):
        from apps.inventario.helpers.transformacion.movimientos_transformacion import (
            crear_movimiento_transformacion
        )
        
        almacen = validated_data.get('almacen', None)
        if not almacen:
            almacen = self.context['request'].user.almacen
        tipo = validated_data.get('tipo')
        productos_entrada = validated_data.get('productos_entrada', [])
        productos_salida = validated_data.get('productos_salida', [])
        nota = validated_data.get('nota', '')
        usuario = self.context['request'].user if 'request' in self.context else None
        movimiento = crear_movimiento_transformacion(
            almacen=almacen,
            tipo=tipo,
            productos_entrada=productos_entrada,
            productos_salida=productos_salida,
            nota=nota,
            usuario=usuario
        )
        
        return movimiento
    
    
#=============================================
#SERILIZERS PARA EL MODELO DE TRANSFORMACION
#=============================================

class TransformacionListSerializer(serializers.ModelSerializer):
    almacen_id = serializers.IntegerField(source='almacen.id', read_only=True)
    almacen_nombre = serializers.CharField(source='almacen.nombre', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True) 
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)  
    #productos_entrada = ProductosTransformacionSerializer(many=True, source='get_productos_entrada', read_only=True)
    #productos_salida = ProductoTransformadoMermaSerializer(many=True, source='get_productos_salida', read_only=True)
    class Meta:
        model = Transformacion
        fields = ('id', 'almacen_id', 'almacen_nombre', 'tipo', 'created_at', 'created_by', 'created_by_name')
       
class LoteProductoDetalleSerializer(serializers.Serializer):
    """Serializer para mostrar lotes en productos de transformación"""
    lote_id = serializers.IntegerField(source='lote.id', read_only=True)
    cantidad = serializers.DecimalField(max_digits=20, decimal_places=4, read_only=True)
    costo_unitario = serializers.DecimalField(max_digits=20, decimal_places=4, read_only=True)
    costo_total = serializers.DecimalField(max_digits=20, decimal_places=4, read_only=True)


class ProductoTransformacionDetalleSerializer(serializers.Serializer):
    """Serializer para mostrar productos con sus lotes en transformación"""
    producto_id = serializers.IntegerField(read_only=True)
    producto_nombre = serializers.CharField(read_only=True)
    producto_clave = serializers.CharField(read_only=True)
    unidad_medida = serializers.CharField(read_only=True, allow_null=True)
    unidad_clave = serializers.CharField(read_only=True, allow_null=True)
    cantidad_total = serializers.DecimalField(max_digits=20, decimal_places=4, read_only=True)
    lotes = LoteProductoDetalleSerializer(many=True, read_only=True)


class TransformacionDetailSerializer(serializers.ModelSerializer):
    almacen_id = serializers.IntegerField(source='almacen.id', read_only=True)
    almacen_nombre = serializers.CharField(source='almacen.nombre', read_only=True)
    created_by_id = serializers.IntegerField(source='created_by.id', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True) 
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    
    # Productos de entrada (productos que se transformaron)
    productos_entrada = serializers.SerializerMethodField()
    # Productos de salida (productos nuevos resultantes - null si es MERMA)
    productos_salida = serializers.SerializerMethodField()
    
    class Meta:
        model = Transformacion
        fields = (
            'id', 'tipo', 'referencia', 'nota',
            'almacen_id', 'almacen_nombre',
            'created_at', 'created_by_id', 'created_by_name',
            'productos_entrada', 'productos_salida'
        )
    
    def get_productos_entrada(self, obj):
        """Obtiene los productos de entrada (salida del inventario) agrupados por producto con sus lotes"""
        if not obj.movimiento_salida:
            return []
        
        productos_dict = {}
        for prod_mov in obj.movimiento_salida.productosMovimiento.all():
            producto_id = prod_mov.producto.id
            
            if producto_id not in productos_dict:
                productos_dict[producto_id] = {
                    'producto_id': producto_id,
                    'producto_nombre': prod_mov.producto.nombre,
                    'producto_clave': prod_mov.producto.codigo,
                    'unidad_medida': prod_mov.producto.unidad_sat.nombre if prod_mov.producto.unidad_sat else None,
                    'unidad_clave': prod_mov.producto.unidad_sat.clave if prod_mov.producto.unidad_sat else None,
                    'cantidad_total': Decimal('0.00'),
                    'lotes': []
                }
            
            productos_dict[producto_id]['cantidad_total'] += prod_mov.cantidad
            productos_dict[producto_id]['lotes'].append({
                'lote_id': prod_mov.lote.id if prod_mov.lote else None,
                'cantidad': prod_mov.cantidad,
                'costo_unitario': prod_mov.costo_unitario,
                'costo_total': prod_mov.costo_total
            })
        
        return list(productos_dict.values())
    
    def get_productos_salida(self, obj):
        """Obtiene los productos de salida (entrada al inventario) agrupados por producto con sus lotes"""
        if not obj.movimiento_entrada or obj.tipo == 'MERMA':
            return []
        
        productos_dict = {}
        for prod_mov in obj.movimiento_entrada.productosMovimiento.all():
            producto_id = prod_mov.producto.id
            
            if producto_id not in productos_dict:
                productos_dict[producto_id] = {
                    'producto_id': producto_id,
                    'producto_nombre': prod_mov.producto.nombre,
                    'producto_clave': prod_mov.producto.codigo,
                    'unidad_medida': prod_mov.producto.unidad_sat.nombre if prod_mov.producto.unidad_sat else None,
                    'unidad_clave': prod_mov.producto.unidad_sat.clave if prod_mov.producto.unidad_sat else None,
                    'cantidad_total': Decimal('0.00'),
                    'lotes': []
                }
            
            productos_dict[producto_id]['cantidad_total'] += prod_mov.cantidad
            productos_dict[producto_id]['lotes'].append({
                'lote_id': prod_mov.lote.id if prod_mov.lote else None,
                'cantidad': prod_mov.cantidad,
                'costo_unitario': prod_mov.costo_unitario,
                'costo_total': prod_mov.costo_total
            })
        
        return list(productos_dict.values())