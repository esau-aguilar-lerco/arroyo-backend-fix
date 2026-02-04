from datetime import date
from rest_framework import serializers
from rest_framework.exceptions import ValidationError as DRFValidationError
from decimal import Decimal

# MODELS
from apps.base.models import BaseModel
from apps.usuarios.models import Usuario
from ..models import (OrdenCompra, OrdenCompraDetalle, Proveedor, Producto,Compra, GastosCompra,
                       CompraDetalle, PagosCompra, OrdenCompra, Proveedor, Producto, Almacen)
from apps.contabilidad.models import MetodoPago, CondicionPago

# SERIALIZERS
from apps.base.serializer import BaseSerializer, SerializerRelatedField
from .proveedor_serializer import ProveedorMiniSerializer
from .productos_serializer import ProductoMiniSerializer
from .almacen_serializer import AlmacenMiniSerializer
from decimal import Decimal, InvalidOperation


from apps.usuarios.serializers.usuarios import UsuarioMiniSerializer


class MetodoPagoSerializer(serializers.Serializer):
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
    


"""
==============================================
    SERIALIZERS PARA ORDEN DE COMPRA DETALLE
==============================================
"""
class OrdenCompraDetalleSerializer(BaseSerializer):
    """
    Serializer para los detalles de una orden de compra
    """
    producto = SerializerRelatedField(
        queryset=Producto.objects.filter(status_model=BaseModel.STATUS_MODEL_ACTIVE),
        required=True,
        allow_null=False,
        help_text="ID del producto (solo activos, puede ser un entero o {\"id\": <pk>})"
    )
    producto_obj = ProductoMiniSerializer(read_only=True, source='producto')
    
    cantidad = serializers.DecimalField(max_digits=25, decimal_places=5, min_value=1, required=True)
    #precio_unitario = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=True)
    #subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = OrdenCompraDetalle
        fields = [
            'id', 'producto', 'producto_obj', 'cantidad', 'precio', 
            #'precio_unitario', 'subtotal'
        ]
        read_only_fields = ('id', 'subtotal',)

    def validate(self, data):
        """
        Validar que el producto esté activo
        """
        producto = data.get('producto')
        if producto and producto.status_model != BaseModel.STATUS_MODEL_ACTIVE:
            raise serializers.ValidationError("El producto seleccionado no está activo.")
        return data


"""
==============================================
    SERIALIZER MINI PARA ORDEN DE COMPRA
==============================================
"""
class OrdenCompraMiniSerializer(BaseSerializer):
    """
    Serializer mini para listar órdenes de compra básicas
    """
    proveedor_nombre = serializers.CharField(source='proveedor.nombre', read_only=True)
    encargado_nombre = serializers.CharField(source='encargado.full_name', read_only=True)
    
    class Meta:
        model = OrdenCompra
        fields = ('id', 'codigo', 'proveedor_nombre', 'estado',  'created_at','created_by','updated_at','updated_by', 'encargado_nombre')
        read_only_fields = ('id', 'codigo', 'proveedor_nombre', 'created_at', 'created_by','updated_at','updated_by', 'encargado_nombre')


