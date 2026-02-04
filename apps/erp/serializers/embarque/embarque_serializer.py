from rest_framework import serializers
from apps.erp.models import Venta, Almacen, Rutas, Producto, CajaApertura, CajaTransaccion
from apps.inventario.models import LoteInventario, EmbarqueReparto, ProductoEmbarque
from apps.base.serializer import FlexiblePKRelatedField, SerializerRelatedField

from apps.erp.helpers.embarque import crear_movimiento_inventario_almacen_embarque


################################################################################################################
#                      SERIALIZERS PARA MOVIMIENTOS DE CAJA DEL EMBARQUE
################################################################################################################

class CajaTransaccionEmbarqueSerializer(serializers.ModelSerializer):
    """
    Serializer para mostrar las transacciones de caja en el contexto de un embarque
    """
    metodo_pago_id = serializers.IntegerField(source='metodo_pago.id', read_only=True, allow_null=True)
    metodo_pago_nombre = serializers.CharField(source='metodo_pago.nombre', read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    
    class Meta:
        model = CajaTransaccion
        fields = [
            'id',
            'referencia',
            'tipo',
            'monto',
            'metodo_pago_id',
            'metodo_pago_nombre',
            'gasto_tipo',
            'descripcion',
            'created_at',
        ]
        read_only_fields = fields


class EmbarqueCajaMovimientosSerializer(serializers.ModelSerializer):
    """
    Serializer para mostrar los movimientos de caja asociados a un embarque
    """
    caja_id = serializers.IntegerField(source='caja.id', read_only=True, allow_null=True)
    caja_nombre = serializers.CharField(source='caja.nombre', read_only=True, allow_null=True)
    usuario_id = serializers.IntegerField(source='usuario.id', read_only=True, allow_null=True)
    usuario_nombre = serializers.SerializerMethodField(read_only=True)
    fecha_apertura = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    fecha_cierre = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True, allow_null=True)
    
    transacciones = CajaTransaccionEmbarqueSerializer(many=True, read_only=True)
    
    # Totales calculados
    total_entradas = serializers.SerializerMethodField(read_only=True)
    total_salidas = serializers.SerializerMethodField(read_only=True)
    total_gastos = serializers.SerializerMethodField(read_only=True)
    balance = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = CajaApertura
        fields = [
            'id',
            'caja_id',
            'caja_nombre',
            'usuario_id',
            'usuario_nombre',
            'monto_inicial',
            'monto_final',
            'is_abierta',
            'fecha_apertura',
            'fecha_cierre',
            'transacciones',
            'total_entradas',
            'total_salidas',
            'total_gastos',
            'balance',
        ]
        read_only_fields = fields
    
    def get_usuario_nombre(self, obj):
        """Obtiene el nombre completo del usuario"""
        if obj.usuario:
            return obj.usuario.full_name()
        return None
    
    def get_total_entradas(self, obj):
        """Calcula el total de entradas"""
        total = sum(
            float(t.monto) for t in obj.transacciones.all()
            if t.tipo == CajaTransaccion.TIPO_ENTRADA and t.status_model == CajaTransaccion.STATUS_MODEL_ACTIVE
        )
        return round(total, 2)
    
    def get_total_salidas(self, obj):
        """Calcula el total de salidas"""
        total = sum(
            float(t.monto) for t in obj.transacciones.all()
            if t.tipo == CajaTransaccion.TIPO_SALIDA and t.status_model == CajaTransaccion.STATUS_MODEL_ACTIVE
        )
        return round(total, 2)
    
    def get_total_gastos(self, obj):
        """Calcula el total de gastos"""
        total = sum(
            float(t.monto) for t in obj.transacciones.all()
            if t.tipo == CajaTransaccion.TIPO_GASTO and t.status_model == CajaTransaccion.STATUS_MODEL_ACTIVE
        )
        return round(total, 2)
    
    def get_balance(self, obj):
        """Calcula el balance (monto_inicial + entradas - salidas - gastos)"""
        monto_inicial = float(obj.monto_inicial) if obj.monto_inicial else 0.0
        entradas = self.get_total_entradas(obj)
        salidas = self.get_total_salidas(obj)
        gastos = self.get_total_gastos(obj)
        return round(monto_inicial + entradas - salidas - gastos, 2)


