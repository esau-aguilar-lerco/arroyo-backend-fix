from rest_framework import serializers
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction

from apps.credito.models import CreditoProveedor, PagosCreditoProveedor
from apps.base.serializer import FlexiblePKRelatedField
from apps.contabilidad.models import MetodoPago
from apps.erp.serializers.caja.movimientos import MetodoPagoCajaAperturaSerializer
from apps.erp.models import CajaApertura, CajaTransaccion, Proveedor


class RoundedDecimalField(serializers.DecimalField):
    """
    Campo Decimal que redondea automáticamente a 4 decimales antes de validar
    """
    def to_internal_value(self, data):
        # Convertir a Decimal y redondear a 4 decimales
        if data is None:
            return None
        try:
            decimal_value = Decimal(str(data))
            rounded_value = decimal_value.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
            return super().to_internal_value(rounded_value)
        except Exception as e:
            self.fail('invalid', value=data)


class PagosCreditoProveedorSerializer(serializers.ModelSerializer):
    """Serializer para listar pagos de crédito de proveedor"""
    metodo_pago = serializers.SerializerMethodField()
    proveedor = serializers.SerializerMethodField()
    credito_id = serializers.IntegerField(source='credito_proveedor.id', read_only=True)
    created_by_nombre = serializers.CharField(source='created_by.get_full_name', read_only=True)
    fecha_pago = serializers.DateTimeField(source='created_at', format='%Y-%m-%d %H:%M:%S', read_only=True)
    
    class Meta:
        model = PagosCreditoProveedor
        fields = [
            'id',
            'credito_id',
            'proveedor',
            'monto',
            'metodo_pago',
            'fecha_pago',
            'created_by_nombre',
            'token'
        ]
    
    def get_metodo_pago(self, obj):
        if obj.metodo_pago:
            return {
                'id': obj.metodo_pago.id,
                'nombre': obj.metodo_pago.nombre,
                'codigo': obj.metodo_pago.id
            }
        return None
    
    def get_proveedor(self, obj):
        if obj.credito_proveedor and obj.credito_proveedor.proveedor:
            return {
                'id': obj.credito_proveedor.proveedor.id,
                'codigo': obj.credito_proveedor.proveedor.codigo,
                'nombre': obj.credito_proveedor.proveedor.nombre
            }
        return None


