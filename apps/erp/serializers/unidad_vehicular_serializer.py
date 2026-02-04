from rest_framework import serializers
from decimal import Decimal

# MODELS
from apps.base.models import BaseModel
from ..models import UnidadVehicular

# SERIALIZERS
from apps.base.serializer import BaseSerializer


class UnidadVehicularMiniSerializer(BaseSerializer):
    """
    Serializer mini para listar unidades vehiculares básicas
    """
    clave = serializers.SerializerMethodField()
    
    class Meta:
        model = UnidadVehicular
        fields = ('id', 'nombre', 'placas', 'tipo', 'marca', 'modelo', 'clave')
        read_only_fields = ('id', 'nombre', 'placas', 'tipo', 'marca', 'modelo', 'clave')
    
    def get_clave(self, obj):
        """Obtener la clave del sistema"""
        return obj.get_clave()


class UnidadVehicularSerializer(BaseSerializer):
    """
    Serializer completo para unidades vehiculares
    """
    # Campos calculados
    clave = serializers.SerializerMethodField()
   
    
    # Validaciones para campos específicos
    capacidad_carga = serializers.DecimalField(
        allow_null=True,
        required=False,
        max_digits=10, 
        decimal_places=2, 
        min_value=Decimal('0.01'),
        help_text="Capacidad de carga en toneladas"
    )
    
    anio = serializers.IntegerField(required=False, allow_null=True, help_text="Año del vehículo")
    
    class Meta:
        model = UnidadVehicular
        fields = [
            'id', 'nombre', 'tipo', 'placas', 'marca', 'modelo', 'anio',
            'capacidad_carga', 'fecha_adquisicion', 'status_model',
            'clave', 
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = (
            'id', 'clave',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        )

    def get_clave(self, obj):
        """Obtener la clave del sistema"""
        return obj.get_clave()

    def validate(self, data):
        """
        Validaciones generales
        """
        # Validar que fecha_adquisicion no sea futura
        fecha_adquisicion = data.get('fecha_adquisicion')
        if fecha_adquisicion:
            from datetime import date
            if fecha_adquisicion > date.today():
                raise serializers.ValidationError({
                    'fecha_adquisicion': 'La fecha de adquisición no puede ser futura.'
                })
        
        return data

        """
        Actualizar unidad vehicular asignando el usuario actual
        """
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            validated_data['updated_by_id'] = request.user.id
        
        # Normalizar campos de texto
        if 'nombre' in validated_data:
            validated_data['nombre'] = validated_data['nombre'].strip().upper()
        if 'marca' in validated_data:
            validated_data['marca'] = validated_data['marca'].strip().upper()
        if 'modelo' in validated_data:
            validated_data['modelo'] = validated_data['modelo'].strip().upper()
        if 'placas' in validated_data:
            validated_data['placas'] = validated_data['placas'].strip().upper()
        
        return super().update(instance, validated_data)