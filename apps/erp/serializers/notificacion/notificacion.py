# notifications/serializers.py
from rest_framework import serializers
from apps.erp.models import Notificacion

class NotificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notificacion
        fields = '__all__'
