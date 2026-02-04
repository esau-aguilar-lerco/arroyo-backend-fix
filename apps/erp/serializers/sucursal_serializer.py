from apps.base.serializer import BaseSerializer, FlexiblePKRelatedField, serializers, SerializerRelatedField
from drf_spectacular.utils import extend_schema_field
from apps.erp.serializers.proveedor_serializer import ProveedorMiniSerializer
from apps.usuarios.serializers.usuarios import UsuarioMiniSerializer
from .almacen_serializer import AlmacenMiniSerializer, DireccionAlmacenObjSerializer
from apps.direccion.serializers.direccion_serializer import (
    EstadoSerializer,
    MunicipioSerializer,
    CodigoPostalSerializer,
    ColoniaSerializer
)

from apps.direccion.models import Estado, Municipio, CodigoPostal, Colonia

from apps.erp.serializers.empresa_serializer import EmpresaMiniSerializer
from ..models import Sucursal, DireccionSucursal





class DireccionSucursalSerializer(serializers.ModelSerializer):
    # Mostrar solo IDs en escritura
    #usuario = serializers.PrimaryKeyRelatedField(queryset=Usuario.objects.all())
    estado = serializers.PrimaryKeyRelatedField(queryset=Estado.objects.all(), allow_null=True, help_text="ID del estado")
    municipio = serializers.PrimaryKeyRelatedField(queryset=Municipio.objects.all(), allow_null=True, help_text="ID del municipio")
    codigo_postal = serializers.PrimaryKeyRelatedField(queryset=CodigoPostal.objects.all(), allow_null=True, help_text="ID del código postal")
    colonia = serializers.PrimaryKeyRelatedField(queryset=Colonia.objects.all(), allow_null=True, help_text="ID de la colonia")

    # Campos anidados solo lectura (útil en GET)
    estado_name =  serializers.StringRelatedField(source='estado', read_only=True, help_text="Nombre del estado")
    municipio_name = serializers.StringRelatedField(source='municipio', read_only=True, help_text="Nombre del municipio")
    codigo_postal_name = serializers.StringRelatedField(source='codigo_postal', read_only=True, help_text="Código postal")
    colonia_name = serializers.StringRelatedField(source='colonia', read_only=True, help_text="Nombre de la colonia")


    class Meta:
        model = DireccionSucursal
        fields = [
            'id',
            'estado', 'estado_name',
            'municipio', 'municipio_name',
            'codigo_postal', 'codigo_postal_name',
            'colonia', 'colonia_name',
            'calle', 'numero_exterior', 'numero_interior',
            
        ]
        extra_kwargs = {
            'calle': {'help_text': 'Nombre de la calle'},
            'numero_exterior': {'help_text': 'Número exterior del almacén'},
            'numero_interior': {'help_text': 'Número interior del almacén (opcional)'},
        }

class DireccionSucursalObjSerializer(serializers.ModelSerializer):
    estado = EstadoSerializer(read_only=True)
    municipio = MunicipioSerializer(read_only=True)
    codigo_postal = CodigoPostalSerializer(read_only=True)
    colonia = ColoniaSerializer(read_only=True)
    class Meta:
        model = DireccionSucursal
        fields = [
            'id',
            'calle', 'numero_exterior', 'numero_interior',
            'estado', 'municipio', 'codigo_postal', 'colonia',
            

        ]
        read_only_fields = ('id','calle', 'numero_exterior', 'numero_interior',)




