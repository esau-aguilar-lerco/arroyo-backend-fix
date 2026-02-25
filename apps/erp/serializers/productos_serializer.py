from rest_framework import serializers
from decimal import Decimal

#MODELS
from apps.base.models import BaseModel
from ..models import Categoria, Producto, Proveedor
from apps.contabilidad.models import UnidadSat

#SERIALIZERS
from apps.base.serializer import BaseSerializer, SerializerRelatedField,FlexiblePKRelatedField
from .proveedor_serializer import ProveedorMiniSerializer, ProveedorSerializer, DireccionProveedorSerializer
from apps.contabilidad.serializers.unidadSatSerializer import UnidadSatMiniSerializer


class CategoriaSerializer(BaseSerializer):
    class Meta:
        model = Categoria
        fields = '__all__'
       

"""
==============================================
    CATEGORIA MINI SERIALIZER
==============================================
"""
class CategoriaMiniSerializer(BaseSerializer):
    class Meta:
        model = Categoria
        fields = ('id', 'nombre')
        read_only_fields = ('id','nombre')




class ProductoSerializer(BaseSerializer):
    #categoria = serializers.PrimaryKeyRelatedField(queryset=Categoria.objects.all(), write_only=True)

    categoria = SerializerRelatedField(
        queryset=Categoria.objects.filter(status_model=BaseModel.STATUS_MODEL_ACTIVE),
        required=True,
        allow_null=False,
        help_text="ID de la categoría (solo activos, puede ser un entero o {\"id\": <pk>})"
    )
    categoria_obj = CategoriaMiniSerializer(read_only=True, source='categoria')


    unidad_sat = SerializerRelatedField(
        queryset=UnidadSat.objects.all(),
        required=True,
        allow_null=False,
        help_text="ID de la unidad de medida (solo activos, puede ser un entero o {\"id\": <pk>})"
    )
    unidad_sat_obj = UnidadSatMiniSerializer(read_only=True, source='unidad_sat')




   
    # Explicitly declare decimal fields to ensure correct type in schema and docs
    stock_minimo = serializers.FloatField(required=False)
    iva = serializers.FloatField(required=False, default=0.0, allow_null=True)
    precio_base = serializers.FloatField(required=False, default=0.0, read_only=True)
    otro_impuesto = serializers.FloatField(required=False, default=0.0, allow_null=True)
    precio_mayoreo = serializers.FloatField(required=True)
    precio_publico = serializers.FloatField(required=True)
    horas_caducidad = serializers.IntegerField(required=False, allow_null=False, default=0, help_text="Días para que un lote caduque después de su creación. 0 = No caduca")

    proveedores = FlexiblePKRelatedField(
        queryset=Proveedor.objects.exclude(status_model=Proveedor.STATUS_MODEL_DELETE),
        many=True,
        required=True,
        help_text="IDs de los proveedores (solo activos, puede ser un array de enteros o un array de [ {\"id\": <pk> } ])"
    )
    proveedores_obj = ProveedorMiniSerializer(many=True, read_only=True, source='proveedores')

    class Meta:
        model = Producto
        #fields = '__all__'
        exclude = ('imagen',)  # Exclude image field if not needed in the API
        read_only_fields = ('created_at', 'updated_at', 'created_by', 'updated_by', 'status_model','codigo')
        extra_fields = [ 'proveedores_detalle', 'unidad_sat_detalle']

    def _to_decimal_or_zero(self, value):
        if value is None:
            return Decimal('0.00')
        try:
            return Decimal(str(value))
        except Exception:
            return Decimal('0.00')

    def validate(self, attrs):
        """
        Reglas generales de precio de venta:
        - Ningún precio de venta (mayoreo/menudeo) puede ser <= costo para Arroyo.
        - Se valida contra costo ponderado cuando el producto ya existe.
        """
        instance = getattr(self, 'instance', None)
        costo_arroyo = instance.get_costo_arroyo() if instance else Decimal('0.00')
        # Si en el futuro se habilita edición de precio_base, usarlo como costo explícito.
        if 'precio_base' in attrs and attrs.get('precio_base') is not None:
            costo_arroyo = max(costo_arroyo, self._to_decimal_or_zero(attrs.get('precio_base')))

        validaciones = [
            ('precio_mayoreo', 'MAYOREO'),
            ('precio_publico', 'MENUDEO'),
        ]
        for field_name, label in validaciones:
            if field_name not in attrs and instance is not None:
                continue
            precio = self._to_decimal_or_zero(attrs.get(field_name, getattr(instance, field_name, None)))
            if precio < 0:
                raise serializers.ValidationError({field_name: f'El precio {label} no puede ser negativo.'})
            if costo_arroyo > 0 and precio <= costo_arroyo:
                raise serializers.ValidationError({
                    field_name: (
                        f'El precio {label} debe ser mayor al costo para Arroyo '
                        f'(${costo_arroyo:.2f}).'
                    )
                })
        return attrs

    def to_representation(self, instance):
        """
        Unifica salida de precios conforme a reglas globales:
        - precio_base => costo para Arroyo (ponderado)
        - precio_mayoreo / precio_publico => precios finales vigentes (editables)
        - *_calculado => precios sugeridos por fórmula
        """
        data = super().to_representation(instance)
        try:
            costo = float(instance.get_costo_arroyo())
            data['precio_base'] = costo
            data['precio_unitario'] = costo
        except Exception:
            pass
        try:
            data['precio_mayoreo_calculado'] = float(instance.get_precio_mayoreo_calculado())
        except Exception:
            pass
        try:
            data['precio_publico_calculado'] = float(instance.get_precio_menudeo_calculado())
        except Exception:
            pass
        try:
            data['precio_mayoreo'] = float(instance.get_precio_mayoreo())
        except Exception:
            pass
        try:
            data['precio_publico'] = float(instance.get_precio_menudeo())
        except Exception:
            pass
        return data

