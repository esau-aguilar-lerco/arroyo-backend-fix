from rest_framework import serializers
from django.db import transaction
from decimal import Decimal

# Models
from apps.erp.models import  CajaTransaccion, PagosVenta, Venta
from apps.contabilidad.models import MetodoPago

# Serializers base
from apps.base.serializer import BaseSerializer, SerializerRelatedField
#from apps.contabilidad.serializers.metodoPagoSerializaer import MetodoPagoMiniSerializer


class MetodoPagoCajaAperturaSerializer(serializers.Serializer):
    """
    Serializer para cada método de pago en una transacción de caja
    """
    metodo_pago = SerializerRelatedField(
        queryset=MetodoPago.objects.all(),
        help_text="ID del método de pago o dic {id: <id>}",
        required=True
    )
    monto = serializers.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        help_text="Monto asignado al método de pago", 
        required=True
    )
    referencia = serializers.CharField(
        max_length=100, 
        help_text="Referencia del pago (número de transferencia, cheque, etc.)", 
        required=False, 
        allow_blank=True,
        allow_null=True
    )
    
    def validate_monto(self, value):
        """Validar que el monto sea positivo"""
        if value <= 0:
            raise serializers.ValidationError("El monto debe ser mayor a cero.")
        return value
    


class MovimientoCajaVentaSerializer(serializers.Serializer):
    """
    Serializer para registrar pagos de una venta en la caja
    
    Este serializer:
    1. Valida que el usuario tenga una caja abierta
    2. Valida que el total de pagos coincida con el total de la venta (o sea un abono)
    3. Crea los registros en CajaTransaccion
    4. Crea los registros en PagosVenta
    5. Actualiza el total_pagado de la venta
    """
    pagos = MetodoPagoCajaAperturaSerializer(
        many=True, 
        help_text="Lista de métodos de pago y montos asociados al movimiento", 
        required=False
    )
    venta = SerializerRelatedField(
        queryset=Venta.objects.filter(status_model=Venta.STATUS_MODEL_ACTIVE),
        help_text="ID de la venta o dic {id: <id>}",
        required=True
    )
    pagar_con_credito = serializers.BooleanField(
        help_text="Indica si se debe usar crédito del cliente para este pago",
        required=False,
        default=False
    )
    pago_credito = serializers.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        help_text="Monto a pagar con crédito del cliente (si aplica)", 
        required=False,
        default=0,
        allow_null=True
    )
    
    
    
    # Campos de solo lectura (respuesta)
    caja_apertura_id = serializers.IntegerField(read_only=True)
    cajero = serializers.SerializerMethodField(read_only=True)
    total_pagos = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    nuevo_saldo = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    
    def get_cajero(self, obj):
        """Obtener nombre del cajero"""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            return request.user.full_name()
        return ''
    
    #def validate_pagos(self, value):
    #    """Validar que haya al menos un método de pago"""
    #    if not value or len(value) == 0:
    #        raise serializers.ValidationError("Debe proporcionar al menos un método de pago.")
    #    return value
    
    def validate(self, data):
        """
        Validaciones generales:
        1. Usuario tiene caja abierta
        2. Total de pagos no excede el adeudo
        3. La venta no está cancelada
        """
        request = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            raise serializers.ValidationError("No se pudo identificar al usuario.")
        
        usuario = request.user
        venta = data.get('venta')
        pagos = data.get('pagos', [])
        pago_con_credito = data.get('pagar_con_credito', False)
        pago_credito = data.get('pago_credito', Decimal('0.00'))
        #print(pago_con_credito, pago_credito)
        if venta.ya_terminada:
            raise serializers.ValidationError({
                'venta': 'No se pueden registrar pagos en una venta ya terminada.',
                'error_code': 'VENTA_TERMINADA'
            })
            
        
            
        cliente = venta.cliente
        if pago_con_credito and  not cliente.puede_pagar_credito(pago_credito) :
            raise serializers.ValidationError({
                'cliente': f'El cliente {cliente.nombre} no tiene crédito disponible para pagar.',
                'error_code': 'CREDITO_INDISPONIBLE'
            })
        if pago_con_credito:
            metodo_credito = MetodoPago.objects.filter(is_credito=True).first()
            pagos.append({
                'metodo_pago': metodo_credito,
                'monto': pago_credito,
                'referencia': 'Pago con crédito'
            })
        
        #  Validar que el usuario tenga una caja abierta
        caja_apertura = usuario.get_mi_caja()
        
        if not caja_apertura:
            raise serializers.ValidationError({
                'detail': f'El usuario {usuario.full_name()} no tiene una caja abierta.',
                'error_code': 'SIN_CAJA_ABIERTA'
            })
        
        #  Validar que la venta no esté cancelada
        if venta.fase == Venta.FASE_CANCELADA:
            raise serializers.ValidationError({
                'venta': 'No se pueden registrar pagos en una venta cancelada.',
                'error_code': 'VENTA_CANCELADA'
            })
        
        #  Calcular total de pagos
        total_pagos = sum(Decimal(str(pago['monto'])) for pago in pagos)
        
        #  Validar que no se exceda el adeudo
        adeudo_actual = Decimal(str(venta.adeudo()))
        #print("Adeudo actual:", type(adeudo_actual), adeudo_actual)
        #print("Total pagos:", type(total_pagos), total_pagos)

        #obtner el cambio 
        cambio =   max(float(total_pagos) - float(adeudo_actual), 0)
        
        #if float(total_pagos) > float(adeudo_actual):
        #    raise serializers.ValidationError({
        #        'pagos': f'El total de pagos (${total_pagos}) excede el adeudo de la venta (${adeudo_actual}).',
        #        'error_code': 'EXCEDE_ADEUDO',
        #        'adeudo': str(adeudo_actual),
        #        'total_pagos': str(total_pagos)
        #    })
        
        # Agregar datos calculados al contexto
        data['_cambio'] = cambio
        data['_caja_apertura'] = caja_apertura
        data['_total_pagos'] = total_pagos
        data['_usuario'] = usuario
        
        return data
    
    @transaction.atomic
    def create(self, validated_data):
        """
        Crear las transacciones de caja y los pagos de venta
        """
        venta = validated_data['venta']
        pagos_data = validated_data['pagos']
        caja_apertura = validated_data['_caja_apertura']
        total_pagos = validated_data['_total_pagos']
        usuario = validated_data['_usuario']
        pagar_con_credito = validated_data.get('pagar_con_credito', False)
        pago_credito = validated_data.get('pago_credito', Decimal('0.00'))
        cambio = validated_data.get('_cambio', Decimal('0.00'))
        
        
        pagos_creados = []
        transacciones_creadas = []
        
        try:
            

            for pago_data in pagos_data:
                metodo_pago = pago_data['metodo_pago']
                monto = Decimal(str(pago_data['monto']))
                #print("METODO PAGO:", metodo_pago.nombre, "MONTO:", cambio)
                referencia = pago_data.get('referencia', '').strip()
                if metodo_pago.nombre.upper() == 'EFECTIVO' and cambio > 0:
                    monto = monto - Decimal(str(cambio))
                    
                    transaccion = CajaTransaccion.objects.create(
                    caja_apertura=caja_apertura,
                    tipo=CajaTransaccion.TIPO_SALIDA,
                    monto=cambio,
                    metodo_pago=metodo_pago,
                    descripcion=f"SALIDA CAMBIO EN EFECTIVO POR {venta.codigo}",
                    created_by=usuario,
                    referencia=referencia or None
                    #updated_by=usuario
                )
                    
                    
                
                #  Crear transacción en CajaTransaccion
                transaccion = CajaTransaccion.objects.create(
                    caja_apertura=caja_apertura,
                    tipo=CajaTransaccion.TIPO_ENTRADA,
                    monto=monto + Decimal(str(cambio)),
                    metodo_pago=metodo_pago,
                    descripcion=f"Pago de venta {venta.codigo} - {metodo_pago.nombre}",
                    created_by=usuario,
                    referencia=referencia or None
                    #updated_by=usuario
                )
                transacciones_creadas.append(transaccion)
                
                # Crear registro en PagosVenta
                pago_venta = PagosVenta.objects.create(
                    venta=venta,
                    monto=monto,
                    metodo_pago=metodo_pago,
                    referencia=referencia or None,
                    created_by=usuario,
                    #updated_by=usuario
                )
                pagos_creados.append(pago_venta)
                
            if pagar_con_credito and pago_credito > 0:
                from apps.credito.models import CreditoCliente
                cliente = venta.cliente
                model_credito = CreditoCliente(cliente=cliente,
                                               monto=pago_credito,
                                               venta=venta,
                                               referencia=f'VENTA-{venta.id}',
                                               created_by=usuario)
                model_credito.save()
                
            
            #  Actualizar total_pagado de la venta
            venta.total_pagado = Decimal(str(venta.total_pagado)) + total_pagos
            venta.cambio = Decimal(str(cambio))
            #venta.ya_terminada = True
            #  Si ya no hay adeudo, marcar como terminada
            #if float(venta.adeudo()) <= 0.0:
            #    venta.fase = Venta.FASE_TERMINADA
            
            venta.save()
            
            # Retornar datos para la respuesta
            return {
                'venta': venta,
                'pagos': pagos_creados,
                'transacciones': transacciones_creadas,
                'caja_apertura_id': caja_apertura.id,
                'cajero': usuario,
                'total_pagos': total_pagos,
                'nuevo_saldo': venta.total_pagado
            }
            
        except Exception as e:
            # Si hay error, la transacción se revierte automáticamente
            raise serializers.ValidationError({
                'detail': f'Error al procesar el pago: {str(e)}',
                'error_code': 'ERROR_PROCESAMIENTO'
            })
            
    
