from decimal import Decimal
from django.db import transaction
from rest_framework import serializers
from django.utils import timezone
from apps.credito.models import CreditoCliente, PagosCredito
from apps.erp.models import CajaApertura,CajaTransaccion
#from apps.contabilidad.models import MetodoPago

from apps.base.serializer import FlexiblePKRelatedField, SerializerRelatedField
from apps.erp.serializers.caja.movimientos import MetodoPagoCajaAperturaSerializer

class PagosCreditoSerializer(serializers.ModelSerializer):
    """
    Serializer para PagosCredito
    """
    metodo_pago_nombre = serializers.CharField(source='metodo_pago.nombre', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = PagosCredito
        fields = [
            'id',
            'credito',
            'monto',
            'metodo_pago',
            'metodo_pago_nombre',
            'created_at',
            'created_by',
            'created_by_username',
            'status_model'
        ]
        read_only_fields = ['id', 'created_at', 'created_by', 'created_by_username']


class PagosCreditoMiniSerializer(serializers.ModelSerializer):
    """
    Serializer mini para PagosCredito
    """
    pago_name = serializers.SerializerMethodField()
    creado_por_name = serializers.SerializerMethodField()
    class Meta:
        model = PagosCredito
        fields = [
            'id',
            'monto',
            'metodo_pago',
            'pago_name',
            'created_at',
            'created_by',
            'creado_por_name',
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_pago_name(self, obj):
        return f"{obj.metodo_pago.nombre}"
    
    def get_creado_por_name(self, obj):
        return obj.created_by.full_name()




class PagoCreditoCreateSingularSerializer(serializers.Serializer):
    credito = FlexiblePKRelatedField(
        queryset=CreditoCliente.objects.filter(is_pagado=False),
        help_text="ID del crédito o dic {id: <id>}",
        required=True
    )
    cantidad_pagar = serializers.DecimalField(max_digits=12, decimal_places=2, help_text="Cantidad a pagar del crédito", required=True)
    pagos = MetodoPagoCajaAperturaSerializer(
        many=True,
        help_text="Lista de pagos a registrar en el crédito",
        required=True
    )
    
    def validate_pagos(self, value):
        """Validar que haya al menos un método de pago"""
        if not value or len(value) == 0:
            raise serializers.ValidationError("Debe proporcionar al menos un método de pago.")
        return value
    
    def validate(self, attrs):
        request  = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            raise serializers.ValidationError("No se pudo identificar al usuario.")
        usuario = request.user
        
        credito = attrs['credito']
        pagos = attrs['pagos']
      #  Validar que el usuario tenga una caja abierta
        caja_apertura = usuario.get_mi_caja()
        
        if not caja_apertura:
            raise serializers.ValidationError(
                f'El usuario {usuario.get_full_name()} no tiene una caja abierta.'
            )
            
        #  Calcular total de pagos
        total_pagos = float(sum(Decimal(str(pago['monto'])) for pago in pagos))
        
        adeudo_credito = credito.adeudo_actual()
        
        if float(attrs['cantidad_pagar']) > adeudo_credito:
            raise serializers.ValidationError(
                f'La cantidad a pagar (${attrs["cantidad_pagar"]:.2f}) excede el adeudo de la crédito (${adeudo_credito:.2f}).'
            )
            
        cambio = abs(total_pagos - float(attrs['cantidad_pagar']))
            
        #if total_pagos > adeudo_credito:
        #    raise serializers.ValidationError(
        #        f'El total de pagos (${total_pagos:.2f}) excede el adeudo de la crédito (${adeudo_credito:.2f}).'
        #    )
        
        attrs['_cambio'] = cambio
        attrs['_caja_apertura'] = caja_apertura
        attrs['_total_pagos'] = total_pagos
        attrs['_usuario'] = usuario
        return attrs
    
    @transaction.atomic
    def create(self, validated_data):
        credito = validated_data['credito']
        pagos_data = validated_data['pagos']
        caja_apertura = validated_data['_caja_apertura']
        usuario = validated_data['_usuario']
        cambio = validated_data['_cambio']
        
        for pago_data in pagos_data:
            metodo_pago = pago_data['metodo_pago']
            monto = pago_data['monto']
            referencia = pago_data.get('referencia', '').strip()
            
            if cambio > 0 and metodo_pago.nombre.upper() == 'EFECTIVO':
                monto = monto - Decimal(str(cambio))
            
            mov = credito.abonar(
                monto=monto,
                metodo_pago=metodo_pago,
                usuario=usuario
            )
            CajaTransaccion.objects.create(
                caja_apertura=caja_apertura,
                monto=monto + Decimal(str(cambio)),
                metodo_pago=metodo_pago,
                referencia=referencia,
                created_by=usuario,
                descripcion=f'Pago de crédito ID {credito.id}'
            )
            if cambio > 0 and metodo_pago.nombre.upper() == 'EFECTIVO':
                CajaTransaccion.objects.create(
                    caja_apertura=caja_apertura,
                    monto=Decimal(str(cambio)),
                    tipo=CajaTransaccion.TIPO_SALIDA,
                    metodo_pago=metodo_pago,
                    referencia='Cambio entregado',
                    created_by=usuario,
                    descripcion=f'Cambio entregado en pago de crédito ID {credito.id}'
                )
            
        return mov
    
class PagoCreditoUpdateSerializer(serializers.Serializer):
    """
    Serializer para actualizar un abono de crédito.
    
    Elimina los pagos existentes y las transacciones de caja asociadas,
    luego crea los nuevos pagos.
    """
    credito = FlexiblePKRelatedField(
        queryset=CreditoCliente.objects.filter(is_pagado=False),
        help_text="ID del crédito o dic {id: <id>}",
        required=True
    )
    cantidad_pagar = serializers.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        help_text="Nueva cantidad a pagar del crédito", 
        required=True
    )
    pagos = MetodoPagoCajaAperturaSerializer(
        many=True,
        help_text="Lista de nuevos pagos a registrar en el crédito",
        required=True
    )
    pago_anterior_id = serializers.IntegerField(
        help_text="ID del pago anterior a eliminar/actualizar",
        required=True
    )
    
    def validate_pagos(self, value):
        """Validar que haya al menos un método de pago"""
        if not value or len(value) == 0:
            raise serializers.ValidationError("Debe proporcionar al menos un método de pago.")
        return value
    
    def validate_pago_anterior_id(self, value):
        """Validar que el pago anterior exista"""
        try:
            pago = PagosCredito.objects.get(id=value)
        except PagosCredito.DoesNotExist:
            raise serializers.ValidationError("El pago especificado no existe.")
        return value
    
    def validate(self, attrs):
        request = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            raise serializers.ValidationError("No se pudo identificar al usuario.")
        usuario = request.user
        
        credito = attrs['credito']
        pagos = attrs['pagos']
        pago_anterior_id = attrs['pago_anterior_id']
        
        # Obtener pago anterior
        try:
            pago_anterior = PagosCredito.objects.get(id=pago_anterior_id)
        except PagosCredito.DoesNotExist:
            raise serializers.ValidationError("El pago anterior no existe.")
        
        # Validar que el pago pertenezca al crédito
        if pago_anterior.credito_id != credito.id:
            raise serializers.ValidationError(
                "El pago especificado no pertenece al crédito indicado."
            )
        
        # Validar que el usuario tenga una caja abierta
        caja_apertura = usuario.get_mi_caja()
        
        if not caja_apertura:
            raise serializers.ValidationError(
                f'El usuario {usuario.get_full_name()} no tiene una caja abierta.'
            )
        
        # Calcular el adeudo considerando que se va a revertir el pago anterior
        monto_pago_anterior = float(pago_anterior.monto)
        adeudo_sin_pago_anterior = credito.adeudo_actual() + monto_pago_anterior
        
        if float(attrs['cantidad_pagar']) > adeudo_sin_pago_anterior:
            raise serializers.ValidationError(
                f'La cantidad a pagar (${attrs["cantidad_pagar"]:.2f}) excede el adeudo disponible (${adeudo_sin_pago_anterior:.2f}).'
            )
        
        # Calcular total de pagos
        total_pagos = float(sum(Decimal(str(pago['monto'])) for pago in pagos))
        cambio = abs(total_pagos - float(attrs['cantidad_pagar']))
        
        attrs['_cambio'] = cambio
        attrs['_caja_apertura'] = caja_apertura
        attrs['_total_pagos'] = total_pagos
        attrs['_usuario'] = usuario
        attrs['_pago_anterior'] = pago_anterior
        attrs['_monto_pago_anterior'] = monto_pago_anterior
        return attrs
    
    @transaction.atomic
    def update(self, instance, validated_data):
        """
        Actualizar el abono: eliminar pagos anteriores y crear nuevos
        """
        credito = validated_data['credito']
        pagos_data = validated_data['pagos']
        caja_apertura = validated_data['_caja_apertura']
        usuario = validated_data['_usuario']
        cambio = validated_data['_cambio']
        pago_anterior = validated_data['_pago_anterior']
        monto_pago_anterior = validated_data['_monto_pago_anterior']
        
        # 1. Revertir el pago anterior en el crédito
        credito.monto_pagado -= Decimal(str(monto_pago_anterior))
        credito.cliente.total_credito = float(credito.cliente.total_credito) - monto_pago_anterior
        credito.cliente.save(update_fields=["total_credito"])
        
        # 2. Si el crédito estaba pagado, reactivarlo
        if credito.is_pagado:
            credito.is_pagado = False
            credito.estado = CreditoCliente.ACTIVA
            credito.fecha_pago = None
        
        credito.save()
        
        # 3. Eliminar transacciones de caja asociadas al pago anterior
        CajaTransaccion.objects.filter(
            descripcion__icontains=f'crédito ID {credito.id}',
            created_at__date=pago_anterior.created_at.date(),
            created_by=pago_anterior.created_by
        ).delete()
        
        # 4. Eliminar el pago anterior
        pago_anterior.delete()
        
        # 5. Crear los nuevos pagos (similar al create)
        for pago_data in pagos_data:
            metodo_pago = pago_data['metodo_pago']
            monto = pago_data['monto']
            referencia = pago_data.get('referencia', '').strip()
            
            if cambio > 0 and metodo_pago.nombre.upper() == 'EFECTIVO':
                monto = monto - Decimal(str(cambio))
            
            mov = credito.abonar(
                monto=monto,
                metodo_pago=metodo_pago,
                usuario=usuario
            )
            CajaTransaccion.objects.create(
                caja_apertura=caja_apertura,
                monto=monto + Decimal(str(cambio)),
                metodo_pago=metodo_pago,
                referencia=referencia,
                created_by=usuario,
                descripcion=f'Pago de crédito ID {credito.id} (Editado)'
            )
            if cambio > 0 and metodo_pago.nombre.upper() == 'EFECTIVO':
                CajaTransaccion.objects.create(
                    caja_apertura=caja_apertura,
                    monto=Decimal(str(cambio)),
                    tipo=CajaTransaccion.TIPO_SALIDA,
                    metodo_pago=metodo_pago,
                    referencia='Cambio entregado',
                    created_by=usuario,
                    descripcion=f'Cambio entregado en pago de crédito ID {credito.id} (Editado)'
                )
        
        return credito


class PagoCreditoCancelarSerializer(serializers.Serializer):
    """
    Serializer para cancelar un abono de crédito.
    
    Elimina el pago y revierte el monto en el crédito y el saldo del cliente.
    """
    pago_id = serializers.IntegerField(
        help_text="ID del pago a cancelar",
        required=True
    )
    motivo = serializers.CharField(
        max_length=500,
        help_text="Motivo de la cancelación",
        required=False,
        allow_blank=True,
        default=""
    )
    
    def validate_pago_id(self, value):
        """Validar que el pago exista"""
        try:
            pago = PagosCredito.objects.select_related('credito', 'credito__cliente').get(id=value)
        except PagosCredito.DoesNotExist:
            raise serializers.ValidationError("El pago especificado no existe.")
        return value
    
    def validate(self, attrs):
        request = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            raise serializers.ValidationError("No se pudo identificar al usuario.")
        usuario = request.user
        
        pago_id = attrs['pago_id']
        pago = PagosCredito.objects.select_related('credito', 'credito__cliente').get(id=pago_id)
        
        # Validar que el usuario tenga una caja abierta
        caja_apertura = usuario.get_mi_caja()
        
        if not caja_apertura:
            raise serializers.ValidationError(
                f'El usuario {usuario.get_full_name()} no tiene una caja abierta.'
            )
        
        attrs['_pago'] = pago
        attrs['_caja_apertura'] = caja_apertura
        attrs['_usuario'] = usuario
        return attrs
    
    @transaction.atomic
    def create(self, validated_data):
        """
        Cancelar el abono: eliminar el pago y revertir montos
        """
        pago = validated_data['_pago']
        caja_apertura = validated_data['_caja_apertura']
        usuario = validated_data['_usuario']
        motivo = validated_data.get('motivo', '')
        
        credito = pago.credito
        monto_pago = float(pago.monto)
        metodo_pago = pago.metodo_pago
        
        # 1. Revertir el monto pagado en el crédito
        credito.monto_pagado -= Decimal(str(monto_pago))
        
        # 2. Revertir el saldo del cliente
        credito.cliente.total_credito = float(credito.cliente.total_credito) - monto_pago
        credito.cliente.save(update_fields=["total_credito"])
        
        # 3. Si el crédito estaba pagado, reactivarlo
        if credito.is_pagado:
            credito.is_pagado = False
            credito.estado = CreditoCliente.ACTIVA
            credito.fecha_pago = None
        
        credito.save()
        
        # 4. Eliminar transacciones de caja asociadas al pago
        CajaTransaccion.objects.filter(
            descripcion__icontains=f'crédito ID {credito.id}',
            created_at__date=pago.created_at.date(),
            created_by=pago.created_by
        ).delete()
        
        # 5. Registrar transacción de cancelación en caja (salida)
        CajaTransaccion.objects.create(
            caja_apertura=caja_apertura,
            monto=Decimal(str(monto_pago)),
            tipo=CajaTransaccion.TIPO_SALIDA,
            metodo_pago=metodo_pago,
            referencia=f'Cancelación de pago #{pago.id}',
            created_by=usuario,
            descripcion=f'Cancelación de pago de crédito ID {credito.id}. Motivo: {motivo}'
        )
        
        # 6. Eliminar el pago
        pago_id = pago.id
        pago.delete()
        
        return {
            'pago_id_cancelado': pago_id,
            'credito_id': credito.id,
            'cliente': credito.cliente.razon_social,
            'monto_revertido': monto_pago,
            'nuevo_adeudo': credito.adeudo_actual(),
            'motivo': motivo,
            'mensaje': f'Pago #{pago_id} cancelado exitosamente.'
        }


class PagoCreditoCreateMasivoSerializer(serializers.Serializer):
    """
    Serializer para registrar pagos masivos a múltiples créditos
    
    Permite registrar pagos a varios créditos en una sola petición,
    cada uno con sus propios métodos de pago.
    """
    lista = PagoCreditoCreateSingularSerializer(
        many=True,
        help_text="Lista de créditos con sus pagos a registrar",
        required=True
    )
    
    def validate_lista(self, value):
        """Validar que la lista no esté vacía"""
        if not value or len(value) == 0:
            raise serializers.ValidationError(
                "Debe proporcionar al menos un crédito para procesar pagos."
            )
        return value
    
    @transaction.atomic
    def create(self, validated_data):
        """
        Procesar todos los pagos masivos en una transacción atómica
        
        Si algún pago falla, se revierten todos los cambios.
        """
        lista_pagos = validated_data['lista']
        creditos_procesados = []
        pagos_totales = 0
        monto_total = Decimal('0.00')
        errores = []
        
        # Pasar el contexto a cada serializer hijo
        request = self.context.get('request')
        
        for index, pago_data in enumerate(lista_pagos):
            try:
                # Crear serializer hijo con contexto
                serializer = PagoCreditoCreateSingularSerializer(
                    data=pago_data,
                    context={'request': request}
                )
                
                # Validar
                if not serializer.is_valid():
                    errores.append({
                        'indice': index,
                        'credito_id': pago_data.get('credito'),
                        'errores': serializer.errors
                    })
                    continue
                
                # Crear el pago
                credito = serializer.save()
                
                # Calcular totales
                total_pago = sum(
                    Decimal(str(p['monto'])) 
                    for p in pago_data['pagos']
                )
                
                creditos_procesados.append({
                    'credito_id': credito.id,
                    'cliente': credito.cliente.get_full_name(),
                    'monto_pagado': float(total_pago),
                    'adeudo_restante': credito.adeudo_actual(),
                    'pagos_registrados': len(pago_data['pagos'])
                })
                
                pagos_totales += len(pago_data['pagos'])
                monto_total += total_pago
                
            except Exception as e:
                errores.append({
                    'indice': index,
                    'credito_id': pago_data.get('credito'),
                    'error': str(e)
                })
        
        # Si hay errores, lanzar excepción (rollback automático)
        if errores:
            raise serializers.ValidationError({
                'errores': errores,
                'mensaje': f'Se encontraron {len(errores)} errores al procesar los pagos.'
            })
        
        return {
            'creditos_procesados': creditos_procesados,
            'total_creditos': len(creditos_procesados),
            'total_pagos': pagos_totales,
            'monto_total': float(monto_total),
            'mensaje': f'Se procesaron exitosamente {len(creditos_procesados)} créditos con {pagos_totales} pagos.'
        }


class CreditoClienteSerializer(serializers.ModelSerializer):
    """
    Serializer para CreditoCliente (Dispersiones)
    """
    cliente_codigo = serializers.CharField(source='cliente.codigo', read_only=True)
    cliente_nombre = serializers.CharField(source='cliente.get_full_name', read_only=True)
    adeudo_actual = serializers.SerializerMethodField()
    ha_vencido = serializers.BooleanField(read_only=True)
    #estado_display = serializers.SerializerMethodField()
    dias_para_vencimiento = serializers.SerializerMethodField()
    pagos = PagosCreditoSerializer(many=True, read_only=True)
    total_pagos = serializers.SerializerMethodField()
    
    class Meta:
        model = CreditoCliente
        fields = [
            'id',
            'cliente',
            'cliente_codigo',
            'cliente_nombre',
            'fecha',
            'venta',
            'monto',
            'monto_pagado',
            'adeudo_actual',
            'dias_plazo',
            'fecha_vencimiento',
            'dias_para_vencimiento',
            'estado',
            #'estado_display',
            'is_pagado',
            'fecha_pago',
            'ha_vencido',
            'referencia',
            'observaciones',
            'pagos',
            'total_pagos',
            'created_at',
            'updated_at',
            'created_by',
            'updated_by',
            'status_model'
        ]
        read_only_fields = [
            'id', 'monto_pagado', 'is_pagado', 'fecha_pago',
            'fecha_vencimiento', 'created_at', 'updated_at'
        ]
    
    def get_adeudo_actual(self, obj):
        """Calcular adeudo actual"""
        return obj.adeudo_actual()
    
    
    
    def get_dias_para_vencimiento(self, obj):
        """Calcular días para vencimiento o días vencidos"""
        if not obj.fecha_vencimiento:
            return None
        
        if obj.is_pagado:
            return 0
        
        dias = (obj.fecha_vencimiento - timezone.now().date()).days
        return dias
    
    def get_total_pagos(self, obj):
        """Obtener total de pagos realizados"""
        return obj.pagos.count()


class CreditoClienteMiniSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source='cliente.get_full_name', read_only=True)
    class Meta:
        model = CreditoCliente
        fields = [
            'id',
            'cliente',
            'cliente_nombre',
            'fecha',
            'venta',
            'monto',
            'monto_pagado',
            'adeudo_actual',
            'fecha_vencimiento',
            'estado',
            'is_pagado',
            'referencia',
            'ha_vencido',
            
        ]