"""
==============================================
    SERIALIZER PRINCIPAL PARA ORDEN DE COMPRA
==============================================
"""
class OrdenCompraSerializer(BaseSerializer):
    """
    Serializer completo para órden de compra con sus detalles
    """
    proveedor = SerializerRelatedField(
        queryset=Proveedor.objects.filter(status_model=BaseModel.STATUS_MODEL_ACTIVE),
        required=True,
        allow_null=False,
        help_text="ID del proveedor (solo activos, puede ser un entero o {\"id\": <pk>})"
    )
    proveedor_obj = ProveedorMiniSerializer(read_only=True, source='proveedor')
    

    encargado = SerializerRelatedField(
        queryset=Usuario.objects.filter(is_active=True),
        required=True,
        allow_null=False,
        help_text="ID del encargado (solo activos, puede ser un entero o {\"id\": <pk>})"
    )
    encargado_obj = UsuarioMiniSerializer(read_only=True, source='encargado')
    
    condicion_pago = serializers.ChoiceField(
        choices=CondicionPago.CONDICIONES_LIST,
        default=CondicionPago.CONDICION_CONTADO,
        help_text="Condición de pago",
        allow_null=True,
        required=False
    )
    
    pagos = MetodoPagoSerializer(many=True, required=False,
                                        allow_empty=True,
                                        help_text="Lista de métodos de pago asociados a la orden de compra")
    
    pagar_con_credito = serializers.BooleanField(default=False, help_text="Indica si se pagará con crédito del proveedor")
    pago_credito = serializers.DecimalField(max_digits=20, decimal_places=4, required=False, allow_null=True, help_text="Monto a pagar con crédito del proveedor",default=Decimal('0.00'))
    detalles = OrdenCompraDetalleSerializer(many=True, required=True)
    
    # Campos calculados
    #total_calculado = serializers.SerializerMethodField()
    total_productos = serializers.SerializerMethodField()
    pagos_detalle = serializers.SerializerMethodField()
    
    class Meta:
        model = OrdenCompra
        fields = [
            'id', 'codigo', 'proveedor', 'proveedor_obj', 'estado', 
             'total_productos',
            'encargado', 'encargado_obj','condicion_pago',
            'detalles', 'created_at', 'updated_at', 'created_by', 'updated_by',
             'pagos','pagos_detalle','pagar_con_credito','pago_credito'
        ]
        read_only_fields = ('id', 'codigo', 'total_productos', 'created_at', 'updated_at', 'created_by', 'updated_by', 'estado')

    def get_pagos_detalle(self, obj):
        """
        Obtener los pagos asociados a la orden de compra
        """
        pagos_qs = obj.pagos_orden_compra.all()
        pagos_list = []
        for pago in pagos_qs:
            pagos_list.append({
                'id': pago.id,
                'monto': pago.monto,
                'metodo_pago': {
                    'id': pago.metodo_pago.id,
                    'nombre': pago.metodo_pago.nombre
                } if pago.metodo_pago else None,
                'referencia': pago.referencia,
            })
        return pagos_list

    def get_total_productos(self, obj):
        """
        Obtener el número total de productos diferentes
        """
        if hasattr(obj, 'detalles'):
            return obj.detalles.count()
        return 0

    def validate_detalles(self, detalles):
        """
        Validar que haya al menos un detalle
        """
        if not detalles:
            raise serializers.ValidationError("Debe incluir al menos un producto en la orden de compra.")
        
        # Validar que no haya productos duplicados
        productos_ids = [detalle['producto'].id for detalle in detalles]
        if len(productos_ids) != len(set(productos_ids)):
            raise serializers.ValidationError("No se pueden incluir productos duplicados en la orden de compra.")
        
        return detalles

    def validate(self, data):
        """
        Validaciones generales
        """
         # Validar que no se pueda modificar si está en estados no permitidos
        if self.instance and self.instance.estado in [OrdenCompra.FINALIZADA, OrdenCompra.CANCELADA, OrdenCompra.EN_PROCESO]:
            raise DRFValidationError("No se puede modificar una orden de compra finalizada, cancelada o en proceso.")

        proveedor = data.get('proveedor')
        if proveedor and proveedor.status_model != BaseModel.STATUS_MODEL_ACTIVE:
            raise DRFValidationError("El proveedor seleccionado no está activo.")

        return data
    
    def validate_estado(self, value):
        """
        Validar que el estado sea uno de los permitidos
        """
        estados_permitidos = [OrdenCompra.PENDIENTE, OrdenCompra.EN_PROCESO, OrdenCompra.FINALIZADA, OrdenCompra.CANCELADA]
        if value not in estados_permitidos:
            raise serializers.ValidationError(f"El estado '{value}' no es válido.")
        return value
    

    def create(self, validated_data):
        """
        Crear orden de compra con sus detalles
        """
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            validated_data['created_by_id'] = request.user.id

        detalles_data = validated_data.pop('detalles')
        pagos = validated_data.pop('pagos', [])
        
        pagar_con_credito = validated_data.pop('pagar_con_credito', False)
        pago_credito = validated_data.pop('pago_credito', None)
        
        # Calcular el total antes de crear
        #total = sum(
        #    Decimal(str(detalle['cantidad'])) * Decimal(str(detalle['precio_unitario'])) 
        #    for detalle in detalles_data
        #)
        #validated_data['total'] = total
        
        # Crear la orden de compra
        orden_compra = OrdenCompra.objects.create(**validated_data)
        pagos_name_list = [p['metodo_pago'].nombre for p in pagos]
        # Crear los detalles
        for detalle_data in detalles_data:
            OrdenCompraDetalle.objects.create(orden_compra=orden_compra, **detalle_data)
        
        for metodo_data in pagos:
            metodo_pago = metodo_data['metodo_pago']
            monto = metodo_data['monto']
            referencia = metodo_data.get('referencia', None)
            orden_compra.pagos_orden_compra.create(
                metodo_pago=metodo_pago,
                monto=monto,
                referencia=referencia
            )
        if pagar_con_credito and float(pago_credito) > 0:
            metodo_credito = MetodoPago.objects.filter(nombre__iexact='CREDITO').first()
            orden_compra.pagos_orden_compra.create(
                metodo_pago=metodo_credito,
                monto=pago_credito,
                #referencia=referencia
            )
            pagos_name_list.append(metodo_credito.nombre)
            
        if len(pagos_name_list) == 1 and 'CREDITO' in pagos_name_list:
            orden_compra.condicion_pago = CondicionPago.CONDICION_CREDITO
            orden_compra.save()
        elif len(pagos_name_list) > 1 and 'CREDITO' in pagos_name_list:
            orden_compra.condicion_pago = CondicionPago.CONDICION_MIXTA
            orden_compra.save()
        elif len(pagos_name_list) >= 1 and 'CREDITO' not in pagos_name_list:
            orden_compra.condicion_pago = CondicionPago.CONDICION_CONTADO
            orden_compra.save()
        return orden_compra
    
    

    def update(self, instance, validated_data):
        """
        Actualizar orden de compra y sus detalles
        """
         # ✅ Obtener el usuario del contexto y agregarlo a validated_data
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            validated_data['updated_by_id'] = request.user.id
        detalles_data = validated_data.pop('detalles', None)
        #if instance.estado in [OrdenCompra.FINALIZADA, OrdenCompra.CANCELADA, OrdenCompra.EN_PROCESO]:
        #    raise serializers.ValidationError("No se puede modificar una orden de compra finalizada, cancelada o en proceso.")
        #print(detalles_data)
        
        # Actualizar campos básicos
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Si se proporcionan detalles, manejar actualizaciones inteligentemente
        if detalles_data is not None:
            # ✅ Obtener detalles existentes como lista de diccionarios con ID de producto y cantidad
            detalles_existentes = [
                {'id': detalle.id, 'producto_id': detalle.producto.id, 'cantidad': detalle.cantidad}
                for detalle in instance.detalles.all()
            ]
            # Crear un mapa de detalles existentes por ID para búsqueda rápida
            #detalles_map = {detalle['id']: detalle for detalle in detalles_existentes}
            productos_existentes = [detalle['producto_id'] for detalle in detalles_existentes]
            productos_enviados = [detalle_data['producto'].id for detalle_data in detalles_data]
            
            # ✅ Obtener productos eliminados por ID
            productos_eliminados = [pid for pid in productos_existentes if pid not in productos_enviados]
            
            productos_new = []
            #total = Decimal('0.00')
            
            for detalle_data in detalles_data:
                producto_id = detalle_data['producto'].id
                cantidad = Decimal(str(detalle_data['cantidad']))
                precio_raw = detalle_data.get('precio', None)

                if precio_raw in (None, "", 0):
                    raise serializers.ValidationError({
                        "detalles": "Todos los productos deben incluir un precio válido al editar la orden."
                    })

                try:
                    precio = Decimal(str(precio_raw))
                except InvalidOperation:
                    raise serializers.ValidationError({
                        "detalles": f"Precio inválido para el producto {detalle_data.get('producto')}"
                    })
                #precio_unitario = Decimal(str(detalle_data['precio_unitario']))
                #subtotal_calculado = cantidad * precio_unitario
                
                if producto_id not in productos_existentes:
                    # Producto nuevo
                    productos_new.append({
                        'id': producto_id,
                        'cantidad': cantidad,
                        'precio': precio,
                        #'precio_unitario': precio_unitario,
                        #'subtotal': subtotal_calculado
                    })
                else:
                    # Si el producto ya existe, actualizar su cantidad
                    model_detalle = OrdenCompraDetalle.objects.get(producto_id=producto_id, orden_compra=instance)
                    if model_detalle:
                        model_detalle.cantidad = cantidad
                        #model_detalle.precio_unitario = precio_unitario
                        #model_detalle.subtotal = subtotal_calculado
                        model_detalle.precio = precio
                        model_detalle.save()
                
                # ✅ Sumar al total todos los productos (nuevos y actualizados)
                #total += subtotal_calculado
                
            # ✅ Eliminar productos que ya no están en la lista
            if productos_eliminados:
                OrdenCompraDetalle.objects.filter(
                    producto_id__in=productos_eliminados,
                    orden_compra=instance
                ).delete()
                
            # ✅ Crear nuevos detalles
            for detalle in productos_new:
                OrdenCompraDetalle.objects.create(
                    orden_compra=instance,
                    producto_id=detalle['id'],
                    cantidad=detalle['cantidad'],
                    precio=detalle['precio'],
                    #precio_unitario=detalle['precio_unitario'],
                    #subtotal=detalle['subtotal']
                )
                
            

            # ✅ Actualizar el total calculado
            #instance.total = total
        
        
        #procesar métodos de pago si es necesario (opcional)
        #metodos_pago = validated_data.pop('metodos_pago', None)
        metodos_pago = validated_data.get('metodos_pago', None)
        if metodos_pago is not None:
            # Eliminar métodos de pago existentes
            instance.pagos_orden_compra.all().delete()
            # Crear nuevos métodos de pago
            for metodo_data in metodos_pago:
                metodo_pago = metodo_data['metodo_pago']
                monto = metodo_data['monto']
                referencia = metodo_data.get('referencia', None)
                instance.pagos_orden_compra.create(
                    metodo_pago=metodo_pago,
                    monto=monto,
                    referencia=referencia
                )
        instance.refresh_from_db()
        instance.total = sum(
            d.cantidad * d.precio
            for d in instance.detalles.all()
        )

        instance.recalcular_pagos()
        
        instance.save()
        return instance


