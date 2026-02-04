from rest_framework import serializers

#from drf_yasg.utils import swagger_serializer_method
#from drf_yasg import openapi
from drf_spectacular.utils import extend_schema_field


from django.contrib.auth.models import Group, Permission
from apps.erp.models import Almacen
#models
from apps.usuarios.models import Usuario, DireccionUsuario
from apps.direccion.models import Estado, Municipio, CodigoPostal, Colonia

#serializer 
from apps.direccion.serializers.direccion_serializer import (
    EstadoSerializer,
    MunicipioSerializer,
    CodigoPostalSerializer,
    ColoniaSerializer
)

from apps.base.serializer import FlexiblePKRelatedField
class UsuarioMiniSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField(read_only=True)

    def get_full_name(self, obj):
        return obj.full_name() if obj else ""

    class Meta:
        model = Usuario
        fields = ('id', 'username', 'full_name',)


class UsuarioDetalleSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField(read_only=True)
    #id = serializers.IntegerField(read_only=True)

    def get_full_name(self, obj):
        return obj.full_name() if obj else ""

    class Meta:
        model = Usuario
        fields = ('id', 'username', 'full_name',)
        read_only_fields = ('username', 'full_name',)
# Serializador principal
class DireccionUsuarioSerializer_(serializers.ModelSerializer):
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
        model = DireccionUsuario
        fields = [
            'id',
            #'usuario',
            'estado', 'estado_name',
            'municipio', 'municipio_name',
            'codigo_postal', 'codigo_postal_name',
            'colonia', 'colonia_name',
            'calle', 'numero_exterior', 'numero_interior',
        ]
        extra_kwargs = {
            'calle': {'help_text': 'Nombre de la calle'},
            'numero_exterior': {'help_text': 'Número exterior del domicilio'},
            'numero_interior': {'help_text': 'Número interior del domicilio (opcional)'},
        }

class DireccionUsuarioObjSerializer(serializers.ModelSerializer):
    estado = EstadoSerializer(read_only=True)
    municipio = MunicipioSerializer(read_only=True)
    codigo_postal = CodigoPostalSerializer(read_only=True)
    colonia = ColoniaSerializer(read_only=True)
    class Meta:
        model = DireccionUsuario
        fields = [
            'id',
            'calle', 'numero_exterior', 'numero_interior',
            'estado', 'municipio', 'codigo_postal', 'colonia'
        ]
        read_only_fields = ('id','calle', 'numero_exterior', 'numero_interior',)


class DireccionUsuarioSerializer(serializers.ModelSerializer):
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
        model = DireccionUsuario
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




class UsuarioListSerializer(serializers.ModelSerializer):
    
    
    created_at = serializers.SerializerMethodField(read_only=True)
    updated_at = serializers.SerializerMethodField(read_only=True)
    date_joined = serializers.SerializerMethodField(read_only=True)
    created_by = serializers.SerializerMethodField(read_only=True)
    updated_by = serializers.SerializerMethodField(read_only=True)
    full_name = serializers.SerializerMethodField(read_only=True)
    grupos = serializers.SerializerMethodField(read_only=True, help_text="Lista de grupos a los que pertenece el usuario")
    almacen_obj = serializers.SerializerMethodField(
        help_text="Objeto del almacén asignado al usuario",
        read_only=True
    )
    #updated_at = serializers.SerializerMethodField(read_only=True)
    class Meta:
        model = Usuario
        fields = ('id', 'username', 'email', 'last_login', 
                  'is_superuser', 'is_active', 
                  'nombre', 'apellido_paterno', 'apellido_materno',
                  'telefono_1','date_joined','created_at', 'created_by',
                  'updated_by', 'full_name','updated_at', 'grupos', 'almacen_obj',)
        
    
    
        
    def get_grupos(self, obj):
        return [{"id": g.id, "name": g.name} for g in obj.groups.all()]
        
    # Métodos de campos legibles
    def get_full_name(self, obj):
        return obj.full_name() if obj else ""

    def get_created_by(self, obj):
        return obj.created_by.full_name() if obj.created_by else ''

    def get_updated_by(self, obj):
        return obj.updated_by.full_name() if obj.updated_by else ''

    def get_created_at(self, obj):
        return obj.created_at.strftime('%Y-%m-%d %H:%M:%S') if obj.created_at else "N/A"

    def get_updated_at(self, obj):
        return obj.updated_at.strftime('%Y-%m-%d %H:%M:%S') if obj.updated_at else "N/A"

    def get_date_joined(self, obj):
        return obj.date_joined.strftime('%Y-%m-%d %H:%M:%S') if obj.date_joined else "N/A"
     #@extend_schema_field(AlmacenMiniSerializer)
    def get_almacen_obj(self, obj):
        
        return {
            'id': obj.almacen.id if obj.almacen else None,
            'codigo': obj.almacen.codigo  if obj.almacen and obj.almacen.codigo else "",
            'nombre': obj.almacen.nombre if obj.almacen and obj.almacen.nombre else "",
            'encargado_name': obj.almacen.encargado.full_name() if obj.almacen and obj.almacen.encargado else "",
        }
      

class UsuarioSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_null=True)

    created_at = serializers.SerializerMethodField(read_only=True)
    updated_at = serializers.SerializerMethodField(read_only=True)
    date_joined = serializers.SerializerMethodField(read_only=True)
    created_by = serializers.SerializerMethodField(read_only=True)
    updated_by = serializers.SerializerMethodField(read_only=True)
    full_name = serializers.SerializerMethodField(read_only=True)

    # Campos de solo lectura para respuesta (detalles)
    grupos = serializers.SerializerMethodField(read_only=True, help_text="Lista de grupos a los que pertenece el usuario")
    permisos = serializers.SerializerMethodField(read_only=True, help_text="Lista de permisos asignados al usuario")

    is_superuser = serializers.BooleanField(read_only=True)

    # Campos editables en el formulario (envían solo ID)
    groups = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(), many=True, write_only=True, required=False
    )
    user_permissions = serializers.PrimaryKeyRelatedField(
        queryset=Permission.objects.all(), many=True, write_only=True, required=False
    )
    permisos_group = serializers.SerializerMethodField(read_only=True, help_text="Permisos del usuario agrupados por modelo")  # ← Nuevo campo

    last_login = serializers.DateTimeField(read_only=True)

    direccion = DireccionUsuarioSerializer(many=True, required=False, allow_null=True, help_text="Dirección del usuario", source='direccion_usuario')

    

    direccion_obj = serializers.SerializerMethodField(
        help_text="Objeto de dirección del usuario",
        read_only=True
    )
    
    
    almacen = FlexiblePKRelatedField(
        queryset=Almacen.objects.all(),
        required=False,
        allow_null=True,
        help_text="ID del almacén asignado al usuario"
    )
    almacen_obj = serializers.SerializerMethodField(
        help_text="Objeto del almacén asignado al usuario",
        read_only=True
    )
  

    

    class Meta:
        model = Usuario

        fields = (
            'id', 'username', 'email', 'password', 'last_login','is_superuser','is_active',
            'nombre', 'apellido_paterno', 'apellido_materno',
            'telefono_1', 'date_joined',
            'direccion','direccion_obj',
            'created_at', 'updated_at', 'created_by', 'updated_by',
            'full_name', 'grupos', 'permisos','permisos_group',
            'groups', 'user_permissions','almacen', 'almacen_obj',
        )
        read_only_fields = (
            'created_at', 'updated_at', 'created_by', 'updated_by'
        )
        extra_kwargs = {'password': {'write_only': True}}
    

    # Métodos de campos legibles
    def get_full_name(self, obj):
        return obj.full_name() if obj else ""

    def get_created_by(self, obj):
        return obj.created_by.full_name() if obj.created_by else ''

    def get_updated_by(self, obj):
        return obj.updated_by.full_name() if obj.updated_by else ''

    def get_created_at(self, obj):
        return obj.created_at.strftime('%Y-%m-%d %H:%M:%S') if obj.created_at else "N/A"

    def get_updated_at(self, obj):
        return obj.updated_at.strftime('%Y-%m-%d %H:%M:%S') if obj.updated_at else "N/A"

    def get_date_joined(self, obj):
        return obj.date_joined.strftime('%Y-%m-%d %H:%M:%S') if obj.date_joined else "N/A"

    def get_grupos(self, obj):
        return [{"id": g.id, "name": g.name} for g in obj.groups.all()]

    def get_permisos(self, obj):
        """
        Obtiene los permisos del usuario
        Para superusuarios, excluye permisos de modelos internos
        """
        if obj.is_superuser:
            return [
                {"id": p.id, "codename": p.codename} 
                for p in Permission.objects.select_related('content_type')
                    .exclude(content_type__model='logentry')
            ]
        return [{"id": p.id, "codename": p.codename} for p in obj.user_permissions.all()]

    @extend_schema_field(DireccionUsuarioObjSerializer)
    def get_direccion_obj(self, obj):
        if hasattr(obj, 'direccion_principal') and obj.direccion_principal:
            return DireccionUsuarioObjSerializer(obj.direccion_principal).data
        return None
    
    #@extend_schema_field(AlmacenMiniSerializer)
    def get_almacen_obj(self, obj):
        
        return {
            'id': obj.almacen.id if obj.almacen else None,
            'codigo': obj.almacen.codigo  if obj.almacen and obj.almacen.codigo else "",
            'nombre': obj.almacen.nombre if obj.almacen and obj.almacen.nombre else "",
            'encargado_name': obj.almacen.encargado.full_name() if obj.almacen and obj.almacen.encargado else "",
        }
       

    # Crear usuario
    def create(self, validated_data):
        request = self.context.get('request', None)
        password = validated_data.pop('password', None)
        groups = validated_data.pop('groups', [])
        permissions = validated_data.pop('user_permissions', [])
    
        # Extraer la dirección de validated_data en lugar de initial_data
        direcciones_data = validated_data.pop('direccion_usuario', [])
    
        user = Usuario(**validated_data)
    
        if request and request.user.is_authenticated:
            user.created_by_id = request.user.id
    
        if password:
            user.set_password(password)
    
        user.save()
        user.groups.set(groups)
        user.user_permissions.set(permissions)
    
        for direccion_data in direcciones_data:
            DireccionUsuario.objects.create(usuario=user, **direccion_data)
            
    
        return user
    
    # Actualizar usuario
    def update(self, instance, validated_data):
        request = self.context.get('request', None)
        password = validated_data.pop('password', None)
        groups = validated_data.pop('groups', None)
        permissions = validated_data.pop('user_permissions', None)

        # Remove direccion_usuario from validated_data to handle separately
        direcciones_data = validated_data.pop('direccion_usuario', None)

        user = super().update(instance, validated_data)

        if request and request.user.is_authenticated:
            user.updated_by = request.user
            user.save(update_fields=['updated_by'])

        if password:
            user.set_password(password)
            user.save(update_fields=['password'])

        if groups is not None:
            user.groups.set(groups)

        if permissions is not None:
            user.user_permissions.set(permissions)

        # Handle direccion_usuario updates
        if direcciones_data is not None:
            user.direccion_usuario.all().delete()
            for direccion_data in direcciones_data:
                DireccionUsuario.objects.create(usuario=user, **direccion_data)

        return user

    def get_permisos_group(self, obj):
        """
        Obtiene los permisos del usuario agrupados por modelo
        Excluye modelos internos como logentry
        """
        # Si el usuario es superusuario, obtener todos los permisos del sistema
        if obj.is_superuser:
            queryset = Permission.objects.select_related('content_type').exclude(
                content_type__model='logentry'
            )
        else:
            # Obtener IDs de permisos directos
            permisos_directos_ids = obj.user_permissions.values_list('id', flat=True)
            
            # Obtener IDs de permisos de grupos
            permisos_grupos_ids = Permission.objects.filter(
                group__user=obj
            ).values_list('id', flat=True)
            
            # Combinar los IDs (usando set para evitar duplicados)
            todos_permisos_ids = set(list(permisos_directos_ids) + list(permisos_grupos_ids))
            
            # Obtener los permisos finales, excluyendo logentry
            queryset = Permission.objects.filter(
                id__in=todos_permisos_ids
            ).select_related('content_type').exclude(
                content_type__model='logentry'
            )
        
        # Agrupar permisos por modelo
        grouped = {}
        
        for perm in queryset:
            model = perm.content_type.model
            if model not in grouped:
                grouped[model] = []
            grouped[model].append({
                'id': perm.id,
                'codename': perm.codename,
                'name': perm.name,
                'app_label': perm.content_type.app_label
            })
        
        # Ordenar los permisos dentro de cada modelo por codename
        for model in grouped:
            grouped[model].sort(key=lambda x: x['codename'])
        
        return grouped
class MiDataResponseSerializer(serializers.Serializer):
    """
    Serializer para la respuesta de los datos del usuario autenticado
    """
    username = serializers.CharField(
        help_text="Nombre de usuario"
    )
    email = serializers.EmailField(
        help_text="Correo electrónico del usuario"
    )
    full_name = serializers.CharField(
        help_text="Nombre completo del usuario"
    )
    permisos = serializers.ListField(
        child=serializers.CharField(),
        help_text="Lista de permisos del usuario"
    )
    is_superuser = serializers.BooleanField(
        help_text="Indica si el usuario es superusuario"
    )
    is_staff = serializers.BooleanField(
        help_text="Indica si el usuario es staff"
    )
    is_active = serializers.BooleanField(
        help_text="Indica si el usuario está activo"
    )
    
    caja_abierta = serializers.BooleanField(
        help_text="Indica si el usuario tiene una caja abierta"
    )
    mi_almacen_nombre = serializers.CharField(
        help_text="Nombre del almacén asignado al usuario",
        allow_null=True
    )
    mi_almacen_id = serializers.IntegerField(
        help_text="ID del almacén asignado al usuario",
        allow_null=True
    )