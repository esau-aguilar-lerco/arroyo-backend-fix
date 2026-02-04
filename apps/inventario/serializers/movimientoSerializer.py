from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone

from django.db.models import Q, F, Sum

from apps.usuarios.models import Usuario
from rest_framework_simplejwt.models import TokenUser


from apps.base.serializer import BaseSerializer, SerializerRelatedField

from apps.erp.models import Producto, Almacen
from apps.inventario.models import (MovimientoInventario, LoteInventario, ProductosMovimiento, Rack)
from ..helpers.movimientoSalida import movimento_inventario
"""
*******************************************************************************************************
                            SERIALIZERS DE MOVIMIENTO SALIDA 
*******************************************************************************************************
"""


"""
==================================================
   *** SERIALIZER PARA LOS PRODUCTOS EN MOVIMIENTO ***
====================================================
"""
class ProductosMovimientoSerializer(serializers.Serializer):
    """
    Serializer para los productos en un movimiento de inventario
    """
    producto = SerializerRelatedField(
        queryset=Producto.objects.filter(status_model=Producto.STATUS_MODEL_ACTIVE),
        required=True,
        allow_null=False,
        help_text="ID o dic con el id del producto"
    )
    cantidad = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01'),
        help_text="Cantidad del producto a mover (debe ser mayor a 0)"
    )
    #lote = SerializerRelatedField(
    #    queryset=LoteInventario.objects.filter(status_model=LoteInventario.STATUS_MODEL_ACTIVE),
    #    required=True,
    #    allow_null=False,
    #    help_text="ID o dic con el id del lote"
    #)

   