class PagoCreditoProveedorCreateSingularSerializer(serializers.Serializer):
    """
    Serializer para crear un pago singular a un crédito de proveedor
    
    Validaciones:
    - El crédito debe existir y no estar liquidado
    - El monto total de pagos no debe exceder el adeudo
    - cantidad_pagar es el monto que se aplicará al crédito
    - Si total de pagos > cantidad_pagar con EFECTIVO, se calcula cambio
    """
    credito = FlexiblePKRelatedField(
        queryset=CreditoProveedor.objects.all(),
        required=True,
        help_text="ID del crédito de proveedor a pagar"
    )
    
    cantidad_pagar = RoundedDecimalField(
        max_digits=20,
        decimal_places=4,
        required=True,
        help_text="Monto total a pagar al crédito (puede ser menor al total de pagos si hay cambio)"
    )
    
    pagos = MetodoPagoCajaAperturaSerializer(many=True, required=True)
    
    def validate_credito(self, value):
        """Validar que el crédito no esté liquidado"""
        if value.is_pagado:
            raise serializers.ValidationError(
                f"El crédito del proveedor {value.proveedor.nombre} ya está liquidado."
            )
        return value
    
    def validate(self, attrs):
        """Validaciones globales"""
        credito = attrs['credito']
        pagos = attrs['pagos']
        cantidad_pagar = attrs['cantidad_pagar']
        
        # Obtener usuario del contexto
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError("No se pudo obtener el usuario autenticado.")
        
        usuario = request.user
        attrs['usuario'] = usuario
        
        # Validar que cantidad_pagar no exceda el adeudo
        adeudo = credito.adeudo_actual()
        if cantidad_pagar > adeudo:
            raise serializers.ValidationError({
                'cantidad_pagar': f"La cantidad a pagar (${cantidad_pagar}) excede el adeudo actual (${adeudo})."
            })
        
        # Validar que cantidad_pagar sea mayor a cero
        if cantidad_pagar <= 0:
            raise serializers.ValidationError({
                'cantidad_pagar': "La cantidad a pagar debe ser mayor a cero."
            })
        
        # Calcular total de pagos
        total_pagos = sum(Decimal(str(pago['monto'])) for pago in pagos)
        
        # Validar que el total de pagos sea suficiente
        if total_pagos < cantidad_pagar:
            raise serializers.ValidationError({
                'pagos': f"El total de los pagos (${total_pagos}) es menor a la cantidad a pagar (${cantidad_pagar})."
            })
        
        # Validar montos individuales
        for idx, pago in enumerate(pagos):
            monto = Decimal(str(pago['monto']))
            if monto <= 0:
                raise serializers.ValidationError({
                    'pagos': f"El pago #{idx + 1} tiene un monto inválido (${monto}). Debe ser mayor a cero."
                })
        
        return attrs
    
    @transaction.atomic
    def create(self, validated_data):
        """
        Crear pagos y actualizar el crédito de proveedor
        
        1. Registra cada pago en PagosCreditoProveedor
        2. NO registra transacciones en caja (pago a proveedor es independiente de caja)
        3. Calcula cambio si total de pagos > cantidad_pagar con EFECTIVO
        4. Actualiza el monto_pagado del crédito con cantidad_pagar
        5. Marca como pagado si se liquidó completamente
        """
        credito = validated_data['credito']
        pagos = validated_data['pagos']
        usuario = validated_data['usuario']
        cantidad_pagar = validated_data['cantidad_pagar']
        
        # Calcular total de los pagos
        total_pagos = sum(Decimal(str(pago['monto'])) for pago in pagos)
        
        # Determinar si hay cambio
        cambio = Decimal('0')
        metodo_efectivo = None
        
        # Buscar si hay pago en EFECTIVO
        for pago in pagos:
            metodo_pago = pago['metodo_pago']
            if metodo_pago.nombre == 'EFECTIVO':
                metodo_efectivo = metodo_pago
                break
        
        # Si el total excede la cantidad a pagar y hay EFECTIVO, calcular cambio
        if total_pagos > cantidad_pagar and metodo_efectivo:
            cambio = total_pagos - cantidad_pagar
        
        # Registrar cada pago (sin ajustar por cambio, se registra el monto completo)
        pagos_registrados = []
        for pago_data in pagos:
            metodo_pago = pago_data['metodo_pago']
            monto_pago = Decimal(str(pago_data['monto']))
            
            # Crear registro de pago
            pago_obj = PagosCreditoProveedor.objects.create(
                credito_proveedor=credito,
                monto=monto_pago,
                metodo_pago=metodo_pago,
                created_by=usuario
            )
            pagos_registrados.append(pago_obj)
        
        # Actualizar el crédito con la cantidad_pagar (no con el total de pagos)
        credito.monto_pagado = Decimal(str(credito.monto_pagado)) + cantidad_pagar
        credito.actualizar_saldo_proveedor_pago(cantidad_pagar)
        credito.save()
        
        # Verificar si se liquidó completamente
        if credito.adeudo_actual() == 0:
            credito.marcar_pagado()
        
        # Retornar información del cambio junto con el crédito
        credito.cambio_calculado = float(cambio) if cambio > 0 else None
        
        return credito


