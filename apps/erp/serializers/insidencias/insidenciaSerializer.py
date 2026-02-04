from rest_framework import serializers
from apps.erp.models import Insidencia, InsidenciaLote


class InsidenciaMiniSerializer(serializers.ModelSerializer):
    """
    Serializer liviano para listado de insidencias
    """
    total_lotes = serializers.SerializerMethodField()
    lotes_atendidos = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    
    class Meta:
        model = Insidencia
        fields = [
            'id',
            'descripcion',
            'resuelta',
            'created_at',
            'total_lotes',
            'lotes_atendidos',
        ]
    
    def get_total_lotes(self, obj):
        return obj.lotes_insidencia.count()
    
    def get_lotes_atendidos(self, obj):
        return obj.lotes_insidencia.filter(atendida=True).count()


class InsidenciaLoteDetailSerializer(serializers.ModelSerializer):
    """
    Serializer para lotes dentro de una insidencia con info del producto
    """
    lote_id = serializers.IntegerField(source='lote.id', read_only=True)
    producto_id = serializers.IntegerField(source='lote.producto.id', read_only=True)
    producto_nombre = serializers.CharField(source='lote.producto.nombre', read_only=True)
    producto_codigo = serializers.CharField(source='lote.producto.codigo', read_only=True)
    almacen_id = serializers.IntegerField(source='lote.almacen.id', read_only=True, allow_null=True)
    almacen_nombre = serializers.CharField(source='lote.almacen.nombre', read_only=True, allow_null=True)
    cantidad_lote = serializers.DecimalField(source='lote.cantidad', max_digits=20, decimal_places=2, read_only=True)
    costo_unitario = serializers.DecimalField(source='lote.costo_unitario', max_digits=20, decimal_places=2, read_only=True)
    fecha_atencion = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True, allow_null=True)
    
    class Meta:
        model = InsidenciaLote
        fields = [
            'id',
            'lote_id',
            'producto_id',
            'producto_nombre',
            'producto_codigo',
            'almacen_id',
            'almacen_nombre',
            'cantidad',
            'cantidad_lote',
            'costo_unitario',
            'atendida',
            'fecha_atencion',
            'nota',
        ]


class InsidenciaDetailSerializer(serializers.ModelSerializer):
    """
    Serializer completo para detalle de insidencia con sus lotes y productos
    """
    lotes = InsidenciaLoteDetailSerializer(source='lotes_insidencia', many=True, read_only=True)
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    created_by_id = serializers.IntegerField(source='created_by.id', read_only=True, allow_null=True)
    created_by_name = serializers.SerializerMethodField()
    total_lotes = serializers.SerializerMethodField()
    lotes_atendidos = serializers.SerializerMethodField()
    
    class Meta:
        model = Insidencia
        fields = [
            'id',
            'descripcion',
            'solucion',
            'resuelta',
            'created_at',
            'created_by_id',
            'created_by_name',
            'total_lotes',
            'lotes_atendidos',
            'lotes',
        ]
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            full_name = obj.created_by.full_name
            return full_name() if callable(full_name) else full_name
        return None
    
    def get_total_lotes(self, obj):
        return obj.lotes_insidencia.count()
    
    def get_lotes_atendidos(self, obj):
        return obj.lotes_insidencia.filter(atendida=True).count()


class AtenderInsidenciaLoteItemSerializer(serializers.Serializer):
    """
    Serializer para un item de lote a atender
    """
    insidencia_lote_id = serializers.IntegerField(help_text="ID del InsidenciaLote a atender")
    nota = serializers.CharField(required=False, allow_blank=True, allow_null=True, help_text="Nota de atención (opcional)")


class AtenderInsidenciaLoteSerializer(serializers.Serializer):
    """
    Serializer para atender múltiples lotes de una insidencia
    """
    lotes = AtenderInsidenciaLoteItemSerializer(many=True, help_text="Lista de lotes a atender")