"""
==============================================
    SERIALIZER PARA ACTUALIZAR ESTADO
==============================================
"""
class OrdenCompraEstadoSerializer(BaseSerializer):
    """
    Serializer específico para actualizar solo el estado de una orden de compra
    """
    class Meta:
        model = OrdenCompra
        fields = ('estado',)

    def validate_estado(self, value):
        """
        Validar transiciones de estado válidas
        """
        if self.instance:
            estado_actual = self.instance.estado
            
            # Reglas de transición
            transiciones_validas = {
                OrdenCompra.PENDIENTE: [OrdenCompra.EN_PROCESO, OrdenCompra.CANCELADA],
                OrdenCompra.EN_PROCESO: [OrdenCompra.FINALIZADA, OrdenCompra.CANCELADA],
                OrdenCompra.FINALIZADA: [],  # No se puede cambiar desde finalizada
                OrdenCompra.CANCELADA: [],   # No se puede cambiar desde cancelada
            }
            
            if value not in transiciones_validas.get(estado_actual, []):
                raise serializers.ValidationError(
                    f"No es posible cambiar el estado de '{estado_actual}' a '{value}'"
                )
        
        return value




"""
==============================================
    SERIALIZERS PARA COMPRA DETALLE
==============================================
"""
class CompraDetalleSerializer(BaseSerializer):
    """
    Serializer para los detalles de una compra
    """
    producto = SerializerRelatedField(
        queryset=Producto.objects.filter(status_model=BaseModel.STATUS_MODEL_ACTIVE),
        required=True,
        allow_null=False,
        help_text="ID del producto (solo activos, puede ser un entero o {\"id\": <pk>})"
    )
    #producto_nombre = serializers.CharField(max_length=255, read_only=True, source='producto.nombre')
    #producto_codigo = serializers.CharField(max_length=100, read_only=True, source='producto.codigo')
    #producto_unidad = serializers.CharField(max_length=100, read_only=True, source='producto.unidad_sat.clave')
    producto_obj = ProductoMiniSerializer(read_only=True, source='producto')
    
    cantidad = serializers.DecimalField(max_digits=25, decimal_places=5, min_value=Decimal('0.01'), required=True)
    precio_unitario = serializers.DecimalField(max_digits=25, decimal_places=5, min_value=Decimal('0'), required=False)
    subtotal = serializers.DecimalField(max_digits=25, decimal_places=5, read_only=True)

    class Meta:
        model = CompraDetalle
        fields = [
            'id', 'producto', 'producto_obj', 'cantidad', 
            'precio_unitario', 'subtotal',
            "existe_diferencia","es_producto_nuevo","cantidad_entrada"
        ]
        read_only_fields = ('id', 'subtotal', 'existe_diferencia', 'es_producto_nuevo', 'cantidad_entrada')

    def validate(self, data):
        """
        Validar que el producto esté activo
        """
        producto = data.get('producto')
        if producto and producto.status_model != BaseModel.STATUS_MODEL_ACTIVE:
            raise serializers.ValidationError("El producto seleccionado no está activo.")
        return data