"""
====================================================
**SERIALIZER PARA LOS DETALLES DEL PRODUCTOS DE SALIDA**
====================================================
"""
class ProductosMovimientoDetalleSerializer(BaseSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    lote_detalle = serializers.CharField(source='lote', read_only=True)

    class Meta:
        model = ProductosMovimiento
        fields = "__all__"
        # Si quieres mostrar solo ciertos campos, puedes listarlos aquí en vez de "__all__"
        # fields = ["id", "producto", "producto_nombre", "cantidad", "lote", ...]


"""
=====================================================
SERIALIZER PARA LOS DETALLES DEL MOVIMIENTO DE SALIDA
=====================================================

"""
class MovimientoSalidaDetalleSerializer(BaseSerializer):
    """
    Serializer para mostrar el detalle completo de un movimiento de salida
    """
    almacen_salida_nombre = serializers.CharField(source='almacen.nombre', read_only=True)
    almacen_destino_nombre = serializers.CharField(source='almacen_destino.nombre', read_only=True) 
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    #movimiento_display = serializers.CharField(source='get_movimiento_display', read_only=True)
    #fase_display = serializers.CharField(source='get_fase_display', read_only=True)
    #fase = serializers.CharField(source='fase', read_only=True)
    #created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    
    
    # Productos relacionados con el movimiento
    productos_movimiento = ProductosMovimientoDetalleSerializer(many=True, read_only=True, source='productosMovimiento')
    
    class Meta:
        model = MovimientoInventario
        fields = [
            "id", "created_at", "updated_at", "created_by",
            "status_model", "almacen", "almacen_salida_nombre", "almacen_destino", 
            "almacen_destino_nombre", "tipo", "tipo_display", "movimiento", 
            "cantidad", "nota",'referencia',
            'fase',"productos_movimiento"
        ]




"""
======================================================================
---- SERIALIZER PARA LA CREACION DEL MOVIMENTO DE SALIDA (MERMA O TRASPASO) ----
======================================================================
"""

class LotesMovimientoSerializer(serializers.Serializer):
    """
    Serializer para los lotes en un movimiento de inventario
    """
    lote = SerializerRelatedField(
        queryset=LoteInventario.objects.filter(status_model=LoteInventario.STATUS_MODEL_ACTIVE),
        required=True,
        allow_null=False,
        help_text="ID o dic con el id del lote"
    )
    cantidad = serializers.DecimalField(
        max_digits=15,
        decimal_places=5,
        min_value=Decimal('0.01'),
        help_text="Cantidad del lote a mover (debe ser mayor a 0)"
    )
    
class ProductosMovimientoLoteSerializer(serializers.Serializer):
    producto = SerializerRelatedField(
        queryset=Producto.objects.filter(status_model=Producto.STATUS_MODEL_ACTIVE),
        required=True,
        allow_null=False,
        help_text="ID o dic con el id del producto"
    )
    cantidad = serializers.DecimalField(
        max_digits=15,
        decimal_places=5,
        min_value=Decimal('0.01'),
        help_text="Cantidad total del producto a mover (debe ser mayor a 0)"
    )
    lotes = LotesMovimientoSerializer(
        many=True,
        required=True,
        help_text="Lista de lotes para este producto"
    )
class MovimientoSalidaSerializer(serializers.Serializer):
    almacen_origen = SerializerRelatedField(
        queryset=Almacen.objects.filter(status_model=Almacen.STATUS_MODEL_ACTIVE),
        required=False,
        allow_null=True,
        
        help_text="ID o dic con el id del almacén de origen o almacén de la operación, POR DEFECTO SE TOMA EL ALMACÉN DEL USUARIO"
    )

    almacen_destino = SerializerRelatedField(
        queryset=Almacen.objects.filter(status_model=Almacen.STATUS_MODEL_ACTIVE),
        required=False,
        allow_null=True,
        help_text="ID o dic con el id del almacén de destino que recibe el producto (SI ES TRASPASO)"
    )

    nota = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        help_text="Nota adicional sobre el movimiento"
    )

    #tipo = serializers.ChoiceField(
    #    choices=[(MovimientoInventario.SALIDA_TRASPASO, "Traspaso"), (MovimientoInventario.SALIDA_MERMA, "Merma")],
    #    
    #    required=False,
    #    help_text="Tipo de movimiento (salida transferencia)"
    #)
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)

    productos = ProductosMovimientoLoteSerializer(
        many=True,
        required=True,
        help_text="Lista de productos a mover"
    )

    #def validate_productos(self, productos):
    #    """
    #    Validar que cada producto tenga suficiente existencia
    #    """
    #    if not productos:
    #        raise serializers.ValidationError("Debe incluir al menos un producto.")
    #    
    #    # Verificar productos duplicados
    #    productos_ids = [producto['producto'].id for producto in productos]
    #    if len(productos_ids) != len(set(productos_ids)):
    #        raise serializers.ValidationError("No puede incluir el mismo producto múltiples veces.")
    #    
    #    return productos


    def validate(self, attrs):
        """
        Validaciones a nivel de todo el serializer incluyendo existencias
        """
        tipo = attrs.get('tipo')
        almacen_origen = attrs.get('almacen_origen')
        almacen_destino = attrs.get('almacen_destino')
        productos = attrs.get('productos', [])

        # Validar obligatoriedad de almacenes según el tipo de movimiento
        if tipo == MovimientoInventario.SALIDA_TRASPASO:
            if not almacen_destino:
                raise serializers.ValidationError({'detail': 'El almacén de destino es obligatorio para traspasos.'})
            if almacen_origen == almacen_destino:
                raise serializers.ValidationError({'detail': 'Para traspasos, los almacenes de origen y destino deben ser diferentes.'})

        ## VALIDAR EXISTENCIAS EN EL ALMACÉN DE ORIGEN
        #for producto_data in productos:
        #    producto = producto_data['producto']
        #    cantidad_requerida = Decimal(str(producto_data['cantidad']))
        #    
        #    # Verificar cantidad disponible en el almacén de origen
        #    cantidad_disponible = LoteInventario.objects.filter(
        #        producto=producto,
        #        almacen=almacen_origen,
        #        cantidad__gt=0,
        #        status_model=LoteInventario.STATUS_MODEL_ACTIVE
        #    ).aggregate(total_cantidad=Sum('cantidad'))['total_cantidad'] or 0
        #    
        #    cantidad_disponible = Decimal(str(cantidad_disponible)) if cantidad_disponible else Decimal('0')
        #    
        #    # Si no hay suficientes existencias, retornar string simple
        #    if cantidad_disponible < cantidad_requerida:
        #        raise serializers.ValidationError({
        #            'detail': f"No hay suficientes existencias del producto '{producto.nombre}'. "
        #                      f"Disponible: {cantidad_disponible}, Requerido: {cantidad_requerida}"
        #        })
        #        
        #    

        return attrs

    def validate_tipo(self, value):
        """
        Validar el tipo de movimiento.
        """
        if value not in [MovimientoInventario.SALIDA_MERMA, MovimientoInventario.SALIDA_TRASPASO]:
            raise serializers.ValidationError(f"Tipo de movimiento no válido. Debe ser '{MovimientoInventario.SALIDA_MERMA}' o '{MovimientoInventario.SALIDA_TRASPASO}'.")
        return value


    def create(self, validated_data):
        user = self.context.get('user')
        if user is None:
            raise serializers.ValidationError("No se encontró el objeto user en el contexto del serializer.")
        
        if isinstance(user, TokenUser):
            try:
                user = Usuario.objects.get(id=user.id, is_active=True)
            except Usuario.DoesNotExist:
                user = None

        almacen_origen = validated_data['almacen_origen'] 
        almacen_origen = almacen_origen if almacen_origen else user.almacen
        if not almacen_origen:
            raise serializers.ValidationError("El almacén de origen no pudo ser determinado. Por favor, especifíquelo explícitamente.")
        almacen_destino = validated_data['almacen_destino'] if 'almacen_destino' in validated_data else None
        nota = validated_data.get('nota', "")
        sub_movimiento = MovimientoInventario.SALIDA_TRASPASO 
        productos = validated_data['productos']
        lista_productos = productos

        # Guardar el movimiento
        movimiento = movimento_inventario(
            detalle_lotes=lista_productos,
            almacen_salida=almacen_origen,
            almacen_destino=almacen_destino,
            nota=nota,
            sub_movimiento=sub_movimiento,
            user=user
        )

        # Retornar el serializer de detalle
        #return movimiento  cuando usas mixins
        return MovimientoSalidaDetalleSerializer(movimiento).data
    