class   ProductoMiniSerializer(BaseSerializer):
    unidad_sat_clave = serializers.CharField(source='unidad_sat.clave', read_only=True)
    unidad_sat_nombre = serializers.CharField(source='unidad_sat.nombre', read_only=True)
    precio_base = serializers.SerializerMethodField()
    inventario = serializers.SerializerMethodField()
    
    class Meta:
        model = Producto
        fields = ('id', 'nombre', 'codigo', 'unidad_sat_clave', 'unidad_sat_nombre', 'precio_base', 'inventario')
        read_only_fields = ('id', 'nombre', 'codigo', 'unidad_sat_clave', 'unidad_sat_nombre', 'precio_base', 'inventario')
    
    def get_precio_base(self, obj):
        """
        Retorna el precio según el cliente_id del contexto
        Si no hay cliente_id, retorna el precio unitario base
        """

        
        if not self.context:
           return float(obj.get_precio_menudeo())
        
        cliente_id = self.context.get('cliente_id', None)
        is_compras = self.context.get('is_compras', False)
        if cliente_id:
            try:
                precio = obj.get_mi_precio_cliente(int(cliente_id))
                return float(precio) if precio else float(obj.get_precio_menudeo())
            except Exception as e:
                #import traceback
                #traceback.print_exc()
                return float(obj.get_precio_menudeo())
        if is_compras:
            try:
                # Regla global: precio base = costo para Arroyo (promedio ponderado últimas compras).
                return float(obj.get_costo_arroyo())
            except Exception:
                return float(obj.get_costo_arroyo())
                #import traceback
                #traceback.print_exc()
                #return 0.0
       
        # Sin cliente en contexto, por regla de negocio el precio de referencia
        # para venta debe ser menudeo.
        return float(obj.get_precio_menudeo())

    def get_inventario(self, obj):
        """
        Retorna el inventario según el almacen_id del contexto
        Si no hay almacen_id, retorna el inventario total
        """
        #print(f"🔍 Context en get_inventario: {self.context}")

        if not self.context:
            return 0
        
        almacen_id = self.context.get('almacen_id', None)
        #print(f"🔍 almacen_id del contexto: {almacen_id}")

        if almacen_id:
            try:
                inventario = obj.get_mi_stock_almacen(int(almacen_id))
                return float(inventario) if inventario else 0.0
            except Exception as e:
                return 0.0

        # Sin almacen_id, retornar inventario total
        #print(f"ℹ️ Sin almacen_id, usando inventario total")
        
        return 0.0
