from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
#models
from apps.erp.models import Caja,CajaApertura, CajaTransaccion
from apps.usuarios.models import Usuario
#serializers base
from apps.base.serializer import BaseSerializer, FlexiblePKRelatedField, SerializerRelatedField

from .movimientos import MovimientoCajaTransaccionSerializer


class EstadisticaMetodoPagoSerializer(serializers.Serializer):
    """
    Serializer para estadísticas agrupadas por método de pago
    """
    metodo_pago_id = serializers.IntegerField(
        allow_null=True,
        help_text="ID del método de pago"
    )
    metodo_pago = serializers.CharField(
        help_text="Nombre del método de pago"
    )
    total = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Total acumulado para este método de pago"
    )
    
    class Meta:
        fields = ['metodo_pago_id', 'metodo_pago', 'total']


class CajaAperturaMiniSerializer(serializers.ModelSerializer):
    caja_name = serializers.SerializerMethodField()
    fecha_apertura = serializers.DateTimeField(format="%d-%m-%Y %H:%M:%S", read_only=True)
    usuario_name = serializers.SerializerMethodField()
    fecha_cierre = serializers.SerializerMethodField()
    aperturada_por = serializers.SerializerMethodField()
    monto_final = serializers.SerializerMethodField()
    usuario_cierre_name = serializers.SerializerMethodField()
    usuario_apertura_name = serializers.SerializerMethodField()
    class Meta:
        model = CajaApertura
        fields = ['id', 'caja', 'monto_inicial', 'fecha_apertura',
                  'caja_name', 'is_abierta', 'monto_final', 'usuario_name',
                  'fecha_cierre', 'aperturada_por',
                  'monto_final', 'usuario_cierre_name','usuario_apertura_name',
                  
                  ]
        read_only_fields = ['id', 'caja', 'monto_inicial', 'fecha_apertura',
                            'caja_name', 'usuario_name', 'fecha_cierre',
                            'aperturada_por', 'monto_final', 'usuario_cierre_name',
                            'usuario_apertura_name', 'is_abierta'
                            ]
    
    def get_caja_name(self, obj):
        return obj.caja.nombre if obj.caja else ""
    def get_usuario_name(self, obj):
        return obj.usuario.full_name() if obj.usuario else ""

    def get_fecha_cierre(self, obj):
        if obj.updated_at:
            return obj.updated_at.strftime("%d-%m-%Y %H:%M:%S")
        return "--"

    def get_aperturada_por(self, obj):
        if obj.created_by:
            return obj.created_by.full_name() if obj.created_by else "N/A"
        return "--"

    def get_monto_final(self, obj):
        return obj.monto_final if obj.monto_final is not None else 0.0

    def get_usuario_cierre_name(self, obj):
        if obj.updated_by:
            return obj.updated_by.full_name() if obj.updated_by else "N/A"
        return "--"
    
    def get_usuario_apertura_name(self, obj):
        if obj.created_by:
            return obj.created_by.full_name() if obj.created_by else "N/A"
        return "--"