# Multi almacen
class SucursalSerializer(BaseSerializer):
    class Meta:
        model = Sucursal
        fields = '__all__'
        read_only_fields = ('codigo',)


    codigo = serializers.CharField(
        max_length=10,
        min_length=5,
        allow_blank=False,
        help_text="Código del sucursal",
        read_only=True
    )
    #codigo = serializers.SerializerMethodField()
    empresa = SerializerRelatedField(
        queryset=EmpresaMiniSerializer.Meta.model.objects.filter(status_model=EmpresaMiniSerializer.Meta.model.STATUS_MODEL_ACTIVE),
        required=True,
        help_text="ID de la empresa o dic {id: <id>} a la que pertenece la sucursal"
    )
    empresa_obj = EmpresaMiniSerializer(read_only=True, source='empresa',help_text="Detalle de la empresa")

    almacenes = FlexiblePKRelatedField(
        queryset=AlmacenMiniSerializer.Meta.model.objects.exclude(status_model=AlmacenMiniSerializer.Meta.model.STATUS_MODEL_DELETE),
        many=True,
        required=True,
        allow_empty=False,
        help_text="IDs de los almacenes (solo activos, puede ser un array de enteros o un array de [ {\"id\": <pk> } ])"
    )
    almacenes_obj = AlmacenMiniSerializer(many=True, read_only=True, source='almacenes')


    encargado = SerializerRelatedField(
        queryset=UsuarioMiniSerializer.Meta.model.objects.all(),
        allow_null=False,
        required=True,
        help_text="ID del encargado de la sucursal o dic {id: <id>}"
    )
    encargado_obj = UsuarioMiniSerializer(read_only=True, source='encargado',help_text="Detalle del encargado")

    direccion = DireccionSucursalSerializer(many=True, required=False, allow_null=True, help_text="Dirección de la sucursal", source='direccion_sucursal')
    direccion_obj = serializers.SerializerMethodField(
        read_only=True,
        help_text="Detalle de la dirección del almacén asociado a la sucursal"
    )

    @extend_schema_field(DireccionAlmacenObjSerializer)
    def get_direccion_obj(self, obj):
        if hasattr(obj, 'direccion_principal') and obj.direccion_principal:
            return DireccionAlmacenObjSerializer(obj.direccion_principal).data
        

    def create(self, validated_data):
        """
        Crear sucursal con sus direcciones
        """
        # Extraer las direcciones de los datos validados
        direcciones_data = validated_data.pop('direccion_sucursal', [])

        # ✅ Extraer almacenes antes de crear la instancia
        almacenes_data = validated_data.pop('almacenes', [])

        # ✅ Obtener el usuario del contexto y agregarlo a validated_data
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            validated_data['created_by_id'] = request.user.id  # ✅ Usar objeto, no ID

        # ✅ Usar save() en lugar de create() para que se genere el código
        sucursal = Sucursal(**validated_data)
        sucursal.save()

        # ✅ Asignar almacenes después de crear la instancia
        if almacenes_data:
            sucursal.almacenes.set(almacenes_data)

        # Crear las direcciones y asociarlas a la sucursal
        for direccion_data in direcciones_data:
            # ✅ Asignar usuario también a direcciones
            #if request and hasattr(request, 'user') and request.user.is_authenticated:
            #    direccion_data['created_by'] = request.user
            #    direccion_data['updated_by'] = request.user
            DireccionSucursal.objects.create(sucursal=sucursal, **direccion_data)

        return sucursal

    def update(self, instance, validated_data):
        """
        Actualizar sucursal y sus direcciones
        """
        # Extraer las direcciones de los datos validados
        direcciones_data = validated_data.pop('direccion_sucursal', None)

        # ✅ Extraer el campo ManyToMany antes de usar setattr
        almacenes_data = validated_data.pop('almacenes', None)

        # ✅ Obtener el usuario del contexto y agregarlo a validated_data
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            validated_data['updated_by_id'] = request.user.id  # ✅ Usar objeto, no ID

        # Actualizar los campos regulares (no ManyToMany)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # ✅ Manejar la relación ManyToMany por separado
        if almacenes_data is not None:
            instance.almacenes.set(almacenes_data)  # Usar .set() para ManyToMany

        # Si se proporcionaron direcciones, reemplazar las existentes
        if direcciones_data is not None:
            # Eliminar direcciones existentes
            instance.direccion_sucursal.all().delete()

            # Crear nuevas direcciones
            for direccion_data in direcciones_data:
                # ✅ Asignar usuario también a direcciones si el modelo lo soporta
                
                DireccionSucursal.objects.create(sucursal=instance, **direccion_data)

        return instance



class SucursalMiniSerializer(BaseSerializer):
    mi_empresa = serializers.ReadOnlyField()
    nombre_completo = serializers.ReadOnlyField()
    
    class Meta:
        model = Sucursal
        fields = ('id', 'nombre', 'mi_empresa', 'nombre_completo')
        read_only_fields = ('id', 'nombre', 'mi_empresa', 'nombre_completo')