"""
==============================================
    SERIALIZERS PARA PAGOS DE COMPRA
==============================================
"""


"""
==============================================
    SERIALIZER MINI PARA COMPRA
==============================================
"""
class CompraMiniSerializer(BaseSerializer):
    """
    Serializer mini para listar compras básicas
    """
    proveedor_nombre = serializers.CharField(source='proveedor.nombre', read_only=True)
    almacen_destino_nombre = serializers.CharField(source='almacen_destino.nombre', read_only=True)
    orden_compra_codigo = serializers.CharField(source='orden_compra.codigo', read_only=True, allow_null=True)
    #is_app = serializers.BooleanField(required=True, help_text="Indica si la compra fue creada desde la App Móvil")
    
    class Meta:
        model = Compra
        fields = (
            'id', 'codigo', 'is_app', 'orden_compra_codigo', 'proveedor_nombre',
            'almacen_destino_nombre', 'estado', 'total', 'fecha_salida',
            'existe_diferencia', 'created_at'
        )
        read_only_fields = (
            'id', 'codigo', 'is_app', 'orden_compra_codigo', 'proveedor_nombre',
            'almacen_destino_nombre', 'created_at'
        )

class CompraMiniListSerializer(BaseSerializer):
    """
    Serializer mini para listar compras básicas
    """
    class Meta:
        model = Compra
        fields = (
            'id', 'codigo','is_app'
        )
        read_only_fields = (
            'id', 'codigo','is_app'
        )


