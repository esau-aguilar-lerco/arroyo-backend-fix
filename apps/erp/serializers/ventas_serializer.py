from rest_framework import serializers
from decimal import Decimal


from apps.erp.models import Venta, VentaDetalle, VentaDetalleLote, Cliente, Almacen, Rutas, PagosVenta
from apps.contabilidad.models import MetodoPago

from apps.usuarios.serializers.usuarios import UsuarioMiniSerializer
from apps.erp.serializers.cliente_serializer import ClienteMiniSerializer
from apps.erp.serializers.productos_serializer import ProductoMiniSerializer
from apps.erp.serializers.rutas_serializer import RutasMiniSerializer
from apps.base.serializer import BaseSerializer, SerializerRelatedField
from apps.contabilidad.serializers.metodoPagoSerializaer import MetodoPagoMiniSerializer

from apps.base.models import BaseModel
from apps.contabilidad.models import CondicionPago
from apps.usuarios.models import Usuario

from apps.erp.helpers.ventas import main_crearmovomientos_venta



"""
==============================================
    SERIALIZERS PARA PAGOS DE COMPRA
==============================================
"""
class PagosVentaSerializer(BaseSerializer):
    """
    Serializer para los pagos de una compra
    """
    metodo_pago = SerializerRelatedField(
        queryset=MetodoPago.objects.all(),
        required=True,
        #allow_null=True,
        help_text="ID del método de pago (puede ser un entero o {\"id\": <pk>})"
    )
    metodo_pago_obj = MetodoPagoMiniSerializer(read_only=True, source='metodo_pago')
    
    monto = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0.01, required=True)


    #fecha_pagar = serializers.DateField(
    #    required=False,
    #    allow_null=True,
    #    default=None,
    #    help_text="Fecha en que se realizará el pago, si el tipo de pago es crédito"
    #)
    referencia = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        help_text="Referencia del pago (opcional)"
    )   

    class Meta:
        model = PagosVenta
        fields = [
            'id', 'monto', 'metodo_pago', 'metodo_pago_obj',
            'created_at', 'updated_at', 'created_by', 'updated_by', 'referencia'
        ]
        read_only_fields = ('id', 'created_at', 'updated_at', 'created_by', 'updated_by')

    def validate_monto(self, value):
        """
        Validar que el monto sea positivo
        """
        if value <= 0:
            raise serializers.ValidationError("El monto debe ser mayor a cero.")
        return value

    #def validate_fecha_pagar(self, value):
    #    """
    #    Validar que la fecha de pago no sea en el pasado
    #    """
    #    from datetime import date
#
    #    if value and value < date.today():
    #        raise serializers.ValidationError("La fecha de pago no puede ser en el pasado.")
    #    return value

    #def validate(self, data):
    #    """
    #    Validación completa: fecha_pagar requerida si método de pago es crédito
    #    """
    #    metodo_pago = data.get('metodo_pago')
    #    fecha_pagar = data.get('fecha_pagar')
    #    
    #    # ✅ Validar que fecha_pagar sea requerida si el método de pago es crédito
    #    if metodo_pago and metodo_pago.is_credito and not fecha_pagar:
    #        raise serializers.ValidationError({
    #            'fecha_pagar': 'La fecha de pago es requerida cuando el método de pago es crédito.'
    #        })
    #    
    #    # ✅ Si el método NO es crédito, permitir fecha_pagar como null/None
    #    if metodo_pago and not metodo_pago.is_credito:
    #        # Limpiar fecha_pagar si el método no es crédito
    #        data['fecha_pagar'] = None
    #    
    #    return data



    def create(self, validated_data):
        """
        Crear pago de compra asignando el usuario creador
        """
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            validated_data['created_by_id'] = request.user.id
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """
        Actualizar pago de compra asignando el usuario actual
        """
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            validated_data['updated_by_id'] = request.user.id
        return super().update(instance, validated_data)