class PagoCreditoProveedorCreateMasivoSerializer(serializers.Serializer):
    """
    Serializer para crear pagos masivos a múltiples créditos de proveedor
    
    Estructura esperada:
    {
        "lista": [
            {
                "credito": 1,
                "pagos": [
                    {"metodo_pago": 1, "monto": 500.00},
                    {"metodo_pago": 2, "monto": 300.00}
                ]
            },
            {
                "credito": 2,
                "pagos": [
                    {"metodo_pago": 1, "monto": 1000.00}
                ]
            }
        ]
    }
    """
    lista = PagoCreditoProveedorCreateSingularSerializer(many=True, required=True)
    
    def validate(self, attrs):
        """Validar que todos los créditos existan y sean válidos"""
        lista = attrs.get('lista', [])
        
        if not lista:
            raise serializers.ValidationError({
                'lista': 'Debe proporcionar al menos un crédito para procesar.'
            })
        
        # Validar que no haya créditos duplicados
        creditos_ids = [item['credito'].id for item in lista]
        if len(creditos_ids) != len(set(creditos_ids)):
            raise serializers.ValidationError({
                'lista': 'Hay créditos duplicados en la lista. Cada crédito debe aparecer solo una vez.'
            })
        
        return attrs
    
    @transaction.atomic
    def create(self, validated_data):
        """
        Procesar pagos masivos
        
        Todos los pagos se procesan en una transacción atómica.
        Si algún pago falla, se revierten todos los cambios.
        NO requiere caja abierta.
        """
        lista = validated_data['lista']
        
        # Obtener usuario del contexto
        request = self.context.get('request')
        usuario = request.user if request else None
        
        # Procesar cada crédito
        creditos_procesados = []
        total_pagos = 0
        monto_total = Decimal('0')
        errores = []
        
        for idx, item_data in enumerate(lista):
            try:
                # Crear el serializer para el pago singular
                serializer = PagoCreditoProveedorCreateSingularSerializer(
                    data=item_data,
                    context=self.context
                )
                
                if serializer.is_valid(raise_exception=True):
                    credito = serializer.save()
                    
                    # Calcular información del crédito procesado
                    pagos_count = len(item_data['pagos'])
                    cantidad_pagar = Decimal(str(item_data['cantidad_pagar']))
                    
                    creditos_procesados.append({
                        'credito_id': credito.id,
                        'proveedor': credito.proveedor.nombre,
                        'monto_pagado': float(cantidad_pagar),
                        'adeudo_restante': float(credito.adeudo_actual()),
                        'pagos_registrados': pagos_count,
                        'cambio': getattr(credito, 'cambio_calculado', None)
                    })
                    
                    total_pagos += pagos_count
                    monto_total += cantidad_pagar
            
            except serializers.ValidationError as e:
                # Acumular errores
                errores.append({
                    'indice': idx,
                    'credito_id': item_data.get('credito'),
                    'error': str(e.detail)
                })
            except Exception as e:
                errores.append({
                    'indice': idx,
                    'credito_id': item_data.get('credito'),
                    'error': str(e)
                })
        
        # Si hay errores, lanzar excepción (se revertirá la transacción)
        if errores:
            raise serializers.ValidationError({
                'errores': errores,
                'mensaje': f'Se encontraron {len(errores)} errores al procesar los pagos.'
            })
        
        # Retornar resumen de procesamiento
        return {
            'creditos_procesados': creditos_procesados,
            'total_creditos': len(creditos_procesados),
            'total_pagos': total_pagos,
            'monto_total': float(monto_total),
            'mensaje': f'Se procesaron exitosamente {len(creditos_procesados)} créditos con {total_pagos} pagos.'
        }