class CreditoClienteListSerializer(serializers.ModelSerializer):
    """
    Serializer completo para detalle de créditos con historial de pagos
    """
    cliente_codigo = serializers.CharField(source='cliente.codigo', read_only=True)
    cliente_nombre = serializers.CharField(source='cliente.get_full_name', read_only=True)
    adeudo_actual = serializers.SerializerMethodField()
    #estado_display = serializers.SerializerMethodField()
    dias_para_vencimiento = serializers.SerializerMethodField()
    historial_pagos = PagosCreditoMiniSerializer(many=True, read_only=True, source='pagos') 
    
    class Meta:
        model = CreditoCliente
        fields = [
            'id',
            'cliente',
            'cliente_codigo',
            'cliente_nombre',
            'fecha',
            'monto',
            'monto_pagado',
            'adeudo_actual',
            'fecha_vencimiento',
            'dias_para_vencimiento',
            'estado',
            'venta',
            'is_pagado',
            'ha_vencido',
            'referencia',
            'observaciones',
            'historial_pagos'
        ]
    
    def get_adeudo_actual(self, obj):
        """Calcular adeudo actual"""
        return obj.adeudo_actual()
    
    #def get_estado_display(self, obj):
    #    """Mostrar estado descriptivo"""
    #    return obj.estado
    #
    def get_dias_para_vencimiento(self, obj):
        """Calcular días para vencimiento"""
        if not obj.fecha_vencimiento or obj.is_pagado:
            return None
        return (obj.fecha_vencimiento - timezone.now().date()).days
    
    #def get_historial_pagos(self, obj):
    #    """Obtener historial completo de pagos"""
    #    pagos = obj.pagos.all().order_by('-created_at')
    #    return {
    #        'total_pagos': pagos.count(),
    #        'monto_total_pagado': float(obj.monto_pagado),
    #        'pagos': PagosCreditoSerializer(pagos, many=True).data
    #    }