"""
==============================================
    SERIALIZER PARA DETALLE DE VENTA
==============================================
"""
class VentaDetalleSerializer(serializers.ModelSerializer):
    """
    Serializer para detalles de venta con control de lotes
    """
    producto_obj = ProductoMiniSerializer(read_only=True, source='producto')
    
    
    # Campos calculados
    #cantidad_pendiente_asignar = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    #lotes_completos = serializers.BooleanField(read_only=True)
    #costo_promedio_lotes = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = VentaDetalle
        fields = [
            'id', 'producto', 'producto_obj', 'cantidad', 'precio_unitario', 'subtotal',
             
        ]
        read_only_fields = ('id', 'subtotal')

    def validate(self, data):
        """
        Validaciones del detalle
        """
        cantidad = data.get('cantidad', 0)
        precio = data.get('precio_unitario', 0)
        
        if cantidad <= 0:
            raise serializers.ValidationError("La cantidad debe ser mayor a 0.")
        
        if precio < 0:
            raise serializers.ValidationError("El precio unitario no puede ser negativo.")
        
        return data


"""
==============================================
    SERIALIZER MINI PARA VENTAS
==============================================
"""
class VentaMiniSerializer(BaseSerializer):
    """
    Serializer mini para listar ventas básicas
    """
    cliente_nombre = serializers.CharField(source='cliente.get_full_name', read_only=True)
    ruta_nombre = serializers.SerializerMethodField()
    total_detalles = serializers.IntegerField(source='detalles.count', read_only=True)
    origen = serializers.CharField(source='almacen.nombre', read_only=True)
    is_terminada = serializers.BooleanField(read_only=True)

    class Meta:
        model = Venta
        fields = (
            'id', 'codigo', 'cliente_nombre', 'ruta_nombre', 'fase', 
            'total', 'total_detalles', 'created_at','created_by',
            'updated_at', 'updated_by','origen','was_preventa','is_terminada'
        )
        read_only_fields = (
            'id', 'codigo', 'cliente_nombre', 'ruta_nombre', 'total_detalles', 'created_at','origen','was_preventa','is_terminada'
        )

    def get_ruta_nombre(self, obj):
        """
        Retorna el nombre de la ruta o None si no existe
        """
        return obj.ruta.nombre if obj.ruta else ""