"""
*******************************************************************************************************
                            SERIALIZERS DE MOVIMIENTO ENTRADA 
*******************************************************************************************************
"""


"""
==============================================================
                SERIALIZERS DE MOVIMIENTO ENTRADA ABASTECIMIENTO
==============================================================
"""



class MovimientoPrincipalResponseSerializer(serializers.Serializer):
    """Serializer para el movimiento principal en la respuesta"""
    id = serializers.IntegerField(help_text="ID del movimiento principal creado")
    referencia = serializers.CharField(help_text="Referencia del movimiento")
    tipo = serializers.CharField(help_text="Tipo de movimiento (TIPO_ENTRADA)")
    movimiento = serializers.CharField(help_text="Subtipo específico (ENTRADA_ABASTECIMIENTO)")
    fase = serializers.CharField(help_text="Fase del movimiento (FASE_TERMINADA)")


class CompraResponseSerializer(serializers.Serializer):
    """Serializer para la información de compra en la respuesta"""
    id = serializers.IntegerField(help_text="ID de la compra", allow_null=True)
    codigo = serializers.CharField(help_text="Código de la compra", allow_null=True)
    estado_actual = serializers.CharField(help_text="Estado actual de la compra", allow_null=True)


class AlmacenDestinoResponseSerializer(serializers.Serializer):
    """Serializer para la información del almacén destino"""
    id = serializers.IntegerField(help_text="ID del almacén destino")
    nombre = serializers.CharField(help_text="Nombre del almacén destino")
    tipo = serializers.CharField(help_text="Tipo de almacén (CEDIS, SUCURSAL, etc.)")


class ResumenAbastecimientoSerializer(serializers.Serializer):
    """Serializer para el resumen del abastecimiento"""
    total_items = serializers.IntegerField(help_text="Número total de items procesados")
    cantidad_total = serializers.FloatField(help_text="Cantidad total de productos abastecidos")
    costo_total = serializers.FloatField(help_text="Costo total del abastecimiento")
    costo_promedio = serializers.FloatField(help_text="Costo promedio por unidad")
    lotes_creados = serializers.IntegerField(help_text="Número total de lotes creados")


