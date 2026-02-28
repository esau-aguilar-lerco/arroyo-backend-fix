from rest_framework import serializers
from apps.erp.models import Venta, Almacen, Rutas, Producto, CajaApertura, CajaTransaccion
from apps.erp.models import VentaDetalle
from apps.inventario.models import LoteInventario, EmbarqueReparto, ProductoEmbarque
from apps.base.serializer import FlexiblePKRelatedField, SerializerRelatedField
from apps.base.models import BaseModel
from django.db.models import Sum, Count
from django.db.models import Q
from decimal import Decimal, InvalidOperation
import re

from apps.erp.helpers.embarque import crear_movimiento_inventario_almacen_embarque
from apps.contabilidad.models import MetodoPago


_CREDITO_ID_REGEX = re.compile(r"cr[eé]dito\s*id\s*(\d+)", re.IGNORECASE)


def _extraer_credito_id(descripcion):
    if not descripcion:
        return None
    match = _CREDITO_ID_REGEX.search(str(descripcion))
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None


def _abonos_detalle_desde_qs(abonos_qs):
    """
    Devuelve el detalle completo de abonos de caja para cortes de reparto.
    Incluye quién abonó, método, referencia y contexto del crédito/cliente.
    """
    from apps.credito.models import CreditoCliente

    transacciones = list(
        abonos_qs.select_related('metodo_pago', 'created_by').order_by('-created_at', '-id')
    )
    credito_ids = {
        credito_id
        for credito_id in (_extraer_credito_id(tx.descripcion) for tx in transacciones)
        if credito_id is not None
    }

    creditos_map = {}
    if credito_ids:
        creditos_map = {
            credito.id: credito
            for credito in CreditoCliente.objects.select_related('cliente').filter(id__in=credito_ids)
        }

    detalle = []
    for tx in transacciones:
        credito_id = _extraer_credito_id(tx.descripcion)
        credito = creditos_map.get(credito_id)
        cliente = credito.cliente if credito else None

        detalle.append({
            'transaccion_id': tx.id,
            'created_at': tx.created_at,
            'created_by_id': tx.created_by_id,
            'created_by_nombre': tx.created_by.full_name() if tx.created_by else '',
            'tipo': tx.tipo,
            'monto': tx.monto,
            'metodo_pago_id': tx.metodo_pago_id,
            'metodo_pago_nombre': tx.metodo_pago.nombre if tx.metodo_pago else '',
            'referencia': tx.referencia,
            'descripcion': tx.descripcion,
            'credito_id': credito.id if credito else credito_id,
            'credito_estado': credito.estado if credito else None,
            'credito_fecha_vencimiento': credito.fecha_vencimiento if credito else None,
            'credito_monto': credito.monto if credito else None,
            'credito_monto_pagado': credito.monto_pagado if credito else None,
            'credito_adeudo': credito.adeudo_actual() if credito else None,
            'cliente_id': cliente.id if cliente else None,
            'cliente_codigo': cliente.codigo if cliente else None,
            'cliente_nombre': cliente.get_full_name if cliente else None,
        })
    return detalle


def _categoria_metodo_abono(metodo_nombre):
    nombre = (metodo_nombre or '').upper()
    if 'TRANSFER' in nombre:
        return 'transferencia'
    if 'CHEQUE' in nombre:
        return 'cheque'
    if 'DEPOSITO' in nombre or 'DEPÓSITO' in nombre:
        return 'deposito'
    return 'otros'


