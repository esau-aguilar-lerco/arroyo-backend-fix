from django.utils import timezone

from rest_framework import serializers

from rest_framework_simplejwt.models import TokenUser
from apps.base.models import BaseModel
from apps.usuarios.models import Usuario

class BaseSerializer(serializers.ModelSerializer):
    created_at = serializers.SerializerMethodField(read_only=True)
    updated_at = serializers.SerializerMethodField(read_only=True)
    created_by = serializers.SerializerMethodField(read_only=True)
    updated_by = serializers.SerializerMethodField(read_only=True)
    #status_model = serializers.CharField(source='get_status_model_display', read_only=True)

    status_model = serializers.ChoiceField(
        choices=BaseModel.STATUS_CHOICES,
        required=False,
        help_text="Estado del registro"
    )
    #status_model_display = serializers.CharField(
    #    source='get_status_model_display',
    #    read_only=True,
    #    help_text="Descripción legible del estado"
    #)


    def get_updated_at(self, obj):
        if obj.updated_at:
            local_time = timezone.localtime(obj.updated_at)
            return local_time.strftime("%Y-%m-%d %H:%M:%S")
        return ''
    def get_created_at(self, obj):
        if obj.created_at:
            local_time = timezone.localtime(obj.created_at)
            return local_time.strftime("%Y-%m-%d %H:%M:%S")
        return ''
    def get_created_by(self, obj):
        return str(obj.created_by) if obj.created_by else ""
    
    def get_updated_by(self, obj):
        return str(obj.updated_by) if obj.updated_by else ""

    class Meta:
        abstract = True
        #exclude = ('status_model',)
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'created_by', 'updated_by', 'status_model')

    

    def create(self, validated_data):
        request = self.context.get('request', None)
        if request and request.user.is_authenticated:
            user = request.user
            if isinstance(user, TokenUser):
                try:
                    user = Usuario.objects.get(id=user.id)
                except Usuario.DoesNotExist:
                    user = None
            validated_data['created_by'] = user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        request = self.context.get('request', None)
        if request and request.user.is_authenticated:
            user = request.user
            if isinstance(user, TokenUser):
                try:
                    user = Usuario.objects.get(id=user.id)
                except Usuario.DoesNotExist:
                    user = None
            validated_data['updated_by'] = user
        return super().update(instance, validated_data)
    



class SerializerRelatedField(serializers.PrimaryKeyRelatedField):
    """PrimaryKeyRelatedField que acepta tanto un entero (pk) como un dict {"id": pk}.

    - to_internal_value: si recibe dict, extrae 'id' y valida la existencia.
    - to_representation: mantiene el comportamiento por defecto (retorna el pk).
    """
    def to_internal_value(self, data):
        # Aceptar payload como {"id": 1}
        if isinstance(data, dict):
            pk = data.get('id')
            if pk is None:
                raise serializers.ValidationError({"field": "Se requiere el campo 'id' dentro de field."})
            return super().to_internal_value(pk)
        return super().to_internal_value(data)
    


class FlexiblePKRelatedField(serializers.PrimaryKeyRelatedField):
    """
    Permite aceptar tanto un entero como un dict {'id': pk} para relaciones.
    """
    def to_internal_value(self, data):
        if isinstance(data, dict):
            if "id" not in data:
                raise serializers.ValidationError("El diccionario debe contener la clave 'id'.")
            data = data["id"]
        return super().to_internal_value(data)