class ProductoAbastecidoSerializer(serializers.Serializer):
    """Serializer para cada producto abastecido"""
    producto = serializers.DictField(
        help_text="Información del producto",
        child=serializers.CharField()
    )
    lote_id = serializers.IntegerField(help_text="ID del lote creado")
    cantidad = serializers.FloatField(help_text="Cantidad abastecida")
    costo_unitario = serializers.FloatField(help_text="Costo unitario del producto")
    costo_total = serializers.FloatField(help_text="Costo total del item")
    ubicacion = serializers.CharField(help_text="Ubicación del lote (rack o 'Sin asignar')")


class UsuarioProcesadorSerializer(serializers.Serializer):
    """Serializer para la información del usuario que procesó"""
    id = serializers.IntegerField(help_text="ID del usuario")
    username = serializers.CharField(help_text="Nombre de usuario")


class MetadatosAbastecimientoSerializer(serializers.Serializer):
    """Serializer para metadatos del abastecimiento"""
    referencia = serializers.CharField(help_text="Referencia del abastecimiento")
    nota = serializers.CharField(help_text="Nota adicional del abastecimiento")
    fecha_proceso = serializers.DateTimeField(help_text="Fecha y hora del procesamiento")
    procesado_por = UsuarioProcesadorSerializer(help_text="Usuario que procesó el abastecimiento")


class AbastecimientoResponseSerializer(serializers.Serializer):
    """
    Serializer completo para la respuesta exitosa del abastecimiento
    """
    movimiento_principal = MovimientoPrincipalResponseSerializer(
        help_text="Información del movimiento principal creado"
    )
    compra = CompraResponseSerializer(
        help_text="Información de la compra relacionada",
        allow_null=True
    )
    almacen_destino = AlmacenDestinoResponseSerializer(
        help_text="Información del almacén destino"
    )
    resumen = ResumenAbastecimientoSerializer(
        help_text="Resumen estadístico del abastecimiento"
    )
    productos_abastecidos = ProductoAbastecidoSerializer(
        many=True,
        help_text="Lista detallada de productos abastecidos"
    )
    metadatos = MetadatosAbastecimientoSerializer(
        help_text="Metadatos del proceso de abastecimiento"
    )


class AbastecimientoSuccessResponseSerializer(serializers.Serializer):
    """
    Serializer para la respuesta completa de éxito
    """
    success = serializers.BooleanField(
        default=True,
        help_text="Indica si la operación fue exitosa"
    )
    message = serializers.CharField(
        default="Abastecimiento realizado exitosamente",
        help_text="Mensaje descriptivo del resultado"
    )
    data = AbastecimientoResponseSerializer(
        help_text="Datos detallados del abastecimiento realizado"
    )


class AbastecimientoErrorResponseSerializer(serializers.Serializer):
    """
    Serializer para respuestas de error
    """
    success = serializers.BooleanField(
        default=False,
        help_text="Indica que la operación falló"
    )
    message = serializers.CharField(
        help_text="Mensaje descriptivo del error"
    )
    errors = serializers.DictField(
        help_text="Detalles específicos del error",
        child=serializers.CharField()
    )
class AbastecimientoItemSerializer(serializers.Serializer):
    """
    Serializer para un item individual en el abastecimiento
    """
    producto = SerializerRelatedField(
        queryset=Producto.objects.filter(status_model=Producto.STATUS_MODEL_ACTIVE),
        required=True,
        allow_null=False,
        help_text="ID del producto a abastecer"
    )
    cantidad = serializers.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        min_value=Decimal('0.01'),
        help_text="Cantidad a abastecer (debe ser mayor a 0)"
    )
    #costo_unitario = serializers.DecimalField(
    #    max_digits=10, 
    #    decimal_places=2, 
    #    min_value=Decimal('0.01'),
    #    help_text="Costo unitario del producto"
    #)
    ubicacion_rack = SerializerRelatedField(
        queryset=Rack.objects.filter(status_model=Rack.STATUS_MODEL_ACTIVE),
        required=False,
        allow_null=True,
        help_text="ID del rack donde se ubicará el producto, esto sera obligatorio para almacenes tipo CEDIS"
    )
    #fecha_vencimiento = serializers.DateTimeField(
    #    required=False, 
    #    allow_null=True,
    #    help_text="Fecha de vencimiento del producto (opcional)"
    #)
   

