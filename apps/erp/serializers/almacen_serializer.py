from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field


#MODELS
from ..models import Almacen, DireccionAlmacen, Empresa
from apps.direccion.models import Estado, Municipio, CodigoPostal, Colonia
#SERIALIZERS
from apps.base.serializer import BaseSerializer, SerializerRelatedField
from apps.usuarios.serializers.usuarios import UsuarioMiniSerializer
from apps.direccion.serializers.direccion_serializer import (
    EstadoSerializer,
    MunicipioSerializer,
    CodigoPostalSerializer,
    ColoniaSerializer
)
from apps.erp.serializers.empresa_serializer import EmpresaMiniSerializer
#from apps.inventario.serializers.mainInventarioSerializers import PisoSerializer


class DireccionAlmacenSerializer(serializers.ModelSerializer):
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
        model = DireccionAlmacen
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

class DireccionAlmacenObjSerializer(serializers.ModelSerializer):
    estado = EstadoSerializer(read_only=True)
    municipio = MunicipioSerializer(read_only=True)
    codigo_postal = CodigoPostalSerializer(read_only=True)
    colonia = ColoniaSerializer(read_only=True)
    class Meta:
        model = DireccionAlmacen
        fields = [
            'id',
            'calle', 'numero_exterior', 'numero_interior',
            'estado', 'municipio', 'codigo_postal', 'colonia',
            

        ]
        read_only_fields = ('id','calle', 'numero_exterior', 'numero_interior',)




class AlmacenSerializer(BaseSerializer):
    codigo = serializers.CharField(
        max_length=10,
        min_length=5,
        allow_blank=True,
        help_text="Código del almacén",
        read_only=True
    )
    encargado_obj = UsuarioMiniSerializer(read_only=True, source='encargado')
    encargado = SerializerRelatedField(
        queryset=UsuarioMiniSerializer.Meta.model.objects.all(),
        allow_null=True,
        help_text="ID del encargado del almacén o diccionario {'id': <pk>}",
        required=True
    )

    empresa = SerializerRelatedField(
        queryset=Empresa.objects.filter(status_model=Empresa.STATUS_MODEL_ACTIVE),
        allow_null=True,
        help_text="ID de la empresa o diccionario {'id': <pk>}",
        required=True
    )
    empresa_obj = serializers.SerializerMethodField()

    direccion = DireccionAlmacenSerializer(many=True, required=False, allow_null=True, help_text="Dirección del almacén", source='direccion_almacen')
    
    direccion_obj = serializers.SerializerMethodField(
        help_text="Objeto de dirección del almacén",
        read_only=True
    )
   
    tipo = serializers.CharField(source='get_tipo_display', read_only=True)
    #pisos = PisoSerializer(many=True, read_only=True, source='pisos_almacen', help_text="Pisos del almacén")
    class Meta:
        model = Almacen
        fields = '__all__'
        read_only_fields = ('tipo', )


    def create(self, validated_data):
        """
        Crear almacén con sus direcciones
        """
        # Extraer las direcciones de los datos validados
        direcciones_data = validated_data.pop('direccion_almacen', [])

        # ✅ Obtener el usuario del contexto y agregarlo a validated_data
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            validated_data['created_by_id'] = request.user.id
            #validated_data['updated_by_id'] = request.user.id
        
        # Crear el almacén sin las direcciones
        almacen = Almacen.objects.create(**validated_data)
        
        # Crear las direcciones y asociarlas al almacén
        for direccion_data in direcciones_data:
            DireccionAlmacen.objects.create(almacen=almacen, **direccion_data)
        
        return almacen

    def update(self, instance, validated_data):
        """
        Actualizar almacén y sus direcciones
        """
        # Extraer las direcciones de los datos validados
        direcciones_data = validated_data.pop('direccion_almacen', None)

        # ✅ Obtener el usuario del contexto y agregarlo a validated_data
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            validated_data['updated_by_id'] = request.user.id


        
        # Actualizar los campos del almacén
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Si se proporcionaron direcciones, reemplazar las existentes
        if direcciones_data is not None:
            # Eliminar direcciones existentes
            instance.direccion_almacen.all().delete()  # Ajusta 'direcciones' según tu related_name
            
            # Crear nuevas direcciones
            for direccion_data in direcciones_data:
                DireccionAlmacen.objects.create(almacen=instance, **direccion_data)
        
        return instance
    


    
    @extend_schema_field(EmpresaMiniSerializer)
    def get_empresa_obj(self, obj):
        if obj.empresa:
            return EmpresaMiniSerializer(obj.empresa).data
        return None

    @extend_schema_field(DireccionAlmacenObjSerializer)
    def get_direccion_obj(self, obj):
        if hasattr(obj, 'direccion_principal') and obj.direccion_principal:
            return DireccionAlmacenObjSerializer(obj.direccion_principal).data
        return None



class AlmacenMiniSerializer(BaseSerializer):
    class Meta:
        model = Almacen
        fields = ('id', 'codigo', 'nombre', 'encargado_name')
        read_only_fields = ('created_at', 'updated_at', 'created_by', 'updated_by', 'status_model')


    codigo = serializers.SerializerMethodField()
    encargado_name = serializers.CharField(source='encargado.full_name', read_only=True)


    def get_codigo(self, obj):
        return obj.codigo.upper().strip() if obj.codigo else ""
    


class AlmacenDetalleViewSerializer(BaseSerializer):

    class Meta:
        model = Almacen
        fields = ('id', 'codigo', 'nombre')
        read_only_fields = ('nombre','codigo')