class VentaEmbarqueCajaSerializer(serializers.ModelSerializer):
    """
    Serializer para mostrar las ventas realizadas durante el periodo del embarque
    """
    cliente_id = serializers.IntegerField(source='cliente.id', read_only=True, allow_null=True)
    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    created_by_id = serializers.IntegerField(source='created_by.id', read_only=True, allow_null=True)
    created_by_nombre = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Venta
        fields = [
            'id',
            'codigo',
            'cliente_id',
            'cliente_nombre',
            'fase',
            'tipo_venta',
            'total',
            'total_pagado',
            'condicion_pago',
            'is_entregado',
            'created_at',
            'created_by_id',
            'created_by_nombre',
        ]
        read_only_fields = fields
    
    def get_created_by_nombre(self, obj):
        """Obtiene el nombre completo del usuario que creó la venta"""
        if obj.created_by:
            return obj.created_by.full_name()
        return None

################################################################################################################
class LoteProductoEmbarqueSerializer(serializers.Serializer):
    lote = SerializerRelatedField(
        queryset=LoteInventario.objects.exclude(status_model=LoteInventario.STATUS_MODEL_DELETE).all(),
        help_text="ID del lote o dic {id: <id>}",
        required=True
    )
    cantidad = serializers.DecimalField(max_digits=20, decimal_places=5, help_text="Cantidad del lote del producto")

class ProductoEmbarqueSerializer(serializers.Serializer):
    producto = SerializerRelatedField(
        queryset=Producto.objects.filter().all(),
        help_text="ID del producto o dic {id: <id>}",
        required=True
    )
    check = serializers.BooleanField(help_text="Indica si el producto está seleccionado para el embarque", required=False)
    #cantidad = serializers.DecimalField(max_digits=20, decimal_places=5, help_text="Cantidad del producto")
    #lotes = LoteProductoEmbarqueSerializer(many=True, required=False, help_text="Lista de lotes de productos en el embarque")

class ProductosTaraEmbarqueSerializer(serializers.Serializer):
    producto_carga = SerializerRelatedField(
        queryset=ProductoEmbarque.objects.exclude(tipo=ProductoEmbarque.PEDIDO).all(),
        help_text="ID del producto en tara o dic {id: <id>}",
        required=True
    ) 
    check = serializers.BooleanField(help_text="Indica si el producto en tara está seleccionado para el embarque", required=True)
    
class ProductoEmbarqueVentaSerializer(serializers.Serializer):
    venta = SerializerRelatedField(
        queryset=Venta.objects.exclude(status_model=Venta.STATUS_MODEL_DELETE).all(),
        help_text="ID de la venta o dic {id: <id>}",
        required=True
    )
    productos = ProductoEmbarqueSerializer(many=True, allow_empty=False, help_text="Lista de productos asociados a la venta en el embarque")

   


class VentasEmbarqueSubidaRutaSerializer(serializers.Serializer):
    embarque = SerializerRelatedField(
        queryset=EmbarqueReparto.objects.exclude(status_model=EmbarqueReparto.STATUS_MODEL_DELETE).all(),
        help_text="ID del embarque o dic {id: <id>}",
        required=True
    )
    ventas = ProductoEmbarqueVentaSerializer(many=True, allow_empty=False, help_text="Lista de ventas con sus productos para el embarque de la ruta")
    productos_tara = ProductosTaraEmbarqueSerializer(many=True, required=False, help_text="Lista de productos en tara asociados a la venta en el embarque")

   
################################################################################################################

class EmbarqueSerializer(serializers.Serializer):
    almacen_origen = SerializerRelatedField(
        queryset=Almacen.objects.all(),
        help_text="ID del almacén de origen asociado al embarque o dic {id: <id>}",
        required=False,
        allow_null=True
    )
    
    ruta = SerializerRelatedField(
        queryset=Rutas.objects.filter(status_model='ACTIVE').all(),
        help_text="ID de la ruta asociada al embarque o dic {id: <id>}",
        required=True
    )
    
    pedidos = ProductoEmbarqueVentaSerializer(many=True, allow_empty=False, help_text="Lista de preventas asociadas al embarque o lista de diccionarios {id: <id>, productos: [{id: <id>, cantidad: <cantidad>}, ...]}", required=True)

    productos_tara = ProductoEmbarqueSerializer(many=True, required=False, help_text="Lista de productos en tara (opcional)")


    
    def create(self, validated_data):
        # Implementar lógica para crear el embarque
        almacen_origen = self.context.get('almacen_origen')
        ruta = validated_data.get('ruta')
        pedidos = validated_data.get('pedidos', [])
        productos_tara = validated_data.get('productos_tara', [])
        

        #print("Crear embarque con datos:", ruta, embarque_rutas_list, productos_tara)
        model_embarque = crear_movimiento_inventario_almacen_embarque(ruta=ruta, pedidos=pedidos, productos_tara=productos_tara, usuario=None,almacen_origen=almacen_origen)
        # Lógica de negocio para embarque...
        return model_embarque
    
    def update(self, instance, validated_data):
        # Implementar lógica para actualizar el embarque
        return instance


class EmbarqueMiniSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado para listados de embarque
    """
    ruta_id = serializers.IntegerField(source='ruta.id', read_only=True)
    ruta_nombre = serializers.CharField(source='ruta.nombre', read_only=True)
    ruta_codigo = serializers.CharField(source='ruta.codigo', read_only=True)
    encargado_id = serializers.IntegerField(source='encargado.id', read_only=True, allow_null=True)
    encargado_nombre = serializers.CharField(source='encargado.full_name', read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    condicion_pago = serializers.SerializerMethodField()

    class Meta:
        model = EmbarqueReparto
        fields = [
            'id',
            'fase',
            'nota',
            'fecha_salida',
            'fecha_finalizada',
            'created_at',
            'ruta_id',
            'ruta_nombre',
            'ruta_codigo',
            'encargado_id',
            'encargado_nombre',
            'condicion_pago',   # 👈 AGREGA AQUÍ

        ]
    def get_condicion_pago(self, obj):
        """
        Devuelve:
        - CONTADO
        - CRÉDITO
        - MIXTO
        """
        condiciones = (
            obj.ventas
            .values_list('condicion_pago', flat=True)
            .distinct()
        )

        if not condiciones:
            return None

        condiciones = list(condiciones)

        if len(condiciones) == 1:
            return condiciones[0]

        return 'MIXTO'

class LoteProductoEmbarqueDetailSerializer(serializers.Serializer):
    """Serializer para mostrar lotes de productos en embarque"""
    lote_id = serializers.IntegerField(source='lote.id', read_only=True)
    cantidad = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    costo_unitario = serializers.DecimalField(source='lote.costo_unitario', max_digits=20, decimal_places=2, read_only=True)


class ProductoCargadoEmbarqueSerializer(serializers.Serializer):
    """Serializer para productos cargados en un embarque asociados a una venta"""
    id = serializers.IntegerField(read_only=True)
    producto_id = serializers.IntegerField(source='producto.id', read_only=True)
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    precio_unitario = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    producto_codigo = serializers.CharField(source='producto.codigo', read_only=True)
    unidad_medida = serializers.CharField(source='producto.unidad_sat.nombre', read_only=True, allow_null=True)
    unidad_clave = serializers.CharField(source='producto.unidad_sat.clave', read_only=True, allow_null=True)
    cantidad = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    cantidad_entregada = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    cantidad_cargada = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    cantidad_logistica = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    #lotes = LoteProductoEmbarqueDetailSerializer(many=True, read_only=True)


class VentaDetalleEmbarqueSerializer(serializers.Serializer):
    """Serializer para detalles de venta (productos) en el contexto de embarque"""
    id = serializers.IntegerField(read_only=True)
    producto_id = serializers.IntegerField(source='producto.id', read_only=True)
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    producto_codigo = serializers.CharField(source='producto.codigo', read_only=True)
    unidad_medida = serializers.CharField(source='producto.unidad_sat.nombre', read_only=True, allow_null=True)
    unidad_clave = serializers.CharField(source='producto.unidad_sat.clave', read_only=True, allow_null=True)
    cantidad = serializers.DecimalField(max_digits=20, decimal_places=5, read_only=True)
    cantidad_cargada = serializers.DecimalField(max_digits=20, decimal_places=5, read_only=True)
    cantidad_entregada = serializers.DecimalField(max_digits=20, decimal_places=5, read_only=True)
    cantidad_logistica = serializers.DecimalField(max_digits=20, decimal_places=5, read_only=True)
    is_cargado = serializers.BooleanField(read_only=True)
        
    is_entregado = serializers.BooleanField(read_only=True)
    precio_unitario = serializers.DecimalField(max_digits=20, decimal_places=5, read_only=True)
    subtotal = serializers.DecimalField(max_digits=25, decimal_places=5, read_only=True)


class VentaEmbarqueSerializer(serializers.Serializer):
    """Serializer para ventas dentro de un embarque con sus productos cargados"""
    id = serializers.IntegerField(read_only=True)
    codigo = serializers.CharField(read_only=True)
    cliente_id = serializers.IntegerField(source='cliente.id', read_only=True)
    cliente_nombre = serializers.SerializerMethodField()
    fase = serializers.CharField(read_only=True)
    total = serializers.DecimalField(max_digits=25, decimal_places=2, read_only=True)
    is_entregado = serializers.BooleanField(read_only=True)
    is_total_cargado = serializers.BooleanField(read_only=True)
    condicion_pago = serializers.CharField(read_only=True)
    # Detalles de venta con cantidad, cantidad_entregada
    detalles = serializers.SerializerMethodField()
    # Productos cargados del embarque (referencia)
    productos_cargados = serializers.SerializerMethodField()
    
    def get_cliente_nombre(self, obj):
        if obj.cliente:
            nombre = obj.cliente.nombre or ''
            apellido_paterno = obj.cliente.apellido_paterno or ''
            return f"{nombre} {apellido_paterno}".strip()
        return None
    
    def get_detalles(self, obj):
        """Obtiene los detalles de la venta con cantidad, cantidad_entregada, etc."""
        detalles = obj.detalles.exclude(is_cargado=False).select_related('producto__unidad_sat').all()
        return VentaDetalleEmbarqueSerializer(detalles, many=True).data
    
    def get_productos_cargados(self, obj):
        """Obtiene los productos cargados en el embarque para esta venta"""
        embarque = self.context.get('embarque')
        if not embarque:
            return []
        
        # Filtrar productos del embarque que pertenecen a esta venta
        productos = [p for p in embarque.productos.all() if p.preventa_id == obj.id and p.tipo == 'PEDIDO']
        return ProductoCargadoEmbarqueSerializer(productos, many=True).data


class ProductoEmbarqueDetailSerializer(serializers.Serializer):
    """Serializer para mostrar productos en embarque"""
    id = serializers.IntegerField(read_only=True)
    tipo = serializers.CharField(read_only=True)
    producto_id = serializers.IntegerField(source='producto.id', read_only=True)
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    producto_codigo = serializers.CharField(source='producto.codigo', read_only=True)
    unidad_medida = serializers.CharField(source='producto.unidad_sat.nombre', read_only=True, allow_null=True)
    unidad_clave = serializers.CharField(source='producto.unidad_sat.clave', read_only=True, allow_null=True)
    cantidad = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    cantidad_cargada = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    cantidad_entregada = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    cantidad_logistica = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    preventa_id = serializers.IntegerField(source='preventa.id', read_only=True, allow_null=True)
    preventa_codigo = serializers.CharField(source='preventa.codigo', read_only=True, allow_null=True)
    lotes = LoteProductoEmbarqueDetailSerializer(many=True, read_only=True)


class EmbarqueDetailSerializer(serializers.ModelSerializer):
    """
    Serializer completo para detalle de embarque con productos, lotes y ventas
    """
    ruta_id = serializers.IntegerField(source='ruta.id', read_only=True)
    ruta_nombre = serializers.CharField(source='ruta.nombre', read_only=True)
    ruta_codigo = serializers.CharField(source='ruta.codigo', read_only=True)
    encargado_id = serializers.IntegerField(source='encargado.id', read_only=True, allow_null=True)
    encargado_nombre = serializers.CharField(source='encargado.full_name', read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    created_by_id = serializers.IntegerField(source='created_by.id', read_only=True, allow_null=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True, allow_null=True)
    
    # Todos los productos del embarque
    productos = ProductoEmbarqueDetailSerializer(many=True, read_only=True)
    
    # Ventas del embarque con sus productos cargados
    ventas = serializers.SerializerMethodField()
    
    class Meta:
        model = EmbarqueReparto
        fields = [
            'id',
            'fase',
            'nota',
            'fecha_salida',
            'fecha_finalizada',
            'created_at',
            'created_by_id',
            'created_by_name',
            'ruta_id',
            'ruta_nombre',
            'ruta_codigo',
            'encargado_id',
            'encargado_nombre',
            'productos',
            'ventas',
        ]
    
    def get_ventas(self, obj):
        """Obtiene las ventas del embarque con sus productos cargados (solo si include_ventas=true)"""
        include_ventas = self.context.get('include_ventas', False)
        if not include_ventas:
            return []
        ventas = obj.ventas.all()
        #.exclude(is_entregado=True)
        return VentaEmbarqueSerializer(ventas, many=True, context={'embarque': obj}).data