class MovimientoEntradaAbastecimientoSerializer(serializers.Serializer):
    #COMPRA ID
    compra = serializers.IntegerField(required=True, help_text="ID de la compra relacionada al abastecimiento")

    #almacen = SerializerRelatedField(
    #    queryset=Almacen.objects.filter(status_model=Almacen.STATUS_MODEL_ACTIVE),
    #    required=True,
    #    allow_null=False,
    #    help_text="ID del almacén donde se realizará el abastecimiento"
    #)
    items = AbastecimientoItemSerializer(
        many=True, 
        required=True,
        help_text="Lista de productos a abastecer"
    )
    #referencia = serializers.CharField(
    #    max_length=150,
    #    required=False,
    #    allow_blank=True,
    #    help_text="Referencia del abastecimiento (ej: número de orden de compra)"
    #)
    nota = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Notas adicionales sobre el abastecimiento"
    )


"""
==============================================================
                SERIALIZERS DE MOVIMIENTO ENTRADA TRASPASO
==============================================================
"""

class MovimientoEntradaTraspasoSerializer(serializers.Serializer):
    movimiento = SerializerRelatedField(
        queryset=MovimientoInventario.objects.filter(
            #tipo=MovimientoInventario.SALIDA_TRASPASO,
            status_model=MovimientoInventario.STATUS_MODEL_ACTIVE
        ),
        required=True,
        allow_null=False,
        help_text="ID del movimiento de salida por traspaso"
    )




















 


class AbastecimientoItemSerializer_(serializers.Serializer):
    """
    Serializer para un item individual en el abastecimiento
    """
    producto = SerializerRelatedField(
        queryset=Producto.objects.filter(status_model=Producto.STATUS_MODEL_ACTIVE),
        required=True,
        allow_null=False,
        help_text="ID del producto a abastecer"
    )
    cantidad = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        min_value=Decimal('0.01'),
        help_text="Cantidad a abastecer (debe ser mayor a 0)"
    )
    costo_unitario = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        min_value=Decimal('0.01'),
        help_text="Costo unitario del producto"
    )
    fecha_vencimiento = serializers.DateTimeField(
        required=False, 
        allow_null=True,
        help_text="Fecha de vencimiento del producto (opcional)"
    )
   

    def validate(self, attrs):
        """
        Validar que si se especifica una ubicación, sea del mismo almacén
        """
        ubicacion = attrs.get('ubicacion')
        if ubicacion and hasattr(self.context, 'almacen'):
            almacen = self.context['almacen']
            if ubicacion.rack.zona.piso.almacen != almacen:
                raise serializers.ValidationError({
                    'ubicacion': 'La ubicación debe pertenecer al mismo almacén'
                })
        return attrs


class LoteInventarioSerializer(BaseSerializer):
    """
    Serializer para mostrar los lotes de inventario
    """
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    almacen_nombre = serializers.CharField(source='almacen.nombre', read_only=True)
    ubicacion_completa = serializers.SerializerMethodField()
    valor_total = serializers.SerializerMethodField()

    class Meta:
        model = LoteInventario
        fields = [
            "id", "created_at", "updated_at", "created_by", "updated_by",
            "status_model", "producto", "producto_nombre", "almacen", "almacen_nombre",
            "ubicacion", "ubicacion_completa", "cantidad", "costo_unitario", "valor_total",
            "fecha_ingreso", "fecha_vencimiento"
        ]

    def get_ubicacion_completa(self, obj):
        """Obtener la descripción completa de la ubicación"""
        if obj.ubicacion:
            return str(obj.ubicacion)
        return None

    def get_valor_total(self, obj):
        """Calcular el valor total del lote"""
        return obj.cantidad * obj.costo_unitario if obj.cantidad and obj.costo_unitario else 0