"""
==============================================
    SERIALIZER PRINCIPAL PARA VENTAS
==============================================
"""
class VentaSerializer(BaseSerializer):
    """
    Serializer completo para ventas con detalles y control de lotes
    """
    vendedor = SerializerRelatedField(
        queryset=Usuario.objects.filter(
            is_active=True
        ),
        required=False,
        allow_null=True,
        help_text=f"ID del vendedor - OBLIGATORIO cuando fase es {Venta.FASE_VENTA_COMANDA} (puede ser un entero o {{\"id\": <pk>}})"
    )
    cliente = SerializerRelatedField(
        queryset=Cliente.objects.filter(status_model=BaseModel.STATUS_MODEL_ACTIVE),
        required=True,
        help_text="ID del cliente (puede ser un entero o {\"id\": <pk>})"
    )
    cliente_obj = ClienteMiniSerializer(read_only=True, source='cliente')
    
    almacen = SerializerRelatedField(
        queryset=Almacen.objects.filter(status_model=BaseModel.STATUS_MODEL_ACTIVE),
        required=False,
        allow_null=True,
        help_text=f"ID del almacén donde se afectará el inventario (puede ser un entero o (\"id\": <pk>)). Obligatorio para fases {Venta.FASE_VENTA_COMANDA}"
    )
    almacen_obj = serializers.SerializerMethodField()
    
    ruta = SerializerRelatedField(
        queryset=Rutas.objects.filter(status_model=BaseModel.STATUS_MODEL_ACTIVE),
        required=False,
        allow_null=True,
        help_text="ID de la ruta (requerido para preventa, puede ser un entero o {\"id\": <pk>})"
    )
    ruta_obj = RutasMiniSerializer(read_only=True, source='ruta')
    
    # Detalles anidados
    detalles = VentaDetalleSerializer(many=True, required=False)

    #PARA PAGOS
    condicion_pago = serializers.ChoiceField(
        choices=CondicionPago.CONDICIONES_LIST,
        required=False,
        help_text="Condición de pago"
    )# Los detalles se manejan por separado
    pagos = PagosVentaSerializer(many=True, required=False, allow_null=True)

    
    # Campos calculados
    total_calculado = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_detalles = serializers.IntegerField(source='detalles.count', read_only=True)
    vendedor_nombre = serializers.CharField(source='vendedor.full_name', read_only=True)
    adeudo_total = serializers.SerializerMethodField(read_only=True)
    is_terminada = serializers.BooleanField(source='ya_terminada', read_only=True)
    
    class Meta:
        model = Venta
        fields = [
            'id', 'codigo', 'cliente', 'cliente_obj', 'almacen', 'almacen_obj',
            'ruta', 'ruta_obj', 'fase', 'total', 'total_calculado', 'detalles', 
            'total_detalles', 'created_at', 'updated_at', 'status_model','pagos','condicion_pago',
            'is_entregado', 'vendedor','vendedor_nombre','adeudo_total','is_terminada','cambio'
        ]
        read_only_fields = (
            'id', 'codigo', 'total_calculado', 'total_detalles', 
            'created_at', 'updated_at','status_model','total','is_entregado','vendedor','vendedor_nombre','adeudo_total','is_terminada','cambio'
        )

    def get_adeudo_total(self, obj):
        return obj.adeudo()
    def get_almacen_obj(self, obj):
        """
        Retorna información del almacén donde se afecta el inventario
        """
        if obj.almacen:
            from apps.erp.serializers.almacen_serializer import AlmacenMiniSerializer
            return AlmacenMiniSerializer(obj.almacen).data
        return None

    
    def validate_pagos(self, pagos):
        """
        Validar que no se repita más de dos veces el mismo método de pago
        """
        #print("PAGOS RECIBIDOS:", pagos)
        #if self.instance.condicion_pago == CondicionPago.CONDICION_CONTADO and  len(pagos) == 0:
        #    raise serializers.ValidationError(
        #        "La condición de pago es contado, se requieren métodos de pago."
        #    )
        if pagos:
            # Contar métodos de pago por ID
            #metodos_count = {}
            lista_pagos_id = []
            for pago in pagos:
                metodo_id = pago['metodo_pago'].id

                # Validar que no exceda 2 veces el mismo método
                if metodo_id in lista_pagos_id:
                    metodo_nombre = pago['metodo_pago'].nombre
                    raise serializers.ValidationError(
                        f"El método de pago '{metodo_nombre}' no puede aparecer más de 2 veces."
                    )
                lista_pagos_id.append(metodo_id)
                
        
        return pagos
    
    def validate(self, data):
        """
        Validaciones de la venta
        """
        fase = data.get('fase')
        ruta = data.get('ruta')
        almacen = data.get('almacen')
        pagos = data.get('pagos', [])
        if fase == Venta.FASE_VENTA_COMANDA:
            vendedor = data.get('vendedor')
            if not vendedor:
                raise serializers.ValidationError({
                    'vendedor': f'El vendedor es obligatorio cuando la fase es {Venta.FASE_VENTA_COMANDA}.'
                })
        # El almacén es obligatorio para preventa
        if not almacen and fase in [Venta.FASE_PRE_VENTA]:
            raise serializers.ValidationError(
                "Debe especificar el almacén donde se afectará el inventario."
            )
        
        # Si es FASE_PRE_VENTA, la ruta es obligatoria
        if fase == Venta.FASE_PRE_VENTA and not ruta:
            raise serializers.ValidationError({
                'ruta': 'La ruta es obligatoria cuando la fase es PRE VENTA.'
            })
        
        ## Si la fase es EN_PROCESO o TERMINADA, validaciones adicionales
        #if fase in [Venta.FASE_EN_PROCESO, Venta.FASE_TERMINADA]:
        #    # Verificar que el almacén esté activo
        #    if almacen.status_model != BaseModel.STATUS_MODEL_ACTIVE:
        #        raise serializers.ValidationError(
        #            "El almacén debe estar activo para procesar la venta."
        #        )
        
        return data

    def create(self, validated_data):
        """
        Crear venta con detalles y pagos anidados
        """
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            validated_data['created_by_id'] = request.user.id

        detalles_data = validated_data.pop('detalles', [])
        pagos_data = validated_data.pop('pagos', [])  
        vendedor = validated_data.get('vendedor', None)
        if validated_data.get('fase') in [Venta.FASE_VENTA_COMANDA, Venta.FASE_TERMINADA]:
            almacen = request.user.almacen
            if not almacen:
                almacen = vendedor.almacen if vendedor and vendedor.almacen else None
                
            if not almacen:
                almacen = Almacen.objects.filter(id=1).first()
            
            validated_data['almacen'] = almacen
                
            
        #almacen = request.user.almacen if Venta.FASE_VENTA_COMANDA == validated_data.get('fase') and not validated_data.get('almacen') else validated_data.get('almacen')
        #print("ALMACEN ASIGNADO A VENTA:", almacen)
        #print("DETALLES DE VENTA:", request.user)
        # Calcular total inicial
        total_calculado = sum(
            Decimal(str(detalle.get('cantidad', 0))) * Decimal(str(detalle.get('precio_unitario', 0)))
            for detalle in detalles_data
        )
        validated_data['total'] = total_calculado

        # Crear la venta
        venta = Venta.objects.create(**validated_data)
        # Crear detalles
        for detalle_data in detalles_data:
            VentaDetalle.objects.create(venta=venta, **detalle_data)

        if venta.fase in [Venta.FASE_PRE_VENTA, Venta.FASE_VENTA_COMANDA, Venta.FASE_TERMINADA]:
            main_crearmovomientos_venta(venta, detalles_data, user=request.user)
        
        for pago_data in pagos_data:
            PagosVenta.objects.create(venta=venta, created_by_id=request.user.id, **pago_data)
        # 🔑 Recalcular condición de pago según pagos
        total_pagado = sum(
            Decimal(str(p['monto'])) for p in pagos_data
        )

        if total_pagado >= venta.total:
            venta.condicion_pago = CondicionPago.CONDICION_CONTADO
        else:
            venta.condicion_pago = CondicionPago.CONDICION_CREDITO

        venta.save(update_fields=["condicion_pago"])

        return venta

        
       

    def update(self, instance, validated_data):
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            validated_data['updated_by_id'] = request.user.id
        """
        Actualizar venta (sin tocar detalles en este serializer)
        """
        detalles_data = validated_data.pop('detalles', [])
        pagos_data = validated_data.pop('pagos', None)

        
        # Actualizar campos básicos
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

         # Si se proporcionan pagos, reemplazarlos completamente
        if pagos_data is not None:
            #print("PAGOS DATA:", pagos_data)
            # Soft delete de pagos existentes (NO detalles)
            #pass
            instance.pagos.all().delete()

            # Crear nuevos pagos
            for pago_data in pagos_data:
                PagosVenta.objects.create(venta=instance, created_by_id=request.user.id, **pago_data)

        # 🔑 Recalcular condición de pago en updates
        total_pagado = sum(p.monto for p in instance.pagos.all())

        if total_pagado >= instance.total:
            instance.condicion_pago = CondicionPago.CONDICION_CONTADO
        else:
            instance.condicion_pago = CondicionPago.CONDICION_CREDITO

        instance.save(update_fields=["condicion_pago"])
        return instance


