from rest_framework import serializers
from apps.erp.models import incidencia, IncidenciaLote


TIPIFICACIONES_INCIDENCIA = [
    "Producto danado",
    "Caducado/Vencido",
    "Empaque danado/abierto",
    "Temperatura inadecuada",
    "Faltante de producto",
    "Producto incorrecto",
    "Contaminacion",
    "Otro",
]


class IncidenciaMiniSerializer(serializers.ModelSerializer):
    """
    Serializer liviano para listado de incidencias
    """
    total_lotes = serializers.SerializerMethodField()
    lotes_atendidos = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    
    class Meta:
        model = incidencia
        fields = [
            'id',
            'descripcion',
            'resuelta',
            'created_at',
            'total_lotes',
            'lotes_atendidos',
        ]
    
    def get_total_lotes(self, obj):
        return obj.lotes_incidencia.count()
    
    def get_lotes_atendidos(self, obj):
        return obj.lotes_incidencia.filter(atendida=True).count()


class IncidenciaLoteDetailSerializer(serializers.ModelSerializer):
    """
    Serializer para lotes dentro de una incidencia con info del producto
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
        model = IncidenciaLote
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


class IncidenciaDetailSerializer(serializers.ModelSerializer):
    """
    Serializer completo para detalle de incidencia con sus lotes y productos
    """
    lotes = IncidenciaLoteDetailSerializer(source='lotes_incidencia', many=True, read_only=True)
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    created_by_id = serializers.IntegerField(source='created_by.id', read_only=True, allow_null=True)
    created_by_name = serializers.SerializerMethodField()
    total_lotes = serializers.SerializerMethodField()
    lotes_atendidos = serializers.SerializerMethodField()
    
    class Meta:
        model = incidencia
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
        return obj.lotes_incidencia.count()
    
    def get_lotes_atendidos(self, obj):
        return obj.lotes_incidencia.filter(atendida=True).count()


class AtenderIncidenciaLoteItemSerializer(serializers.Serializer):
    """
    Serializer para un item de lote a atender
    """
    incidencia_lote_id = serializers.IntegerField(help_text="ID del IncidenciaLote a atender")
    tipificacion = serializers.ChoiceField(
        choices=[(t, t) for t in TIPIFICACIONES_INCIDENCIA],
        help_text="Tipificacion obligatoria para describir la incidencia"
    )
    nota = serializers.CharField(required=False, allow_blank=True, allow_null=True, help_text="Nota de atención (opcional)")


class AtenderIncidenciaLoteSerializer(serializers.Serializer):
    """
    Serializer para atender múltiples lotes de una incidencia
    """
    lotes = AtenderIncidenciaLoteItemSerializer(many=True, help_text="Lista de lotes a atender")