class CreditoProveedorSerializer(serializers.ModelSerializer):
    """Serializer completo para crédito de proveedor con historial de pagos"""
    proveedor = serializers.SerializerMethodField()
    pagos = PagosCreditoProveedorSerializer(source='pagos_proveedor', many=True, read_only=True)
    adeudo = serializers.SerializerMethodField()
    ha_vencido = serializers.BooleanField(read_only=True)
    dias_vencido = serializers.SerializerMethodField()
    compra_id = serializers.IntegerField(source='compra.id', read_only=True, allow_null=True)
    created_by_nombre = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = CreditoProveedor
        fields = [
            'id',
            'proveedor',
            'fecha',
            'monto',
            'monto_pagado',
            'adeudo',
            'dias_plazo',
            'fecha_vencimiento',
            'is_pagado',
            'fecha_pago',
            'ha_vencido',
            'dias_vencido',
            'estado',
            'observaciones',
            'referencia',
            'compra_id',
            'pagos',
            'created_by_nombre',
            'created_at',
            'updated_at'
        ]
    
    def get_proveedor(self, obj):
        return {
            'id': obj.proveedor.id,
            'codigo': obj.proveedor.codigo,
            'nombre': obj.proveedor.nombre
        }
    
    def get_adeudo(self, obj):
        return float(obj.adeudo_actual())
    
    def get_dias_vencido(self, obj):
        """Calcular días de vencimiento (positivo si está vencido)"""
        from django.utils import timezone
        
        if obj.is_pagado:
            return 0
        
        if not obj.fecha_vencimiento:
            return 0
        
        hoy = timezone.now().date()
        delta = (hoy - obj.fecha_vencimiento).days
        
        return delta if delta > 0 else 0


class CreditoProveedorMiniSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listados de créditos de proveedor"""
    proveedor = serializers.SerializerMethodField()
    adeudo = serializers.SerializerMethodField()
    ha_vencido = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = CreditoProveedor
        fields = [
            'id',
            'proveedor',
            'fecha',
            'monto',
            'monto_pagado',
            'adeudo',
            'fecha_vencimiento',
            'is_pagado',
            'ha_vencido',
            'estado',
            'compra'
        ]
    
    def get_proveedor(self, obj):
        return {
            'id': obj.proveedor.id,
            'codigo': obj.proveedor.codigo,
            'nombre': obj.proveedor.nombre
        }
    
    def get_adeudo(self, obj):
        return float(obj.adeudo_actual())


class CreditoProveedorListSerializer(serializers.ModelSerializer):
    """Serializer para listados con datos adicionales pero sin pagos"""
    proveedor = serializers.SerializerMethodField()
    adeudo = serializers.SerializerMethodField()
    ha_vencido = serializers.BooleanField(read_only=True)
    dias_vencido = serializers.SerializerMethodField()
    total_pagos = serializers.SerializerMethodField()
    compra_id = serializers.IntegerField(source='compra.id', read_only=True, allow_null=True)
    
    class Meta:
        model = CreditoProveedor
        fields = [
            'id',
            'proveedor',
            'fecha',
            'monto',
            'monto_pagado',
            'adeudo',
            'dias_plazo',
            'fecha_vencimiento',
            'is_pagado',
            'fecha_pago',
            'ha_vencido',
            'dias_vencido',
            'estado',
            'total_pagos',
            'compra_id',
            'created_at'
        ]
    
    def get_proveedor(self, obj):
        return {
            'id': obj.proveedor.id,
            'codigo': obj.proveedor.codigo,
            'nombre': obj.proveedor.nombre
        }
    
    def get_adeudo(self, obj):
        return float(obj.adeudo_actual())
    
    def get_dias_vencido(self, obj):
        """Calcular días de vencimiento"""
        from django.utils import timezone
        
        if obj.is_pagado:
            return 0
        
        if not obj.fecha_vencimiento:
            return 0
        
        hoy = timezone.now().date()
        delta = (hoy - obj.fecha_vencimiento).days
        
        return delta if delta > 0 else 0
    
    def get_total_pagos(self, obj):
        """Cantidad de pagos realizados"""
        return obj.pagos_proveedor.count()


class EstadisticasCreditoProveedorSerializer(serializers.Serializer):
    """Serializer para estadísticas de créditos de proveedor"""
    total_creditos = serializers.IntegerField()
    total_dispersado = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_pagado = serializers.DecimalField(max_digits=12, decimal_places=2)
    adeudo_total = serializers.DecimalField(max_digits=12, decimal_places=2)
    creditos_activos = serializers.IntegerField()
    creditos_liquidados = serializers.IntegerField()
    creditos_vencidos = serializers.IntegerField()
    promedio_credito = serializers.DecimalField(max_digits=12, decimal_places=2)