"""
==============================================
    SERIALIZER PARA ACTUALIZAR ESTADO
==============================================
"""
class VentaEstadoSerializer(BaseSerializer):
    """
    Serializer específico para actualizar solo la fase de una venta
    """
    class Meta:
        model = Venta
        fields = ('fase',)

    def validate_fase(self, value):
        """
        Validar transiciones de fase válidas
        """
        if self.instance:
            fase_actual = self.instance.fase
            
            # Definir transiciones válidas
            transiciones_validas = {
                Venta.FASE_PRE_VENTA: [Venta.FASE_EN_PROCESO, Venta.FASE_CANCELADA],
                Venta.FASE_EN_PROCESO: [Venta.FASE_TERMINADA, Venta.FASE_CANCELADA],
                Venta.FASE_TERMINADA: [],  # No se puede cambiar desde terminada
                Venta.FASE_CANCELADA: []   # No se puede cambiar desde cancelada
            }
            
            if value not in transiciones_validas.get(fase_actual, []):
                raise serializers.ValidationError(
                    f"No se puede cambiar de {fase_actual} a {value}."
                )
            
            # Validaciones adicionales para TERMINADA
            if value == Venta.FASE_TERMINADA:
                if not self.instance.ruta:
                    raise serializers.ValidationError(
                        "No se puede terminar una venta sin ruta asignada."
                    )
                
                # Verificar que todos los detalles tengan lotes asignados
                for detalle in self.instance.detalles.all():
                    if not detalle.lotes_completos:
                        raise serializers.ValidationError(
                            f"El detalle '{detalle.producto.nombre}' no tiene todos sus lotes asignados. "
                            f"Pendiente: {detalle.cantidad_pendiente_asignar} unidades."
                        )
            
            # Validaciones adicionales para PRE_VENTA
            if value == Venta.FASE_PRE_VENTA:
                if not self.instance.ruta:
                    raise serializers.ValidationError(
                        "La ruta es obligatoria cuando la fase es PRE VENTA."
                    )
        
        return value
