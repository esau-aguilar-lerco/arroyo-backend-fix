from apps.base.serializer import BaseSerializer, serializers

from ..models import Proveedor,DireccionProveedor

from decimal import Decimal
from django.db.models import Sum, F
from django.db.models.functions import Coalesce
from rest_framework import serializers

from ..models import Proveedor
from apps.credito.models import CreditoProveedor

class ProveedorSolicitudCreditoSerializer(serializers.ModelSerializer):
    total_credito = serializers.SerializerMethodField()
    disponible_credito = serializers.SerializerMethodField()
    puede_pagar_credito = serializers.SerializerMethodField()

    class Meta:
        model = Proveedor
        fields = (
            'id',
            'nombre',
            'total_credito',
            'disponible_credito',
            'puede_pagar_credito',
        )

    # 🔹 LÍMITE DE CRÉDITO ASIGNADO AL PROVEEDOR
    def get_total_credito(self, obj):
        # erp_proveedor.monto
        return obj.monto

    # 🔹 CRÉDITO DISPONIBLE REAL (YA CON PAGOS)
    def get_disponible_credito(self, obj):
        usado = CreditoProveedor.objects.filter(
            proveedor=obj,
            estado='ACTIVA',
            is_pagado=False,
            status_model='ACTIVE'
        ).aggregate(
            total=Coalesce(
                Sum(F('monto') - F('monto_pagado')),
                Decimal('0.00')
            )
        )['total']

        return obj.monto - usado

    def get_puede_pagar_credito(self, obj):
        return self.get_disponible_credito(obj) > 0

class DireccionProveedorSerializer(serializers.ModelSerializer):
    estado = serializers.SerializerMethodField()
    estado_id = serializers.IntegerField(source='estado.id', read_only=True)

    class Meta:
        model = DireccionProveedor
        fields = '__all__'

    def get_estado(self, obj):
        if obj.estado:
            return {
                'id': obj.estado.id,
                'nombre': obj.estado.nombre,  # Ajusta los campos según tu modelo Estado
                # Agrega aquí otros campos relevantes de Estado
            }
        return None


class ProveedorSerializer(BaseSerializer):
    #direccion_proveedor = DireccionProveedorSerializer(many=True)
    monto = serializers.FloatField( required=False, default=0.0)

    origen = serializers.ChoiceField(choices=Proveedor.ORIGEN_LIST, default=Proveedor.ORIGEN_MEX, help_text="Origen del proveedor", required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = Proveedor
        fields = '__all__'
        read_only_fields = ('codigo','total_credito')



class ProveedorMiniSerializer(BaseSerializer):
    class Meta:
        model = Proveedor
        fields = ('id', 'nombre', 'codigo', 'full_name')


        