# ============================================
# Serializers para Respuestas de Estadísticas
# ============================================

class ClienteInfoSerializer(serializers.Serializer):
    """Información básica del cliente"""
    id = serializers.IntegerField()
    codigo = serializers.CharField()
    nombre = serializers.CharField()


class EstadisticasCreditoClienteSerializer(serializers.Serializer):
    """Estadísticas de créditos de un cliente"""
    total_creditos = serializers.IntegerField()
    total_dispersado = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_pagado = serializers.DecimalField(max_digits=12, decimal_places=2)
    adeudo_total = serializers.DecimalField(max_digits=12, decimal_places=2)
    creditos_activos = serializers.IntegerField()
    creditos_liquidados = serializers.IntegerField()
    creditos_vencidos = serializers.IntegerField()
    promedio_credito = serializers.DecimalField(max_digits=12, decimal_places=2)


class CreditosPaginadosSerializer(serializers.Serializer):
    """Listado paginado de créditos"""
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True, required=False)
    previous = serializers.CharField(allow_null=True, required=False)
    results = CreditoClienteListSerializer(many=True)


class EstadisticasClienteResponseSerializer(serializers.Serializer):
    """
    Serializer para la respuesta completa de estadísticas por cliente
    """
    cliente = ClienteInfoSerializer()
    estadisticas = EstadisticasCreditoClienteSerializer()
    creditos = CreditosPaginadosSerializer()
