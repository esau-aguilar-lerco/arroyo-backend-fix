from rest_framework import serializers
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from ..models import Usuario


class PermissionSerializer(serializers.ModelSerializer):
    """
    Serializer para permisos (solo lectura)
    """
    content_type_name = serializers.CharField(source='content_type.name', read_only=True)
    app_label = serializers.CharField(source='content_type.app_label', read_only=True)
    model_name = serializers.CharField(source='content_type.model', read_only=True)
    
    class Meta:
        model = Permission
        fields = ['id', 'name', 'codename', 'content_type', 'content_type_name', 'app_label', 'model_name']
        read_only_fields = ['id', 'name', 'codename', 'content_type']


class GroupSerializer(serializers.ModelSerializer):
    """
    Serializer para grupos con gestión de permisos
    """
    permissions = PermissionSerializer(many=True, read_only=True)
    permission_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="Lista de IDs de permisos a asignar al grupo"
    )

    #permission_ids = FlexiblePKRelatedField(
    #    queryset=Permission.objects.all(),
    #    many=True,
    #    required=True,
    #    allow_empty=False,
    #    help_text="IDs de los permisos (solo activos, puede ser un array de enteros o un array de [ {\"id\": <pk> } ])"
    #)
    users_count = serializers.SerializerMethodField()
    permissions_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Group
        fields = ['id', 'name', 'permissions', 'permission_ids', 'users_count', 'permissions_count']
        read_only_fields = ['id', 'users_count', 'permissions_count']
    
    def get_users_count(self, obj):
        """Contar usuarios en el grupo"""
        return obj.user_set.count()
    
    def get_permissions_count(self, obj):
        """Contar permisos del grupo"""
        return obj.permissions.count()
    
    def validate_name(self, value):
        """Validar nombre del grupo"""
        if not value or not value.strip():
            raise serializers.ValidationError("El nombre del grupo es requerido.")
        
        # Verificar que no exista otro grupo con el mismo nombre
        if self.instance:
            # En actualización, excluir el grupo actual
            if Group.objects.filter(name=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError("Ya existe un grupo con este nombre.")
        else:
            # En creación
            if Group.objects.filter(name=value).exists():
                raise serializers.ValidationError("Ya existe un grupo con este nombre.")
        
        return value.strip()
    
    def validate_permission_ids(self, value):
        """Validar IDs de permisos"""
        if value:
            # Verificar que todos los permisos existen
            existing_permissions = Permission.objects.filter(id__in=value)
            if existing_permissions.count() != len(value):
                raise serializers.ValidationError("Algunos permisos especificados no existen.")
        
        return value
    
    def create(self, validated_data):
        """Crear grupo con permisos"""
        permission_ids = validated_data.pop('permission_ids', [])
        group = Group.objects.create(**validated_data)
        
        if permission_ids:
            permissions = Permission.objects.filter(id__in=permission_ids)
            group.permissions.set(permissions)
        
        return group
    
    def update(self, instance, validated_data):
        """Actualizar grupo con permisos"""
        permission_ids = validated_data.pop('permission_ids', None)
        
        # Actualizar campos básicos
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Actualizar permisos si se proporcionan
        if permission_ids is not None:
            permissions = Permission.objects.filter(id__in=permission_ids)
            instance.permissions.set(permissions)
        
        return instance


class GroupMiniSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado para grupos (para listas)
    """
    users_count = serializers.SerializerMethodField()
    permissions_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Group
        fields = ['id', 'name', 'users_count', 'permissions_count']
    
    def get_users_count(self, obj):
        return obj.user_set.count()
    
    def get_permissions_count(self, obj):
        return obj.permissions.count()


class ContentTypeSerializer(serializers.ModelSerializer):
    """
    Serializer para tipos de contenido
    """
    permissions = PermissionSerializer(many=True, read_only=True)
    permissions_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ContentType
        fields = ['id', 'app_label', 'model', 'name', 'permissions', 'permissions_count']
    
    def get_permissions_count(self, obj):
        return obj.permission_set.count()