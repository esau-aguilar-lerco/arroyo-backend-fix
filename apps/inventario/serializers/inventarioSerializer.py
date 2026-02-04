
from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from drf_spectacular.utils import extend_schema_field


"""
*******************************************************************************************************
                            SERIALIZERS DE CONSULTA DE INVENTARIO 
*******************************************************************************************************
"""

"""
==============================================
        SERIALIZERS DE DETALLE DE INVENTARIO POR ALMACEN
==============================================
"""
class LoteInventarioSerializer(serializers.Serializer):
    """
    Serializer para los lotes de inventario
    """
    id = serializers.IntegerField(read_only=True)
    producto_id = serializers.IntegerField(source='producto.id', read_only=True)
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    unidad_medida = serializers.CharField(source='producto.unidad_sat.nombre', read_only=True, allow_null=True)
    unidad_clave = serializers.CharField(source='producto.unidad_sat.clave', read_only=True, allow_null=True)
    cantidad = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    costo_unitario = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    fecha_vencimiento = serializers.DateTimeField(read_only=True, format="%Y-%m-%d %H:%M:%S", allow_null=True)
    fecha_ingreso = serializers.DateTimeField(read_only=True, format="%Y-%m-%d %H:%M:%S", allow_null=True)
    ubicacion = serializers.CharField(source='ubicacion.nombre', read_only=True, allow_null=True)
    
    # Calcular estado del lote
    estado = serializers.SerializerMethodField()
    
    def get_estado(self, obj):
        """
        Determinar el estado del lote basado en la fecha de vencimiento
        """
        
        
        if not obj.fecha_vencimiento:
            return "SIN VENCIMIENTO"
            
        ahora = timezone.now()
        proximo_vencer = ahora + timedelta(days=1)
        
        if obj.fecha_vencimiento < ahora:
            return "VENCIDO"
        elif obj.fecha_vencimiento <= proximo_vencer:
            return "POR VENCER"
        else:
            return "ACTIVO"



class ProductoInventarioSerializer(serializers.Serializer):
    """
    Serializer para productos en inventario con sus totales
    """
    producto_id = serializers.IntegerField(read_only=True)
    codigo = serializers.CharField(read_only=True)
    producto_nombre = serializers.CharField(read_only=True)
    cantidad_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    valor_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    numero_lotes = serializers.IntegerField(read_only=True, help_text="Número de lotes asociados a este producto activos")
    unidad_medida = serializers.CharField(read_only=True)
    unidad_clave = serializers.CharField(read_only=True)
    #cantidad_disponible = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    lotes_detalle = serializers.SerializerMethodField()

    def get_lotes_detalle(self, obj):
        """
        Obtener detalles de los lotes para este producto
        """
        # Debug: Imprimir el tipo de obj y sus atributos
        #print(f"DEBUG: obj type: {type(obj)}")
        #print(f"DEBUG: obj attributes: {dir(obj) if hasattr(obj, '__dict__') else 'No attributes'}")
        
        # Si obj es un diccionario
        if isinstance(obj, dict):
            lotes_relacionados = obj.get('lotes_relacionados', [])
            #print(f"DEBUG SERIALIZER: lotes_relacionados from dict: {len(lotes_relacionados)} items")
        # Si obj es un objeto
        elif hasattr(obj, 'lotes_relacionados'):
            lotes_relacionados = obj.lotes_relacionados
            #print(f"DEBUG SERIALIZER: lotes_relacionados from object: {len(lotes_relacionados)} items")
        else:
            #print("DEBUG SERIALIZER: No lotes_relacionados found")
            return []
            
        # Verificar que tenemos datos para serializar
        if not lotes_relacionados:
            return []
            
        try:
            serialized_data = LoteInventarioSerializer(lotes_relacionados, many=True).data
            #print(f"DEBUG SERIALIZER: Successfully serialized {len(serialized_data)} lotes")
            return serialized_data
        except Exception as e:
            #print(f"DEBUG SERIALIZER: Error serializing: {e}")
            return []



class InventarioPorAlmacenSerializer(serializers.Serializer):
    """
    Serializer principal para mostrar inventario completo por almacén
    """
    almacen_id = serializers.IntegerField(read_only=True)
    almacen_nombre = serializers.CharField(read_only=True)
    almacen_tipo = serializers.CharField(read_only=True)
    fecha_consulta = serializers.DateTimeField(read_only=True)
    
    # Totales del almacén
    total_productos = serializers.IntegerField(read_only=True)
    total_lotes = serializers.IntegerField(read_only=True)
    valor_total_inventario = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    
    # Productos en inventario
    productos = ProductoInventarioSerializer(many=True, read_only=True)


"""
==============================================
        SERIALIZERS DE DETALLE DE INVENTARIO POR PRODUCTO
==============================================
"""

class AlmacenInventarioSerializer(serializers.Serializer):
    """
    Serializer para almacenes con inventario de un producto específico
    """
    almacen_id = serializers.IntegerField(read_only=True)
    almacen_nombre = serializers.CharField(read_only=True)
    almacen_tipo = serializers.CharField(read_only=True)
    cantidad_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    valor_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    numero_lotes = serializers.IntegerField(read_only=True)
    lotes_detalle = serializers.SerializerMethodField()

    @extend_schema_field(LoteInventarioSerializer(many=True))
    def get_lotes_detalle(self, obj):
        """
        Obtener detalles de los lotes para este almacén
        """
        if hasattr(obj, 'lotes_relacionados'):
            return LoteInventarioSerializer(obj.lotes_relacionados, many=True).data
        return []

class DetalleInventarioPorProductoSerializer(serializers.Serializer):
    """
    Serializer para mostrar el inventario de un producto específico en todos los almacenes
    """
    producto_id = serializers.IntegerField(read_only=True)
    producto_nombre = serializers.CharField(read_only=True)
    producto_codigo = serializers.CharField(read_only=True)
    precio_publico = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    precio_mayoreo = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    costo_ultimo_lote = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    unidad_medida = serializers.CharField(read_only=True)
    unidad_clave = serializers.CharField(read_only=True)
    fecha_consulta = serializers.DateTimeField(read_only=True)
    
    # Totales del producto
    cantidad_total_global = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    #                      valor_total_global = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    total_almacenes = serializers.IntegerField(read_only=True)
    total_lotes_global = serializers.IntegerField(read_only=True)
    
    # Inventario por almacén
    almacenes = AlmacenInventarioSerializer(many=True, read_only=True)
    
   
"""
==============================================
        SERIALIZERS DE DETALLE DE INVENTARIO POR rack
==============================================
"""

class DetalleInventarioRackSerializer(serializers.Serializer):
    """
    Serializer para los detalles de inventario de un rack específico
    """
    id = serializers.IntegerField(read_only=True)
    nombre = serializers.CharField(read_only=True)
    fecha_consulta = serializers.DateTimeField(read_only=True)
    total_productos = serializers.IntegerField(read_only=True)
    total_lotes = serializers.IntegerField(read_only=True)
    cantidad_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    valor_total = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    productos = ProductoInventarioSerializer(many=True, read_only=True)

