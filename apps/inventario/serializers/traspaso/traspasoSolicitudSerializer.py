from rest_framework import serializers
from decimal import Decimal

from apps.inventario.models import SolicitudTraspaso, SolicitudTraspasoDetalle
from apps.erp.models import Almacen, Producto
from apps.usuarios.models import Usuario
from apps.base.serializer import FlexiblePKRelatedField


class SolicitudTraspasoDetalleSerializer(serializers.ModelSerializer):
    """
    Serializer para el detalle de productos en una solicitud de traspaso
    """
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    producto_codigo = serializers.CharField(source='producto.codigo', read_only=True)
    producto_unidad = serializers.CharField(source='producto.unidad_sat.nombre', read_only=True)
    
    class Meta:
        model = SolicitudTraspasoDetalle
        fields = [
            'id',
            'producto',
            'producto_nombre',
            'producto_codigo',
            'producto_unidad',
            'cantidad',
        ]
        read_only_fields = ['id']
    
    def validate_cantidad(self, value):
        """Validar que la cantidad sea mayor a 0"""
        if value <= 0:
            raise serializers.ValidationError("La cantidad debe ser mayor a 0")
        return value


class SolicitudTraspasoListSerializer(serializers.ModelSerializer):
    """
    Serializer para listar solicitudes de traspaso (vista resumida)
    """
    almacen_solicitante_nombre = serializers.CharField(source='almacen_solicitante.nombre', read_only=True)
    almacen_surtidor_nombre = serializers.CharField(source='almacen_surtidor.nombre', read_only=True)
    total_productos = serializers.SerializerMethodField()
    creado_por_nombre = serializers.CharField(source='created_by.get_full_name', read_only=True)
    aprobado_por_nombre = serializers.CharField(source='aprobado_por.get_full_name', read_only=True)
    rechazado_por_nombre = serializers.CharField(source='rechazado_por.get_full_name', read_only=True)
    
    class Meta:
        model = SolicitudTraspaso
        fields = [
            'id',
            'referencia',
            'almacen_solicitante',
            'almacen_solicitante_nombre',
            'almacen_surtidor',
            'almacen_surtidor_nombre',
            'estado',
            'total_productos',
            'created_at',
            'creado_por_nombre',
            'aprobado_el',
            'aprobado_por_nombre',
            'rechazado_el',
            'rechazado_por_nombre',
        ]
    
    def get_total_productos(self, obj):
        """Retorna el total de productos diferentes en la solicitud"""
        return obj.detalles.count()


class SolicitudTraspasoDetailSerializer(serializers.ModelSerializer):
    """
    Serializer para ver el detalle completo de una solicitud de traspaso
    """
    almacen_solicitante_nombre = serializers.CharField(source='almacen_solicitante.nombre', read_only=True)
    almacen_surtidor_nombre = serializers.CharField(source='almacen_surtidor.nombre', read_only=True)
    detalles = SolicitudTraspasoDetalleSerializer(many=True, read_only=True)
    creado_por_nombre = serializers.CharField(source='created_by.get_full_name', read_only=True)
    aprobado_por_nombre = serializers.SerializerMethodField()
    rechazado_por_nombre = serializers.SerializerMethodField()
    referencia = serializers.SerializerMethodField()
    
    rechazado_el = serializers.SerializerMethodField()
    class Meta:
        model = SolicitudTraspaso
        fields = [
            'id',
            'referencia',
            'almacen_solicitante',
            'almacen_solicitante_nombre',
            'almacen_surtidor',
            'almacen_surtidor_nombre',
            'estado',
            'nota',
            'movimiento',
            'detalles',
            'created_at',
            'created_by',
            'creado_por_nombre',
            'aprobado_el',
            'aprobado_por',
            'aprobado_por_nombre',
            'rechazado_el',
            'rechazado_por',
            'rechazado_por_nombre',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'referencia',
            'movimiento',
            'aprobado_el',
            'aprobado_por',
            'rechazado_el',
            'rechazado_por',
            'created_at',
            'created_by',
            'updated_at',
        ]
        
    def get_aprobado_por_nombre(self, obj):
        """Obtener el nombre completo del usuario que aprobó la solicitud"""
        return obj.aprobado_por.full_name() if obj.aprobado_por else ''
    def get_rechazado_por_nombre(self, obj):
        """Obtener el nombre completo del usuario que rechazó la solicitud"""
        return obj.rechazado_por.full_name() if obj.rechazado_por else ''
    def get_referencia(self, obj):
        """Generar referencia única para la solicitud"""
        return obj.referencia if obj.referencia is not None else f""

    def get_rechazado_el(self, obj):
        """Obtener la fecha de rechazo formateada"""
        return obj.rechazado_el.strftime("%Y-%m-%d %H:%M:%S") if obj.rechazado_el else ''

class SolicitudTraspasoCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer para crear y actualizar solicitudes de traspaso
    """
    almacen_solicitante = FlexiblePKRelatedField(
        queryset=Almacen.objects.filter(status_model='ACTIVE'),
        required=False,
        allow_null=True,
        help_text="Almacén que solicita el traspaso toma por defecto el almacén del usuario"
    )
    almacen_surtidor = FlexiblePKRelatedField(
        queryset=Almacen.objects.filter(status_model='ACTIVE'),
        required=True,
        help_text="Almacén desde donde se surtirá el traspaso"
    )
    detalles = SolicitudTraspasoDetalleSerializer(many=True)
    
    class Meta:
        model = SolicitudTraspaso
        fields = [
            'id',
            'almacen_solicitante',
            'almacen_surtidor',
            'nota',
            'detalles',
        ]
        read_only_fields = ['id']
    
    def validate(self, data):
        """Validaciones generales"""
        # Validar que no sea el mismo almacén
        if data.get('almacen_solicitante') == data.get('almacen_surtidor'):
            raise serializers.ValidationError({
                'almacen_surtidor': 'El almacén surtidor debe ser diferente al almacén solicitante'
            })
        
        # Validar que haya al menos un producto
        detalles = data.get('detalles', [])
        if not detalles:
            raise serializers.ValidationError({
                'detalles': 'Debe incluir al menos un producto en la solicitud'
            })
        
        # Validar productos duplicados
        productos_ids = [d['producto'].id for d in detalles]
        if len(productos_ids) != len(set(productos_ids)):
            raise serializers.ValidationError({
                'detalles': 'No puede incluir el mismo producto más de una vez'
            })
        
        return data
    
    def create(self, validated_data):
        """Crear solicitud con sus detalles"""
        detalles_data = validated_data.pop('detalles')
        
        # Crear solicitud
        solicitud = SolicitudTraspaso.objects.create(**validated_data)
        
        # Crear detalles
        for detalle_data in detalles_data:
            SolicitudTraspasoDetalle.objects.create(
                solicitud=solicitud,
                **detalle_data
            )
        
        return solicitud
    
    def update(self, instance, validated_data):
        """Actualizar solicitud y sus detalles"""
        # Solo permitir actualización si está pendiente
        if instance.estado != SolicitudTraspaso.PENDIENTE:
            raise serializers.ValidationError({
                'estado': f'No se puede modificar una solicitud en estado {instance.estado}'
            })
        
        detalles_data = validated_data.pop('detalles', None)
        
        # Actualizar campos de la solicitud
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Actualizar detalles si se proporcionaron
        if detalles_data is not None:
            # Eliminar detalles existentes
            instance.detalles.all().delete()
            
            # Crear nuevos detalles
            for detalle_data in detalles_data:
                SolicitudTraspasoDetalle.objects.create(
                    solicitud=instance,
                    **detalle_data
                )
        
        return instance
    
    def to_representation(self, instance):
        """Usar el serializer de detalle para la respuesta"""
        return SolicitudTraspasoDetailSerializer(instance).data


class AprobarRechazarSolicitudSerializer(serializers.Serializer):
    """
    Serializer para aprobar o rechazar una solicitud
    """
    nota = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Nota opcional para justificar la aprobación o rechazo"
    )
