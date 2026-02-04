from rest_framework import serializers
from decimal import Decimal

# MODELS
from apps.base.models import BaseModel
from apps.base.serializer import BaseSerializer, SerializerRelatedField
from apps.erp.models import Producto
from ..models import ProductosSolicitud


class ProductosSolicitudMiniSerializer(BaseSerializer):
    """
    Serializer mini para listar solicitudes básicas
    """
    nombre = serializers.CharField(source='producto.nombre', read_only=True)
    codigo = serializers.CharField(source='producto.codigo', read_only=True)
    unidad_sat_clave = serializers.CharField(source='producto.unidad_sat.clave', read_only=True)
    unidad_sat_nombre = serializers.CharField(source='producto.unidad_sat.nombre', read_only=True)  
    tiempo_desde_solicitud = serializers.SerializerMethodField()
    precio_base = serializers.DecimalField(source='producto.precio_ultima_compra', max_digits=10, decimal_places=2, read_only=True)
    solicitado_por = serializers.CharField(source='created_by.nombre', read_only=True)
    #almacen = serializers.CharField(source='almacen.nombre', read_only=True)
    almacen_origen = serializers.SerializerMethodField()
    class Meta:
        model = ProductosSolicitud
        fields = ('id', 'producto', 'nombre', 'codigo', 'cantidad', 'fase', 'created_at', 'motivo', 'tiempo_desde_solicitud', 'unidad_sat_clave', 'unidad_sat_nombre', 'precio_base', 'solicitado_por', 'almacen', 'almacen_origen')
        read_only_fields = ('id', 'producto_nombre', 'producto_codigo', 'created_at','tiempo_desde_solicitud', 'unidad_sat_clave', 'unidad_sat_nombre', 'precio_base', 'solicitado_por', 'almacen', 'almacen_origen')

    def get_tiempo_desde_solicitud(self, obj):
        """Tiempo transcurrido desde la solicitud"""
        from django.utils import timezone
        if obj.created_at:
            delta = timezone.now() - obj.created_at
            dias = delta.days
            horas = delta.seconds // 3600
            
            if dias > 0:
                return f"{dias} día{'s' if dias != 1 else ''}"
            elif horas > 0:
                return f"{horas} hora{'s' if horas != 1 else ''}"
            else:
                return "Menos de 1 hora"
        return "No disponible"
    def get_almacen_origen(self, obj):
        """Obtener el nombre del almacén origen del producto"""
        if obj.almacen:
            return obj.almacen.nombre
        return ''
    

class ProductosSolicitudSerializer(BaseSerializer):
    """
    Serializer completo para solicitudes de productos
    """
    # Campos relacionados
    producto = SerializerRelatedField(
        queryset=Producto.objects.filter(status_model=Producto.STATUS_MODEL_ACTIVE),
        required=True,
        allow_null=False,
        help_text="Producto para el cual se hace la solicitud"
    )
    
    ## Campos calculados
    #producto_info = serializers.SerializerMethodField()
    #stock_actual = serializers.SerializerMethodField()
    #stock_minimo = serializers.SerializerMethodField()
    #diferencia_stock = serializers.SerializerMethodField()
    tiempo_desde_solicitud = serializers.SerializerMethodField()
    
    # Validaciones para campos específicos
    cantidad = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        min_value=Decimal('0.01'),
        help_text="Cantidad solicitada del producto"
    )
    
    class Meta:
        model = ProductosSolicitud
        fields = [
            'id', 'producto', 'cantidad', 'fase', 'motivo', 'almacen',
             'tiempo_desde_solicitud',
            'created_at', 'updated_at', 'created_by', 'updated_by', 'status_model'
        ]
        read_only_fields = (
            'id', 'tiempo_desde_solicitud',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        )

   
    def get_tiempo_desde_solicitud(self, obj):
        """Tiempo transcurrido desde la solicitud"""
        from django.utils import timezone
        if obj.created_at:
            delta = timezone.now() - obj.created_at
            dias = delta.days
            horas = delta.seconds // 3600
            
            if dias > 0:
                return f"{dias} día{'s' if dias != 1 else ''}"
            elif horas > 0:
                return f"{horas} hora{'s' if horas != 1 else ''}"
            else:
                return "Menos de 1 hora"
        return "No disponible"

    def validate_cantidad(self, value):
        """Validar cantidad solicitada"""
        if value <= 0:
            raise serializers.ValidationError("La cantidad debe ser mayor a cero.")
        
        if value > 999999:
            raise serializers.ValidationError("La cantidad no puede exceder 999,999 unidades.")
        
        return value

    def validate_producto(self, value):
        """Validar producto"""
        if not value:
            raise serializers.ValidationError("El producto es requerido.")
        
        if value.status_model != BaseModel.STATUS_MODEL_ACTIVE:
            raise serializers.ValidationError("El producto seleccionado no está activo.")
        
        return value

    def validate(self, data):
        """Validaciones generales"""
        producto = data.get('producto')
        fase = data.get('fase', ProductosSolicitud.SOLICITUD)
        
        ## Validar que no exista una solicitud activa para el mismo producto
        #if not self.instance:  # Solo en creación
        #    solicitud_existente = ProductosSolicitud.objects.filter(
        #        producto=producto,
        #        fase=ProductosSolicitud.SOLICITUD,
        #        status_model=BaseModel.STATUS_MODEL_ACTIVE
        #    ).exists()
        #    
        #    if solicitud_existente:
        #        raise serializers.ValidationError({
        #            'producto': f'Ya existe una solicitud activa para el producto {producto.nombre}'
        #        })
        
        return data

    def create(self, validated_data):
        """Crear solicitud asignando el usuario creador"""
        request = self.context.get('request')
        #if request and hasattr(request, 'user') and request.user.is_authenticated:
        validated_data['created_by'] = request.user
        
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Actualizar solicitud asignando el usuario actual"""
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            validated_data['updated_by_id'] = request.user.id
        
        return super().update(instance, validated_data)


class ProductosSolicitudEstadoSerializer(serializers.ModelSerializer):
    """
    Serializer específico para cambiar solo el estado de la solicitud
    """
    class Meta:
        model = ProductosSolicitud
        fields = ('fase',)
    
    def validate_fase(self, value):
        """Validar transiciones de estado"""
        if self.instance:
            estado_actual = self.instance.fase
            
            # Validar transiciones permitidas
            transiciones_validas = {
                ProductosSolicitud.SOLICITUD: [ProductosSolicitud.ATENDIDO, ProductosSolicitud.CANCELADO],
                ProductosSolicitud.ATENDIDO: [ProductosSolicitud.CANCELADO],  # Solo puede cancelarse
                ProductosSolicitud.CANCELADO: []  # No puede cambiar desde cancelado
            }
            
            if value not in transiciones_validas.get(estado_actual, []):
                raise serializers.ValidationError(
                    f"No se puede cambiar de '{estado_actual}' a '{value}'. "
                    f"Transiciones válidas desde '{estado_actual}': {transiciones_validas.get(estado_actual, [])}"
                )
        
        return value