class CajaAperturaSerializer(BaseSerializer):
    caja = SerializerRelatedField(
        queryset=Caja.objects.filter(status_model=Caja.STATUS_MODEL_ACTIVE),
        help_text="ID de la caja o dic (id: <id>)",
        required=True
    )
    caja_name = serializers.SerializerMethodField()
    usuario = SerializerRelatedField(
        queryset=Usuario.objects.filter(is_active=True),
        help_text="ID del usuario asignado (id: <id>)",
        required=True,
        allow_null=True
    )
    usuario_name = serializers.SerializerMethodField()
    
    fecha_apertura = serializers.DateTimeField(format="%d-%m-%Y %H:%M:%S", read_only=True)
    fecha_cierre = serializers.SerializerMethodField()
    
    #transacciones = MovimientoCajaTransaccionSerializer(many=True, read_only=True)
    
    # Estadísticas de ingresos y salidas por método de pago
    estadisticas_ingresos = serializers.SerializerMethodField(read_only=True)
    estadisticas_salidas = serializers.SerializerMethodField(read_only=True)
    estadisticas_gastos = serializers.SerializerMethodField(read_only=True)
    total_ingresos = serializers.SerializerMethodField(read_only=True)
    total_salidas = serializers.SerializerMethodField(read_only=True)
    balance_neto = serializers.SerializerMethodField(read_only=True)
    efectivo_caja = serializers.SerializerMethodField(read_only=True)
    
    
    class Meta:
        model = CajaApertura
        fields = ['id', 'caja','usuario', 'monto_inicial',
                  'fecha_apertura','monto_final', 'is_abierta',
                  'caja_name', 'usuario_name',
                  'created_at', 'updated_at', 'created_by', 'updated_by', 'status_model',
                  #'transacciones',
                  'estadisticas_ingresos', 'estadisticas_salidas', 'estadisticas_gastos',
                  'total_ingresos', 'total_salidas', 'balance_neto','fecha_cierre',
                    'efectivo_caja'
                  ]
        read_only_fields = ['id', 
                            'fecha_apertura',
                            'caja_name', 'usuario_name',
                            'monto_final', 'is_abierta',
                            'created_at', 'updated_at', 'created_by', 'updated_by', 'status_model',
                            #'transacciones',
                            'estadisticas_ingresos', 'estadisticas_salidas', 'estadisticas_gastos',
                            'total_ingresos', 'total_salidas', 'balance_neto','fecha_cierre',
                            'efectivo_caja'
                            ]
        
        
        
    def get_usuario_name(self, obj):
        return obj.usuario.full_name() if obj.usuario else "N/A"
    
    def get_caja_name(self, obj):
        return obj.caja.nombre if obj.caja else "N/A"
    
    def get_fecha_cierre(self, obj):
        if obj.updated_at:
            return obj.updated_at.strftime("%d-%m-%Y %H:%M:%S")
        return ""
    
    def get_efectivo_caja(self, obj):
        """
        Calcula el efectivo disponible en caja basado en las transacciones
        Optimizado: usa las transacciones ya precargadas
        """
        
        from django.db import models
        efectivo = 0.0
        
        #filtrar y sumar en memoria usando las transacciones ya precargadas desde una consulta
        efectivo_query = obj.transacciones.filter(
            status_model=CajaTransaccion.STATUS_MODEL_ACTIVE,
            tipo=CajaTransaccion.TIPO_ENTRADA,
            metodo_pago__nombre__iexact='EFECTIVO'
        ).aggregate(total=models.Sum('monto'))
        efectivo += float(efectivo_query['total']) if efectivo_query['total'] else 0.0
        
        salida_efectivo_query = obj.transacciones.filter(
            status_model=CajaTransaccion.STATUS_MODEL_ACTIVE,
            tipo=CajaTransaccion.TIPO_SALIDA,
            metodo_pago__nombre__iexact='EFECTIVO'
        ).aggregate(total=models.Sum('monto'))
        efectivo -= float(salida_efectivo_query['total']) if salida_efectivo_query['total'] else 0.0
        
        return round(efectivo, 2)
        
    
    @extend_schema_field(EstadisticaMetodoPagoSerializer(many=True))
    def get_estadisticas_ingresos(self, obj):
        """
        Estadísticas de ingresos agrupados por método de pago
        Optimizado: usa las transacciones ya precargadas
        """
        
        from collections import defaultdict
        
        # Agrupar en memoria usando las transacciones ya precargadas
        ingresos_por_metodo = defaultdict(float)
        
        for transaccion in obj.transacciones.all():
            if (transaccion.tipo == CajaTransaccion.TIPO_ENTRADA and 
                transaccion.status_model == CajaTransaccion.STATUS_MODEL_ACTIVE):
                
                metodo_id = transaccion.metodo_pago.id if transaccion.metodo_pago else None
                metodo_nombre = transaccion.metodo_pago.nombre if transaccion.metodo_pago else 'Sin método'
                key = (metodo_id, metodo_nombre)
                ingresos_por_metodo[key] += float(transaccion.monto)
        
        # Convertir a lista de diccionarios
        estadisticas = [
            {
                'metodo_pago_id': metodo_id,
                'metodo_pago': metodo_nombre,
                'total': total
            }
            for (metodo_id, metodo_nombre), total in ingresos_por_metodo.items()
        ]
        
        # Ordenar por total descendente
        estadisticas.sort(key=lambda x: x['total'], reverse=True)
        
        # Serializar con el serializer dedicado
        return EstadisticaMetodoPagoSerializer(estadisticas, many=True).data
    
    @extend_schema_field(EstadisticaMetodoPagoSerializer(many=True))
    def get_estadisticas_gastos(self, obj):
        """
        Estadísticas de gastos agrupados por método de pago
        Optimizado: usa las transacciones ya precargadas
        """
        
        from collections import defaultdict
        
        # Agrupar en memoria usando las transacciones ya precargadas
        ingresos_por_metodo = defaultdict(float)
        
        for transaccion in obj.transacciones.all():
            if (transaccion.tipo == CajaTransaccion.TIPO_GASTO and 
                transaccion.status_model == CajaTransaccion.STATUS_MODEL_ACTIVE):
                
                metodo_id = transaccion.metodo_pago.id if transaccion.metodo_pago else None
                metodo_nombre = transaccion.metodo_pago.nombre if transaccion.metodo_pago else 'Sin método'
                key = (metodo_id, metodo_nombre)
                ingresos_por_metodo[key] += float(transaccion.monto)
        
        # Convertir a lista de diccionarios
        estadisticas = [
            {
                'metodo_pago_id': metodo_id,
                'metodo_pago': metodo_nombre,
                'total': total
            }
            for (metodo_id, metodo_nombre), total in ingresos_por_metodo.items()
        ]
        
        # Ordenar por total descendente
        estadisticas.sort(key=lambda x: x['total'], reverse=True)
        
        # Serializar con el serializer dedicado
        return EstadisticaMetodoPagoSerializer(estadisticas, many=True).data
    
    @extend_schema_field(EstadisticaMetodoPagoSerializer(many=True))
    def get_estadisticas_salidas(self, obj):
        """
        Estadísticas de salidas agrupadas por método de pago
        Optimizado: usa las transacciones ya precargadas
        """
        
        from collections import defaultdict
        
        # Agrupar en memoria usando las transacciones ya precargadas
        salidas_por_metodo = defaultdict(float)
        
        for transaccion in obj.transacciones.all():
            if (transaccion.tipo == CajaTransaccion.TIPO_SALIDA and 
                transaccion.status_model == CajaTransaccion.STATUS_MODEL_ACTIVE):
                
                metodo_id = transaccion.metodo_pago.id if transaccion.metodo_pago else None
                metodo_nombre = transaccion.metodo_pago.nombre if transaccion.metodo_pago else 'Sin método'
                key = (metodo_id, metodo_nombre)
                salidas_por_metodo[key] += float(transaccion.monto)
        
        # Convertir a lista de diccionarios
        estadisticas = [
            {
                'metodo_pago_id': metodo_id,
                'metodo_pago': metodo_nombre,
                'total': total
            }
            for (metodo_id, metodo_nombre), total in salidas_por_metodo.items()
        ]
        
        # Ordenar por total descendente
        estadisticas.sort(key=lambda x: x['total'], reverse=True)
        
        # Serializar con el serializer dedicado
        return EstadisticaMetodoPagoSerializer(estadisticas, many=True).data
    
    @extend_schema_field(serializers.DecimalField(max_digits=20, decimal_places=2))
    def get_total_ingresos(self, obj):
        """
        Total de todos los ingresos
        Optimizado: usa la anotación precalculada del queryset
        """
        # Usar la anotación si existe, sino calcular en memoria
        if hasattr(obj, '_total_ingresos') and obj._total_ingresos is not None:
            return float(obj._total_ingresos)
        
        # Fallback: calcular desde transacciones precargadas
        
        total = sum(
            float(t.monto) for t in obj.transacciones.all()
            if t.tipo == CajaTransaccion.TIPO_ENTRADA and 
               t.status_model == CajaTransaccion.STATUS_MODEL_ACTIVE
        )
        return total
    
    @extend_schema_field(serializers.DecimalField(max_digits=20, decimal_places=2))
    def get_total_salidas(self, obj):
        """
        Total de todas las salidas
        Optimizado: usa la anotación precalculada del queryset
        """
        # Usar la anotación si existe, sino calcular en memoria
        if hasattr(obj, '_total_salidas') and obj._total_salidas is not None:
            return float(obj._total_salidas)
        
        # Fallback: calcular desde transacciones precargadas
        
        total = sum(
            float(t.monto) for t in obj.transacciones.all()
            if t.tipo == CajaTransaccion.TIPO_SALIDA and 
               t.status_model == CajaTransaccion.STATUS_MODEL_ACTIVE
        )
        return total
    
    @extend_schema_field(serializers.DecimalField(max_digits=20, decimal_places=2))
    def get_balance_neto(self, obj):
        """
        Balance neto: monto_inicial + ingresos - salidas
        """
        total_ingresos = self.get_total_ingresos(obj)
        total_salidas = self.get_total_salidas(obj)
        monto_inicial = float(obj.monto_inicial) if obj.monto_inicial else 0.0
        
        return monto_inicial + total_ingresos - total_salidas