def _resumen_abonos_por_credito(abonos_detalle):
    """
    Resumen tabular para impresión de corte:
    crédito, cliente, transferencia, cheque, deposito, otros, abono y saldo.
    """
    agrupado = {}
    for row in abonos_detalle:
        credito_id = row.get('credito_id')
        key = credito_id or f"tx-{row.get('transaccion_id')}"
        bucket = agrupado.setdefault(key, {
            'credito_id': credito_id,
            'cliente_id': row.get('cliente_id'),
            'cliente_codigo': row.get('cliente_codigo'),
            'cliente_nombre': row.get('cliente_nombre'),
            'transferencia': Decimal('0.00'),
            'cheque': Decimal('0.00'),
            'deposito': Decimal('0.00'),
            'otros': Decimal('0.00'),
            'abono_total': Decimal('0.00'),
            'saldo': row.get('credito_adeudo'),
            'movimientos': [],
        })

        monto = Decimal(str(row.get('monto') or 0))
        categoria = _categoria_metodo_abono(row.get('metodo_pago_nombre'))
        bucket[categoria] += monto
        bucket['abono_total'] += monto
        if row.get('credito_adeudo') is not None:
            bucket['saldo'] = row.get('credito_adeudo')
        bucket['movimientos'].append({
            'transaccion_id': row.get('transaccion_id'),
            'created_at': row.get('created_at'),
            'created_by_id': row.get('created_by_id'),
            'created_by_nombre': row.get('created_by_nombre'),
            'monto': row.get('monto'),
            'metodo_pago_id': row.get('metodo_pago_id'),
            'metodo_pago_nombre': row.get('metodo_pago_nombre'),
            'referencia': row.get('referencia'),
            'descripcion': row.get('descripcion'),
        })

    return sorted(
        agrupado.values(),
        key=lambda item: (
            item.get('cliente_nombre') or '',
            item.get('credito_id') or 0,
        ),
    )


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
    cantidad = serializers.DecimalField(max_digits=20, decimal_places=5, help_text="Cantidad del producto")
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
    auto_iniciar_reparto = serializers.BooleanField(
        required=False,
        default=True,
        help_text="Si es true (default), al finalizar checkin cambia fase a REPARTO. Si es false, conserva PROGRAMADO."
    )

   
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

        embarque_abierto = (
            EmbarqueReparto.objects
            .filter(
                ruta=ruta,
                status_model=BaseModel.STATUS_MODEL_ACTIVE,
                fase__in=EmbarqueReparto.fases_programado_compat(),
            )
            .order_by('-id')
            .first()
        )
        if embarque_abierto:
            raise serializers.ValidationError(
                f"La ruta {ruta.codigo if ruta else ''} ya tiene un embarque programado "
                f"(ID {embarque_abierto.id}, fase {embarque_abierto.fase})."
            )

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
    fase = serializers.SerializerMethodField()
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

    def get_fase(self, obj):
        # Para la app/web de reparto, una venta entregada debe mostrarse como TERMINADA.
        return Venta.FASE_TERMINADA if getattr(obj, 'is_entregado', False) else obj.fase
    
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
    cantidad = serializers.SerializerMethodField()
    precio_unitario = serializers.SerializerMethodField()
    cantidad_cargada = serializers.SerializerMethodField()
    cantidad_entregada = serializers.SerializerMethodField()
    cantidad_logistica = serializers.SerializerMethodField()
    preventa_id = serializers.IntegerField(source='preventa.id', read_only=True, allow_null=True)
    preventa_codigo = serializers.CharField(source='preventa.codigo', read_only=True, allow_null=True)
    lotes = LoteProductoEmbarqueDetailSerializer(many=True, read_only=True)

    def _to_decimal(self, value, decimal_places=3):
        if value is None:
            return Decimal('0.000' if decimal_places == 3 else '0.00')
        try:
            number = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return Decimal('0.000' if decimal_places == 3 else '0.00')
        quant = Decimal('0.001' if decimal_places == 3 else '0.01')
        return number.quantize(quant)

    def _first_positive_decimal(self, values, decimal_places=3):
        for value in values:
            number = self._to_decimal(value, decimal_places=decimal_places)
            if number > 0:
                return number
        return self._to_decimal(0, decimal_places=decimal_places)

    def _get_venta_detalle(self, obj):
        if obj.tipo != ProductoEmbarque.PEDIDO or not obj.preventa_id:
            return None

        cache = self.context.setdefault('_venta_detalle_cache', {})
        key = (obj.preventa_id, obj.producto_id)
        if key in cache:
            return cache[key]

        detalle = None
        preventa = getattr(obj, 'preventa', None)
        if preventa is not None and hasattr(preventa, 'detalles'):
            detalle = next(
                (d for d in preventa.detalles.all() if d.producto_id == obj.producto_id),
                None
            )

        if detalle is None:
            detalle = (
                VentaDetalle.objects
                .filter(venta_id=obj.preventa_id, producto_id=obj.producto_id)
                .only(
                    'cantidad',
                    'cantidad_logistica',
                    'cantidad_cargada',
                    'cantidad_entregada',
                    'precio_unitario'
                )
                .first()
            )

        cache[key] = detalle
        return detalle

    def get_cantidad(self, obj):
        if obj.tipo == ProductoEmbarque.PEDIDO:
            detalle = self._get_venta_detalle(obj)
            if detalle is not None:
                return self._first_positive_decimal([
                    detalle.cantidad_logistica,
                    detalle.cantidad_cargada,
                    detalle.cantidad,
                    obj.cantidad,
                ], decimal_places=3)

        lotes_total = obj.lotes.aggregate(total=Sum('cantidad')).get('total')
        return self._first_positive_decimal([obj.cantidad, lotes_total], decimal_places=3)

    def get_precio_unitario(self, obj):
        detalle = self._get_venta_detalle(obj)
        producto = getattr(obj, 'producto', None)
        precio_menudeo = None
        precio_costo = None
        if producto is not None:
            try:
                precio_menudeo = producto.get_precio_menudeo()
            except Exception:
                precio_menudeo = None
            try:
                precio_costo = producto.get_costo_arroyo()
            except Exception:
                precio_costo = None
        return self._first_positive_decimal([
            obj.precio_unitario,
            getattr(detalle, 'precio_unitario', None),
            precio_menudeo,
            precio_costo,
        ], decimal_places=2)

    def get_cantidad_cargada(self, obj):
        detalle = self._get_venta_detalle(obj)
        if detalle is None:
            return self._to_decimal(0, decimal_places=3)
        return self._to_decimal(detalle.cantidad_cargada, decimal_places=3)

    def get_cantidad_entregada(self, obj):
        detalle = self._get_venta_detalle(obj)
        if detalle is None:
            return self._to_decimal(0, decimal_places=3)
        return self._to_decimal(detalle.cantidad_entregada, decimal_places=3)

    def get_cantidad_logistica(self, obj):
        detalle = self._get_venta_detalle(obj)
        if detalle is None:
            return self._to_decimal(0, decimal_places=3)
        return self._to_decimal(detalle.cantidad_logistica, decimal_places=3)


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
    total_ventas = serializers.SerializerMethodField()
    total_cobrado_ventas = serializers.SerializerMethodField()
    total_abonos = serializers.SerializerMethodField()
    total_abonos_efectivo = serializers.SerializerMethodField()
    recibio_abono = serializers.SerializerMethodField()
    abonos_detalle = serializers.SerializerMethodField()
    abonos_resumen_credito = serializers.SerializerMethodField()
    abonos_por_metodo = serializers.SerializerMethodField()
    formas_pago = serializers.SerializerMethodField()
    total_ventas_formas_pago = serializers.SerializerMethodField()
    total_abonos_formas_pago = serializers.SerializerMethodField()
    total_general_formas_pago = serializers.SerializerMethodField()
    
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
            'total_ventas',
            'total_cobrado_ventas',
            'total_abonos',
            'total_abonos_efectivo',
            'recibio_abono',
            'abonos_detalle',
            'abonos_resumen_credito',
            'abonos_por_metodo',
            'formas_pago',
            'total_ventas_formas_pago',
            'total_abonos_formas_pago',
            'total_general_formas_pago',
        ]

    def _ventas_queryset(self, obj):
        cache = self.context.setdefault('_ventas_cache', {})
        if obj.id in cache:
            return cache[obj.id]

        qs = obj.ventas.exclude(
            status_model=Venta.STATUS_MODEL_DELETE
        ).exclude(
            fase=Venta.FASE_CANCELADA
        )
        cache[obj.id] = qs
        return qs

    def _abonos_queryset(self, obj):
        """
        Abonos capturados en la caja del embarque/reparto (cash operativo de ruta).
        """
        cache = self.context.setdefault('_abonos_cache', {})
        if obj.id in cache:
            return cache[obj.id]

        apertura_caja = getattr(obj, 'apertura_caja', None)
        if not apertura_caja:
            qs = CajaTransaccion.objects.none()
        else:
            qs = CajaTransaccion.objects.filter(
                caja_apertura=apertura_caja,
                status_model=BaseModel.STATUS_MODEL_ACTIVE,
                tipo=CajaTransaccion.TIPO_ENTRADA,
            ).filter(
                Q(descripcion__icontains='Pago de crédito ID') |
                Q(descripcion__icontains='Pago de credito ID')
            ).select_related('metodo_pago', 'created_by')
        cache[obj.id] = qs
        return qs

    def _ventas_transacciones_queryset(self, obj):
        cache = self.context.setdefault('_ventas_transacciones_cache', {})
        if obj.id in cache:
            return cache[obj.id]

        apertura_caja = getattr(obj, 'apertura_caja', None)
        if not apertura_caja:
            qs = CajaTransaccion.objects.none()
        else:
            qs = CajaTransaccion.objects.filter(
                caja_apertura=apertura_caja,
                status_model=BaseModel.STATUS_MODEL_ACTIVE,
                tipo=CajaTransaccion.TIPO_ENTRADA,
                descripcion__icontains='Pago de venta',
            )
        cache[obj.id] = qs
        return qs

    def _formas_pago_rows(self, obj):
        cache = self.context.setdefault('_formas_pago_rows_cache', {})
        if obj.id in cache:
            return cache[obj.id]

        metodos = list(
            MetodoPago.objects.filter(activo=True).values('id', 'nombre').order_by('nombre')
        )
        ventas_rows = self._ventas_transacciones_queryset(obj).values('metodo_pago_id').annotate(
            monto_total=Sum('monto')
        )
        abonos_rows = self._abonos_queryset(obj).values('metodo_pago_id').annotate(
            monto_total=Sum('monto')
        )

        ventas_map = {
            row['metodo_pago_id']: (row['monto_total'] or Decimal('0.00'))
            for row in ventas_rows
        }
        abonos_map = {
            row['metodo_pago_id']: (row['monto_total'] or Decimal('0.00'))
            for row in abonos_rows
        }

        rows = []
        for metodo in metodos:
            ventas_total = Decimal(str(ventas_map.get(metodo['id'], Decimal('0.00'))))
            abonos_total = Decimal(str(abonos_map.get(metodo['id'], Decimal('0.00'))))
            rows.append({
                'metodo_pago_id': metodo['id'],
                'metodo_pago_nombre': metodo['nombre'],
                'ventas': ventas_total,
                'abonos': abonos_total,
                'total': ventas_total + abonos_total,
            })

        cache[obj.id] = rows
        return rows
    
    def get_ventas(self, obj):
        """Obtiene las ventas del embarque con sus productos cargados (solo si include_ventas=true)"""
        include_ventas = self.context.get('include_ventas', False)
        if not include_ventas:
            return []
        ventas = self._ventas_queryset(obj)
        #.exclude(is_entregado=True)
        return VentaEmbarqueSerializer(ventas, many=True, context={'embarque': obj}).data

    def get_total_ventas(self, obj):
        total = self._ventas_queryset(obj).aggregate(t=Sum('total')).get('t') or Decimal('0.00')
        return total

    def get_total_cobrado_ventas(self, obj):
        total = self._ventas_queryset(obj).aggregate(t=Sum('total_pagado')).get('t') or Decimal('0.00')
        return total

    def get_total_abonos(self, obj):
        total = self._abonos_queryset(obj).aggregate(t=Sum('monto')).get('t') or Decimal('0.00')
        return total

    def get_total_abonos_efectivo(self, obj):
        total = self._abonos_queryset(obj).filter(
            metodo_pago__nombre__iexact='EFECTIVO'
        ).aggregate(t=Sum('monto')).get('t') or Decimal('0.00')
        return total

    def get_recibio_abono(self, obj):
        return self._abonos_queryset(obj).exists()

    def get_abonos_detalle(self, obj):
        return _abonos_detalle_desde_qs(self._abonos_queryset(obj))

    def get_abonos_resumen_credito(self, obj):
        return _resumen_abonos_por_credito(self.get_abonos_detalle(obj))

    def get_abonos_por_metodo(self, obj):
        rows = self._abonos_queryset(obj).values('metodo_pago_id', 'metodo_pago__nombre').annotate(
            monto_total=Sum('monto'),
            cantidad_pagos=Count('id'),
        )
        base = {
            row['metodo_pago_id']: {
                'metodo_pago_id': row['metodo_pago_id'],
                'metodo_pago_nombre': row['metodo_pago__nombre'],
                'monto_total': row['monto_total'] or Decimal('0.00'),
                'cantidad_pagos': row['cantidad_pagos'] or 0,
            }
            for row in rows
        }

        # Completar métodos no usados con cero para no romper UI de reportes.
        salida = []
        for row in self._formas_pago_rows(obj):
            metodo_id = row['metodo_pago_id']
            data = base.get(metodo_id, None)
            if not data:
                data = {
                    'metodo_pago_id': metodo_id,
                    'metodo_pago_nombre': row['metodo_pago_nombre'],
                    'monto_total': Decimal('0.00'),
                    'cantidad_pagos': 0,
                }
            salida.append(data)
        return salida

    def get_formas_pago(self, obj):
        return self._formas_pago_rows(obj)

    def get_total_ventas_formas_pago(self, obj):
        return sum((row['ventas'] for row in self._formas_pago_rows(obj)), Decimal('0.00'))

    def get_total_abonos_formas_pago(self, obj):
        return sum((row['abonos'] for row in self._formas_pago_rows(obj)), Decimal('0.00'))

    def get_total_general_formas_pago(self, obj):
        return sum((row['total'] for row in self._formas_pago_rows(obj)), Decimal('0.00'))