class SalidaCajaGastoSerializer(serializers.Serializer):
    """
    Serializer para registrar salidas/gastos de caja
    
    Este serializer:
    1. Valida que el usuario tenga una caja abierta
    2. Valida que haya suficiente saldo en efectivo (opcional)
    3. Crea el registro en CajaTransaccion con tipo SALIDA o GASTO
    """
    
    monto = serializers.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        help_text="Monto de la salida/gasto", 
        required=True
    )
    tipo = serializers.ChoiceField(
        choices=[
            (CajaTransaccion.TIPO_GASTO, 'GASTO'),
            (CajaTransaccion.TIPO_SALIDA, 'SALIDA')
        ],
        default=CajaTransaccion.TIPO_SALIDA,
        help_text="Tipo de transacción: GASTO (requiere gasto_tipo) o SALIDA (genérica)",
        required=False
    )
    gasto_tipo = serializers.ChoiceField(
        choices=CajaTransaccion.GASTO_TIPO_CHOICES,
        help_text="Tipo de gasto específico (obligatorio si tipo=GASTO)",
        required=False,
        allow_null=True,
        allow_blank=True
    )
    descripcion = serializers.CharField(
        max_length=255,
        help_text="Descripción de la salida/gasto",
        required=False,
        allow_blank=True,
        allow_null=True
    )
    referencia = serializers.CharField(
        max_length=100,
        help_text="Referencia o número de comprobante",
        required=False,
        allow_blank=True,
        allow_null=True
    )
    metodo_pago = SerializerRelatedField(
        queryset=MetodoPago.objects.all(),
        help_text="Método de pago (ID o {id: <id>}). Por defecto se usa EFECTIVO",
        required=False,
        allow_null=True
    )
    
    def validate_monto(self, value):
        """Validar que el monto sea positivo"""
        if value <= 0:
            raise serializers.ValidationError("El monto debe ser mayor a cero.")
        return value
    
    def validate(self, data):
        """
        Validaciones generales:
        1. Usuario tiene caja abierta
        2. Si tipo=GASTO, debe tener gasto_tipo
        3. Validar que hay suficiente efectivo en caja (opcional)
        """
        request = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            raise serializers.ValidationError("No se pudo identificar al usuario.")
        
        usuario = request.user
        
        # Validar que el usuario tenga una caja abierta
        caja_apertura = usuario.get_mi_caja()

        
        if not caja_apertura:
            raise serializers.ValidationError({
                'detail': f'El usuario {usuario.full_name()} no tiene una caja abierta.',
                'error_code': 'SIN_CAJA_ABIERTA'
            })
        
        # Validar que si tipo=GASTO, debe tener gasto_tipo
        tipo = data.get('tipo')
        gasto_tipo = data.get('gasto_tipo')
        
        if tipo == CajaTransaccion.TIPO_GASTO:
            if not gasto_tipo:
                raise serializers.ValidationError({
                    'gasto_tipo': 'El campo gasto_tipo es obligatorio cuando el tipo de transacción es GASTO.',
                    'error_code': 'GASTO_TIPO_OBLIGATORIO'
                })
        
        # Agregar datos calculados al contexto
        data['_caja_apertura'] = caja_apertura
        data['_usuario'] = usuario
        
        return data    
    
    @transaction.atomic
    def create(self, validated_data):
        """
        Crear la transacción de salida/gasto en caja
        """
        caja_apertura = validated_data.pop('_caja_apertura')
        usuario = validated_data.pop('_usuario')
        
        # Obtener o usar método de pago por defecto (EFECTIVO)
        metodo_pago = validated_data.pop('metodo_pago', None)
        if not metodo_pago:
            metodo_pago = MetodoPago.objects.filter(nombre__iexact='EFECTIVO').first()
            if not metodo_pago:
                raise serializers.ValidationError({
                    'detail': 'No se encontró el método de pago EFECTIVO.',
                    'error_code': 'METODO_PAGO_NO_ENCONTRADO'
                })
        
        try:
            # Crear transacción en CajaTransaccion
            transaccion = CajaTransaccion.objects.create(
                caja_apertura=caja_apertura,
                tipo=validated_data['tipo'],
                monto=validated_data['monto'],
                metodo_pago=metodo_pago,
                gasto_tipo=validated_data.get('gasto_tipo', ''),
                descripcion=validated_data.get('descripcion', ''),
                referencia=validated_data.get('referencia', ''),
                created_by=usuario
            )
            
            return transaccion
            
        except Exception as e:
            # Si hay error, la transacción se revierte automáticamente
            raise serializers.ValidationError({
                'detail': f'Error al registrar la salida/gasto: {str(e)}',
                'error_code': 'ERROR_PROCESAMIENTO'
            })
    
class MovimientoCajaTransaccionSerializer(BaseSerializer):
    """
    Serializer de respuesta para el registro de pagos en caja
    """
    
    metodo_name = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = CajaTransaccion
        fields = ['referencia', 'metodo_pago', 'monto', 'created_at', 'tipo',
                  'descripcion', 'id', 'caja_apertura', 'metodo_name','gasto_tipo']
        read_only_fields = fields
        
    def get_metodo_name(self, obj):
        """Obtener nombre del método de pago"""
        if obj.metodo_pago:
            return obj.metodo_pago.nombre
        return ''