"""
==============================================
    SERIALIZER PRINCIPAL PARA COMPRA
==============================================
"""
class CompraSerializer(BaseSerializer):
    """
    Serializer completo para compra con sus detalles y pagos
    """
    orden_compra = SerializerRelatedField(
        queryset=OrdenCompra.objects.filter(status_model=BaseModel.STATUS_MODEL_ACTIVE),
        required=False,
        allow_null=True,
        help_text="ID de la orden de compra (opcional, puede ser un entero o {\"id\": <pk>})"
    )
    orden_compra_obj = OrdenCompraMiniSerializer(read_only=True, source='orden_compra')
    
    proveedor = SerializerRelatedField(
        queryset=Proveedor.objects.filter(status_model=BaseModel.STATUS_MODEL_ACTIVE),
        required=True,
        allow_null=False,
        help_text="ID del proveedor (solo activos, puede ser un entero o {\"id\": <pk>})"
    )
    proveedor_obj = ProveedorMiniSerializer(read_only=True, source='proveedor')
    destino_is_cedis = serializers.BooleanField(read_only=True, source='almacen_destino.is_cedis')
    almacen_destino = SerializerRelatedField(
        queryset=Almacen.objects.filter(status_model=BaseModel.STATUS_MODEL_ACTIVE),
        required=True,
        allow_null=False,
        help_text="ID del almacén destino (solo activos, puede ser un entero o {\"id\": <pk>})"
    )
    almacen_destino_obj = AlmacenMiniSerializer(read_only=True, source='almacen_destino')

    fecha_salida = serializers.DateField(required=True)
    
    # Campo estado con valor por defecto
    estado = serializers.ChoiceField(
        choices=Compra.ESTADO_COMPRA_CHOICES,
        default=Compra.PROCESANDO,
        required=False,
        help_text="Estado de la compra"
    )

    # Los detalles y pagos se manejan por separado
    
    latitud = serializers.DecimalField(max_digits=10, decimal_places=8, required=False, allow_null=True)
    longitud = serializers.DecimalField(max_digits=10, decimal_places=8, required=False, allow_null=True)

    is_app = serializers.BooleanField(required=True, help_text="Indica si la compra fue creada desde la App Móvil")

    condicion_pago = serializers.ChoiceField(
        choices=CondicionPago.CONDICIONES_LIST,
        default=CondicionPago.CONDICION_CONTADO,
        help_text="Condición de pago",
        allow_null=True,
        required=False
    )
    pagos = MetodoPagoSerializer(many=True, required=False,
                                        allow_empty=True,
                                        help_text="Lista de métodos de pago asociados a la orden de compra")
    pagos_detalle = serializers.SerializerMethodField(read_only=True)
    pagar_con_credito = serializers.BooleanField(default=False, help_text="Indica si se pagará con crédito del proveedor")
    pago_credito = serializers.DecimalField(max_digits=20, decimal_places=4, required=False, allow_null=True, help_text="Monto a pagar con crédito del proveedor",default=Decimal('0.00'))
    
    detalles = CompraDetalleSerializer(many=True, required=False)
    
    class Meta:
        model = Compra
        fields = [
            'id', 'codigo','is_app', 'orden_compra', 'orden_compra_obj', 'proveedor', 'proveedor_obj',
            'almacen_destino', 'almacen_destino_obj','destino_is_cedis',
            'total', 'estado',
            "existe_diferencia",
            # 'total_calculado', 'total_productos', 'total_pagado', 'saldo_pendiente',
            'tiempo_recorrido', 'fecha_salida', 'latitud', 'longitud', 'nota',
            'detalles', 'created_at', 'updated_at', 'created_by', 'updated_by',
            'condicion_pago','pagos_detalle', 'pagos', 'pagar_con_credito', 'pago_credito'
        ]
        read_only_fields = (
            'id', 'codigo', 'total',"existe_diferencia",'destino_is_cedis',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        )
        
    def get_pagos_detalle(self, obj):
        """
        Obtener los pagos asociados a la orden de compra
        """
        pagos_qs = obj.pagos.all()
        pagos_list = []
        for pago in pagos_qs:
            pagos_list.append({
                'id': pago.id,
                'monto': pago.monto,
                'metodo_pago': {
                    'id': pago.metodo_pago.id,
                    'nombre': pago.metodo_pago.nombre
                } if pago.metodo_pago else None,
                'referencia': pago.referencia,
            })
        return pagos_list

    def validate_detalles(self, detalles):
        """
        Validar que haya al menos un detalle si se proporcionan
        """
        if detalles is not None and len(detalles) == 0:
            raise serializers.ValidationError("Debe incluir al menos un producto en la compra.")
        
        #if detalles:
            # Validar que no haya productos duplicados
        #    productos_ids = [detalle['producto'].id for detalle in detalles]
        #    if len(productos_ids) != len(set(productos_ids)):
        #        raise serializers.ValidationError("No se pueden incluir productos duplicados en la compra.")
        
        return detalles

    

    def validate(self, data):
        """
        Validaciones generales
        """
        proveedor = data.get('proveedor')
        if proveedor and proveedor.status_model != BaseModel.STATUS_MODEL_ACTIVE:
            raise serializers.ValidationError("El proveedor seleccionado no está activo.")
            
        almacen_destino = data.get('almacen_destino')
        if almacen_destino and almacen_destino.status_model != BaseModel.STATUS_MODEL_ACTIVE:
            raise serializers.ValidationError("El almacén destino seleccionado no está activo.")
        
        #if self.instance and self.instance.estado in [Compra.FINALIZADA]:
        #    raise serializers.ValidationError("No se puede modificar una compra que está en camino.")
        ## Validar que si se proporciona orden_compra, el proveedor coincida
        #orden_compra = data.get('orden_compra')
        #if orden_compra and proveedor and orden_compra.proveedor != proveedor:
        #    raise serializers.ValidationError(
        #        "El proveedor de la compra debe coincidir con el proveedor de la orden de compra."
        #    )
        #
        return data

    def create(self, validated_data):
        """
        Crear compra con sus detalles y pagos
        """
        orden_compra = validated_data.get('orden_compra')
            # ✅ ASIGNAR ALMACÉN VIRTUAL POR DEFECTO
        # ✅ ALMACÉN VIRTUAL POR DEFECTO: CEDIS
        if not validated_data.get('almacen_virtual'):
            almacen_virtual = Almacen.objects.filter(
                is_cedis=True,
                status_model=BaseModel.STATUS_MODEL_ACTIVE
            ).first()

            if not almacen_virtual:
                raise serializers.ValidationError(
                    "No existe un almacén CEDIS activo para asignar a la compra."
                )

            validated_data['almacen_virtual'] = almacen_virtual


        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            validated_data['created_by_id'] = request.user.id

        detalles_data = validated_data.pop('detalles', [])
        metodos_pago = validated_data.pop('pagos', [])
        #condicion_pago = validated_data.pop('condicion_pago', CondicionPago.CONDICION_CONTADO)
        
        detalles_producto_is_app = []

        # Calcular el total antes de crear si hay detalles
        if detalles_data:
            total = Decimal('0.00')
            #SI ES IS_APP TOMAR LOS DETALLES DEL PRODUCTO DE LA ORDEN DE COMPRA
            if validated_data.get('is_app') and orden_compra:
                for detalle in detalles_data:
                    detalle_oc = OrdenCompraDetalle.objects.filter(
                        orden_compra=orden_compra,
                        producto=detalle['producto']
                    ).first()
                    if detalle_oc:
                        detalles_producto_is_app.append({
                            'producto_id': detalle['producto'].id,
                            'cantidad': detalle['cantidad'],
                            'precio_unitario': detalle_oc.precio,
                        })
                        total += Decimal(str(detalle['cantidad'])) * Decimal(str(detalle_oc.precio))
            else:        
                total = sum(
                    Decimal(str(detalle['cantidad'])) * Decimal(str(detalle['precio_unitario'])) 
                    for detalle in detalles_data
                )
            validated_data['total'] = total
        elif 'total' not in validated_data:
            validated_data['total'] = Decimal('0.00')

        #if not validated_data.get('is_app'):
        validated_data['estado'] = Compra.EN_CAMINO
        pagar_con_credito = validated_data.pop('pagar_con_credito', False)
        pago_credito = validated_data.pop('pago_credito', None)
        
        # Crear la compra
        compra = Compra.objects.create(**validated_data)
        
        # Crear los detalles
        if detalles_producto_is_app:
            for detalle_data in detalles_producto_is_app:
                # Calcular subtotal antes de crear el detalle
                cantidad = Decimal(str(detalle_data['cantidad']))
                precio_unitario = Decimal(str(detalle_data['precio_unitario']))
                subtotal_calculado = cantidad * precio_unitario

                # Agregar el subtotal a los datos del detalle
                detalle_data['subtotal'] = subtotal_calculado
            
                CompraDetalle.objects.create(compra=compra, **detalle_data)
        else:
            for detalle_data in detalles_data:
                # Calcular subtotal antes de crear el detalle
                cantidad = Decimal(str(detalle_data['cantidad']))
                precio_unitario = Decimal(str(detalle_data['precio_unitario']))
                subtotal_calculado = cantidad * precio_unitario

                # Agregar el subtotal a los datos del detalle
                detalle_data['subtotal'] = subtotal_calculado
            
                CompraDetalle.objects.create(compra=compra, **detalle_data)
        
        # Crear los pagos
        #for pago_data in pagos_data:
        #    PagosCompra.objects.create(compra=compra, **pago_data)

        #orden_compra = validated_data.get('orden_compra')
        if orden_compra:
            compra.condicion_pago = orden_compra.condicion_pago
            compra.save()
            orden_compra.estado = OrdenCompra.EN_PROCESO
            orden_compra.save()
            #asociar lo spagos de la orden de compra a la compra
            for pago_oc in orden_compra.pagos_orden_compra.all():
                PagosCompra.objects.create(
                    compra=compra,
                    metodo_pago=pago_oc.metodo_pago,
                    monto=pago_oc.monto,
                    created_by=pago_oc.created_by,
                    referencia=pago_oc.referencia
                )
        
            # Asociar la orden de compra con la compra
            #compra.orden_compra = orden_compra
            #print("Asociando orden de compra:", orden_compra)
            
        pagos_name_list = [p['metodo_pago'].nombre for p in metodos_pago]
        
        for metodo_data in metodos_pago:
            metodo_pago = metodo_data['metodo_pago']
            monto = metodo_data['monto']
            referencia = metodo_data.get('referencia', '')
            compra.pagos.create(
                metodo_pago=metodo_pago,
                monto=monto,
                created_by=compra.created_by,
                referencia=referencia
            )
            
        if pagar_con_credito and float(pago_credito) > 0:
            from apps.credito.models import CreditoProveedor
            metodo_credito = MetodoPago.objects.filter(nombre__iexact='CREDITO').first()
            compra.pagos.create(
                metodo_pago=metodo_credito,
                monto=pago_credito,
                #referencia=referencia
            )
            CreditoProveedor.objects.create(
                compra=compra,
                proveedor=compra.proveedor,
                monto=pago_credito,
                #referencia=referencia
            )
            pagos_name_list.append(metodo_credito.nombre)
            
        if len(pagos_name_list) == 1 and 'CREDITO' in pagos_name_list:
            compra.condicion_pago = CondicionPago.CONDICION_CREDITO
            compra.save()
        elif len(pagos_name_list) > 1 and 'CREDITO' in pagos_name_list:
            compra.condicion_pago = CondicionPago.CONDICION_MIXTA
            compra.save()
        elif len(pagos_name_list) >= 1 and 'CREDITO' not in pagos_name_list:
            compra.condicion_pago = CondicionPago.CONDICION_CONTADO
            compra.save()
        return compra

    def update(self, instance, validated_data):
        """
        Actualizar compra y sus detalles/pagos
        """
        if instance.estado in [Compra.FINALIZADA]:
            raise serializers.ValidationError("No se puede modificar una compra que está en camino.")

        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            validated_data['updated_by_id'] = request.user.id


        # Si la compra ya tiene una orden de compra asignada
        if instance.orden_compra:
            nueva_orden = validated_data.get('orden_compra')
            
            # Verificar si se está intentando cambiar la orden de compra
            if nueva_orden and nueva_orden.id != instance.orden_compra.id:
            # Cambiar a nueva orden: revertir estado de la orden anterior
                instance.orden_compra.estado = OrdenCompra.SOLICITUD
                instance.orden_compra.save()
            elif nueva_orden is None:
                # Desasociar orden: revertir estado de la orden actual
                instance.orden_compra.estado = OrdenCompra.SOLICITUD
                instance.orden_compra.save()

        orden_compra = validated_data.get('orden_compra')
        if orden_compra and orden_compra.estado == OrdenCompra.SOLICITUD:
            orden_compra.estado = OrdenCompra.EN_PROCESO
            orden_compra.save()
        
        #print("VALIDATED DATA EN UPDATE:", validated_data)

        # ✅ CORRECCIÓN: Usar None como default para detectar si se envió el campo
        detalles_data = validated_data.pop('detalles', None)
        metodos_pago = validated_data.pop('metodos_pago', None)
        
        # Actualizar campos básicos
        for attr, value in validated_data.items():
            setattr(instance, attr, value)


        
        # ✅ Solo procesar detalles si se envían explícitamente
        if detalles_data is not None:
            # Eliminar detalles existentes
            instance.detalles.all().delete()
            total = Decimal('0.00')    
            #imprimir la query 
            #print(instance.detalles.all().query)
            if orden_compra and instance.is_app:
                detalles_producto_is_app = []
                for detalle in detalles_data:
                    detalle_oc = OrdenCompraDetalle.objects.filter(
                        orden_compra=orden_compra,
                        producto=detalle['producto']
                    ).first()
                    if detalle_oc:
                        detalles_producto_is_app.append({
                            'producto_id': detalle['producto'].id,
                            'cantidad': detalle['cantidad'],
                            'precio_unitario': detalle_oc.precio,
                        })
                        total += Decimal(str(detalle['cantidad'])) * Decimal(str(detalle_oc.precio))
                detalles_data = detalles_producto_is_app
            else:
                # Crear nuevos detalles SOLO si hay datos
                for detalle_data in detalles_data:
                    # Calcular subtotal antes de crear el detalle
                    cantidad = Decimal(str(detalle_data['cantidad']))
                    precio_unitario = Decimal(str(detalle_data['precio_unitario']))
                    subtotal_calculado = cantidad * precio_unitario

                    # Agregar el subtotal a los datos del detalle
                    detalle_data['subtotal'] = subtotal_calculado

                    # Crear el detalle
                    detalle = CompraDetalle.objects.create(compra=instance, **detalle_data)
                    total += subtotal_calculado
            
            # Actualizar el total solo si se procesaron detalles
            instance.total = total
        
        # ✅ Solo procesar métodos de pago si se envían explícitamente
        if metodos_pago is not None:
            # Eliminar métodos de pago existentes
            instance.pagos.all().delete()
            # Crear nuevos métodos de pago
            for metodo_data in metodos_pago:
                metodo_pago = metodo_data['metodo_pago']
                monto = metodo_data['monto']
                referencia = metodo_data.get('referencia', None)
                instance.pagos.create(
                    metodo_pago=metodo_pago,
                    monto=monto,
                    created_by=instance.updated_by,
                    referencia=referencia
                )
        
        instance.save()
        return instance


