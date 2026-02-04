from apps.base.serializer import BaseSerializer
from rest_framework import serializers
from ..models import Empresa
from apps.contabilidad.models import RegimenFiscal

from drf_spectacular.utils import extend_schema_field

#serializers
from apps.contabilidad.serializers.regimenSerializer import RegimenFiscalDetailSerializer, RegimenFiscalRelatedField





class EmpresaSerializer(BaseSerializer):   
    regimen_fiscal = RegimenFiscalRelatedField(
        queryset=RegimenFiscal.objects.all(),
        required=False,
        allow_null=True,
        help_text="ID del régimen fiscal de la empresa (puede ser un entero o {\"id\": <pk>})"
    )
#
    regimen_fiscal_detalle = serializers.SerializerMethodField(
        help_text="Detalle del régimen fiscal de la empresa"
    )

    cuenta_clave = serializers.CharField(
        max_length=20, required=False, allow_blank=True, allow_null=True, default=None,
        help_text="Cuenta clave de la empresa"
    )

    class Meta:
        model = Empresa
        fields = (
            'id', 'nombre', 'rfc', 'telefono', 'email', 'direccion_fiscal',
            'regimen_fiscal', 'regimen_fiscal_detalle', 'cuenta_clave',
            'created_at', 'updated_at', 'created_by', 'updated_by', 'status_model'
        )
        read_only_fields = ('created_at', 'updated_at', 'created_by', 'updated_by', 'status_model')


    @extend_schema_field(RegimenFiscalDetailSerializer)
    def get_regimen_fiscal_detalle(self, obj):
        if obj.regimen_fiscal:
            return RegimenFiscalDetailSerializer(obj.regimen_fiscal).data
        return None
    






class EmpresaMiniSerializer(BaseSerializer):
    class Meta:
        model = Empresa
        fields = ('id', 'nombre', 'rfc')
        read_only_fields = ('id', 'nombre', 'rfc')     