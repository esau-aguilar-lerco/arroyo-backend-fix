from rest_framework import serializers
from apps.erp.models import Producto, Almacen
from apps.inventario.models import (MovimientoInventario, LoteInventario, SolicitudTraspaso)
#from ..helpers.movimientoSalida import movimento_inventario
from apps.base.serializer import FlexiblePKRelatedField


#SERIALIZERS SOLO PARA VISUALIZAR MOVIMIENTOS PRINCIPALES

class LoteMovimientoSerializer(serializers.Serializer):
    lote = serializers.CharField(help_text="Número de lote")
    cantidad = serializers.DecimalField(max_digits=20, decimal_places=4, help_text="Cantidad a mover del lote")
    
    
class ProductoMovimientoSerializer(serializers.Serializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    unidad_medida = serializers.CharField(source='producto.unidad_sat.nombre', read_only=True, allow_null=True)
    unidad_clave = serializers.CharField(source='producto.unidad_sat.clave', read_only=True, allow_null=True)
    producto = serializers.CharField(source='producto.id', read_only=True)
    cantidad = serializers.DecimalField(max_digits=20, decimal_places=4, help_text="Cantidad del producto a mover")
    lotes = LoteMovimientoSerializer(many=True, help_text="Lista de lotes asociados al producto")


class MovimientoPrincipalSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    detalle_nota = serializers.CharField(read_only=True)
    folio = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    
    almacen_salida = serializers.CharField(source='almacen.nombre', read_only=True)
    almacen_destino = serializers.CharField(source='almacen_destino.nombre', read_only=True, allow_null=True)
    movimiento = serializers.CharField(source='get_movimiento_display', read_only=True)
    tipo = serializers.CharField(source='get_tipo_display', read_only=True)
    referencia = serializers.CharField(read_only=True)
    cantidad = serializers.DecimalField(max_digits=20, decimal_places=4, read_only=True)
    nota = serializers.CharField(read_only=True)
    productos = ProductoMovimientoSerializer(many=True, help_text="Lista de productos en el movimiento")





class MovimimientosMiniSerializer(serializers.ModelSerializer):
    almacen_origen = serializers.SerializerMethodField()
    almacen_destino = serializers.SerializerMethodField()
    folio = serializers.SerializerMethodField()
    
    detalle_nota = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True) 
    class Meta:
        model = MovimientoInventario
        fields = ['id','folio', 'referencia', 'tipo', 'movimiento','fase','almacen_origen','almacen_destino','created_at','detalle_nota']
        
        
    def get_almacen_origen(self, obj):
        if obj.almacen:
            return obj.almacen.nombre
        
        return ''
    
    def get_almacen_destino(self, obj):
        if obj.almacen_destino:
            return obj.almacen_destino.nombre
        return ''
    
    def get_folio(self, obj):
        return obj.folio
    
    def get_detalle_nota(self, obj):
        return obj.detalle_nota if obj.detalle_nota else ''
        
        
#=====================================================================
#           SERIALIZER PARA ENTRADA
#======================================================================
class LoteEntradaSerializer(serializers.Serializer):
    lote = FlexiblePKRelatedField(queryset=LoteInventario.objects.all(), help_text="Lote relacionado")
    cantidad = serializers.DecimalField(max_digits=20, decimal_places=4, help_text="Cantidad a ingresar del lote")

class ProductoEntradaSerializer(serializers.Serializer):
    producto = FlexiblePKRelatedField(queryset=Producto.objects.all(), help_text="Producto relacionado")
    cantidad = serializers.DecimalField(max_digits=20, decimal_places=4, help_text="Cantidad del producto a ingresar")
    lotes = LoteEntradaSerializer(many=True, help_text="Lista de lotes asociados al producto")
    
    def to_internal_value(self, data):
        # Redondear cantidad antes de validar
        if 'cantidad' in data:
            try:
                from decimal import Decimal, ROUND_HALF_UP
                cantidad = Decimal(str(data['cantidad']))
                data['cantidad'] = cantidad.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
            except (ValueError, TypeError, KeyError):
                pass  # Dejar que el validador maneje el error
        
        return super().to_internal_value(data)
class MovimientoEntradaSerializer(serializers.Serializer):
    solicitud_traspaso = FlexiblePKRelatedField(queryset=SolicitudTraspaso.objects.all(), help_text="Solicitud de traspaso relacionada id o {\"id\": <pk>}", required=False, allow_null=True)
    movimiento = FlexiblePKRelatedField(queryset=MovimientoInventario.objects.exclude(fase=MovimientoInventario.FASE_TERMINADA), help_text="Movimiento de entrada relacionado")
    productos = ProductoEntradaSerializer(many=True, help_text="Lista de productos en el movimiento de entrada")
    
    


#=====================================================================
#           SERIALIZER PARA MOVIMIENTOS LISTA Y RETRIVE 
#======================================================================

class MovimientoInventarioListSerializer(serializers.ModelSerializer):
    almacen_nombre = serializers.CharField(source='almacen.nombre', read_only=True)
    almacen_destino_nombre = serializers.CharField(source='almacen_destino.nombre', read_only=True, allow_null=True)
    folio = serializers.SerializerMethodField()
    productos = ProductoMovimientoSerializer(many=True, help_text="Lista de productos en el movimiento")
    class Meta:
        model = MovimientoInventario
        fields = ['id', 'referencia','folio' 'tipo', 'movimiento','nota',
                  'almacen_nombre', 'almacen_destino_nombre', 'cantidad', 'fase', 'created_at',
                  'productos']

    
    def get_folio(self, obj):
        return obj.folio