"""
==============================================
    SERIALIZER PARA ACTUALIZAR ESTADO
==============================================
"""
class CompraEstadoSerializer(BaseSerializer):
    """
    Serializer específico para actualizar solo el estado de una compra
    """
    class Meta:
        model = Compra
        fields = ('estado',)

    def validate_estado(self, value):
        """
        Validar transiciones de estado válidas
        """
        if self.instance:
            estado_actual = self.instance.estado
            
            # Reglas de transición para compras
            transiciones_validas = {
                Compra.ALMACEN_VIRTUAL: [Compra.ALMACEN],  # De virtual a almacén
                Compra.ALMACEN: [],  # Una vez en almacén, no se puede cambiar
            }
            
            if value not in transiciones_validas.get(estado_actual, []):
                raise serializers.ValidationError(
                    f"No es posible cambiar el estado de '{estado_actual}' a '{value}'"
                )
        
        return value




"""
==============================================
    SERIALIZERS PARA GASTOS DE COMPRA
==============================================
"""

class GastosCompraCreateSerializer(BaseSerializer):
    """
    Serializer para los gastos asociados a una compra
    """
    compra = SerializerRelatedField(
        queryset=Compra.objects.filter(status_model=BaseModel.STATUS_MODEL_ACTIVE),
        required=True,
        allow_null=False,
        help_text="ID de la compra asociada (solo activas, puede ser un entero o {\"id\": <pk>})"
    )
   
    class Meta:
        model = GastosCompra
        fields = (
            'compra', 'descripcion', 'monto', 'concepto', 
        )
        
class GastosCompraMultipleCreateSerializer(serializers.Serializer):
    """Serializer para crear múltiples gastos de compra"""
    gastos = GastosCompraCreateSerializer(many=True)
class CompraGastoListSerializer(BaseSerializer):
    """
    Serializer para los gastos asociados a una compra
    """
    compra_folio = serializers.SerializerMethodField(read_only=True)
   
    class Meta:
        model = GastosCompra
        fields = (
            'id','compra_folio', 'descripcion', 'monto', 'concepto', 'created_at', 'created_by',
        )
        read_only_fields = ('id',)
    
    def get_compra_folio(self, obj):
        return obj.compra.codigo if obj.compra else None
class CompraGastoRetrieveSerializer(BaseSerializer):
    """
    Serializer para los gastos asociados a una compra
    """
    compra_folio = serializers.SerializerMethodField(read_only=True)
   
    class Meta:
        model = GastosCompra
        fields = (
            'id','compra_folio', 'descripcion', 'monto', 'concepto', 'created_at', 'created_by',
            'updated_at', 'updated_by'
        )
        read_only_fields = ('id',)
    def get_compra_folio(self, obj):
        return obj.compra.codigo if obj.compra else None