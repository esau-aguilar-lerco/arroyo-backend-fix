from rest_framework import serializers
from apps.erp.models import Rutas, Almacen, UnidadVehicular
from apps.usuarios.models import Usuario
from apps.usuarios.serializers.usuarios import UsuarioMiniSerializer
from apps.base.serializer import BaseSerializer, SerializerRelatedField
from apps.base.models import BaseModel
from .almacen_serializer import AlmacenMiniSerializer
from .unidad_vehicular_serializer import UnidadVehicularMiniSerializer


"""
==============================================
    SERIALIZER MINI PARA RUTAS
==============================================
"""
class RutasMiniSerializer(BaseSerializer):
    """
    Serializer mini para listar rutas básicas
    """
    asignado_nombre = serializers.CharField(source='asignado.full_name', read_only=True)
    almacen_nombre = serializers.CharField(source='almacen.nombre', read_only=True)
    unidad_nombre = serializers.CharField(source='unidad.nombre', read_only=True)
    
    class Meta:
        model = Rutas
        fields = (
            'id', 'codigo', 'nombre', 'origen', 'destino', 'unidad_nombre',
            'asignado_nombre', 'almacen_nombre', 'created_at'
        )
        read_only_fields = (
            'id', 'codigo', 'asignado_nombre', 'almacen_nombre', 'created_at'
        )


"""
==============================================
    SERIALIZER PRINCIPAL PARA RUTAS
==============================================
"""
class RutasSerializer(BaseSerializer):
    """
    Serializer completo para rutas con sus relaciones
    """
    asignado = SerializerRelatedField(
        queryset=Usuario.objects.filter(is_active=True),
        required=False,
        allow_null=True,
        help_text="ID del chofer asignado (solo activos, puede ser un entero o {\"id\": <pk>})"
    )
    asignado_obj = UsuarioMiniSerializer(read_only=True, source='asignado')
    
    # El almacén se crea automáticamente por el signal, solo lectura
    almacen_obj = AlmacenMiniSerializer(read_only=True, source='almacen')

    unidad = SerializerRelatedField(
        queryset=UnidadVehicular.objects.filter(status_model=BaseModel.STATUS_MODEL_ACTIVE),
        required=True,
        allow_null=False,
        help_text="ID de la unidad vehicular asignada (solo activas, puede ser un entero o {\"id\": <pk>})"
    )
    unidad_obj = UnidadVehicularMiniSerializer(read_only=True, source='unidad')

    class Meta:
        model = Rutas
        fields = [
            'id', 'codigo', 'nombre', 'descripcion', 'origen', 'destino', 'unidad', 'unidad_obj',
            'asignado', 'asignado_obj', 'almacen_obj',
            'created_at', 'updated_at', 'created_by', 'updated_by', 'status_model'
        ]
        read_only_fields = (
            'id', 'codigo', 'almacen_obj',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        )

    def validate(self, data):
        """
        Validaciones generales
        """
        # Validar que el usuario asignado esté activo
        asignado = data.get('asignado')
        if asignado and not asignado.is_active:
            raise serializers.ValidationError("El usuario asignado no está activo.")
        
        return data

    def create(self, validated_data):
        """
        Crear ruta (el almacén se crea automáticamente por signal)
        """
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            validated_data['created_by_id'] = request.user.id

        # Crear la ruta (el signal creará el almacén automáticamente)
        ruta = Rutas.objects.create(**validated_data)
        
        return ruta

    def update(self, instance, validated_data):
        """
        Actualizar ruta (el almacén permanece intacto)
        """
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            validated_data['updated_by_id'] = request.user.id
        
        # Actualizar campos básicos (el almacén no se toca)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance


"""
==============================================
    SERIALIZER PARA ACTUALIZAR ESTADO
==============================================
"""
class RutasEstadoSerializer(BaseSerializer):
    """
    Serializer específico para actualizar solo el estado de una ruta
    """
    class Meta:
        model = Rutas
        fields = ('status_model',)

    def validate_status_model(self, value):
        """
        Validar transiciones de estado válidas
        """
        if self.instance:
            estado_actual = self.instance.status_model
            
            # No permitir reactivar rutas eliminadas
            if estado_actual == BaseModel.STATUS_MODEL_DELETE:
                raise serializers.ValidationError(
                    "No se puede reactivar una ruta eliminada."
                )
        
        return value