class ProductoInfoSerializer(serializers.Serializer):
    """Serializer para la información del producto"""
    id = serializers.IntegerField()
    nombre = serializers.CharField()
    codigo = serializers.CharField()
    categoria = serializers.CharField(allow_null=True)
    clave = serializers.CharField(allow_null=True)
    unidad = serializers.CharField(allow_null=True)
    precio_unitario = serializers.FloatField()
    precio_base = serializers.FloatField()
    precio_mayoreo_calculado = serializers.FloatField()
    precio_mayoreo = serializers.FloatField()
    precio_semi_mayoreo_calculado = serializers.FloatField()
    precio_publico = serializers.FloatField()
    precio_publico_calculado = serializers.FloatField()
    precio_semi_mayoreo = serializers.FloatField()
    ultimo_precio = serializers.FloatField()


class InventarioAlmacenSerializer(serializers.Serializer):
    """Serializer para el inventario por almacén"""
    almacen_id = serializers.IntegerField()
    almacen_nombre = serializers.CharField()
    cantidad_total = serializers.FloatField()
    lotes_count = serializers.IntegerField()
    costo_promedio = serializers.FloatField()


class ResumenGlobalSerializer(serializers.Serializer):
    """Serializer para el resumen global"""
    total_stock = serializers.FloatField()
    almacenes_con_stock = serializers.IntegerField()
    valor_inventario = serializers.FloatField()


class ProductoInventarioAlamcenSerializer(serializers.Serializer):
    """
    Serializer que replica exactamente la estructura de respuesta de ProductoInventarioAPIView
    """
    
    # Información del producto
    producto = ProductoInfoSerializer()
    
    # Inventario por almacén específico (puede ser null)
    inventario_almacen = InventarioAlmacenSerializer(allow_null=True)
    
    # Resumen global
    resumen_global = ResumenGlobalSerializer()
    
    def to_representation(self, instance):
        """
        Convierte los datos del objeto a la representación final
        """
        modelo_producto = instance.get('modelo_producto')
        ultimo_precio = instance.get('ultimo_precio', 0)
        inventario_almacen = instance.get('inventario_almacen')
        resumen_global = instance.get('resumen_global')
        
        # Información del producto
        producto_data = {
            'id': modelo_producto.id,
            'codigo': modelo_producto.codigo,
            'nombre': modelo_producto.nombre,
            'categoria': modelo_producto.categoria.nombre if modelo_producto.categoria else None,
            'clave': modelo_producto.unidad_sat.clave if modelo_producto.unidad_sat else None,
            'unidad': modelo_producto.unidad_sat.nombre if modelo_producto.unidad_sat else None,
            'precio_unitario': float(modelo_producto.get_precio_unitario()),
            'precio_base': float(modelo_producto.get_costo_arroyo()),
            'precio_mayoreo_calculado': float(modelo_producto.get_precio_mayoreo_calculado()),
            'precio_mayoreo': float(modelo_producto.get_precio_mayoreo()),
            'precio_semi_mayoreo_calculado': float(modelo_producto.get_precio_semi_mayoreo_calculado()),
            'precio_publico': float(modelo_producto.get_precio_menudeo()),
            'precio_publico_calculado': float(modelo_producto.get_precio_menudeo_calculado()),
            'precio_semi_mayoreo': float(modelo_producto.get_precio_semi_mayoreo()),
            'ultimo_precio': float(ultimo_precio)
        }
        
        return {
            'producto': producto_data,
            'inventario_almacen': inventario_almacen,
            'resumen_global': resumen_global
        }
