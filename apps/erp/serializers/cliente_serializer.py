from rest_framework import serializers
from rest_framework.validators import UniqueValidator, UniqueTogetherValidator
from drf_spectacular.utils import extend_schema_field
from django.db import models
from django.core.cache import cache
from functools import wraps

# Import models
from ..models import  Cliente, DireccionCliente, Venta, VentaDetalle, CategoriaCliente
from apps.direccion.models import Estado, Municipio, CodigoPostal, Colonia

#SERIALIZERS
from apps.usuarios.serializers.usuarios import UsuarioMiniSerializer, UsuarioDetalleSerializer
from apps.direccion.serializers.direccion_serializer import (
    EstadoSerializer,
    MunicipioSerializer,
    CodigoPostalSerializer,
    ColoniaSerializer
)
from apps.base.serializer import BaseSerializer , SerializerRelatedField
from apps.contabilidad.serializers.regimenSerializer import RegimenFiscalDetailSerializer


def cache_cliente_data(timeout=300):  # 5 minutos de caché
    """
    Decorador para cachear datos pesados de cliente
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, obj):
            cache_key = f"cliente_{obj.id}_{func.__name__}_v2"
            cached_data = cache.get(cache_key)
            
            if cached_data is not None:
                return cached_data
            
            result = func(self, obj)
            cache.set(cache_key, result, timeout)
            return result
        return wrapper
    return decorator



class DireccionClienteSerializer(serializers.ModelSerializer):
    # Mostrar solo IDs en escritura
    #usuario = serializers.PrimaryKeyRelatedField(queryset=Usuario.objects.all())
    estado = serializers.PrimaryKeyRelatedField(queryset=Estado.objects.all(), allow_null=True, help_text="ID del estado")
    municipio = serializers.PrimaryKeyRelatedField(queryset=Municipio.objects.all(), allow_null=True, help_text="ID del municipio")
    codigo_postal = serializers.PrimaryKeyRelatedField(queryset=CodigoPostal.objects.all(), allow_null=True, help_text="ID del código postal")
    colonia = serializers.PrimaryKeyRelatedField(queryset=Colonia.objects.all(), allow_null=True, help_text="ID de la colonia")

    # Campos anidados solo lectura (útil en GET)
    estado_name =  serializers.StringRelatedField(source='estado', read_only=True, help_text="Nombre del estado")
    municipio_name = serializers.StringRelatedField(source='municipio', read_only=True, help_text="Nombre del municipio")
    codigo_postal_name = serializers.StringRelatedField(source='codigo_postal', read_only=True, help_text="Código postal")
    colonia_name = serializers.StringRelatedField(source='colonia', read_only=True, help_text="Nombre de la colonia")


    class Meta:
        model = DireccionCliente
        fields = [
            'id',
            'estado', 'estado_name',
            'municipio', 'municipio_name',
            'codigo_postal', 'codigo_postal_name',
            'colonia', 'colonia_name',
            'calle', 'numero_exterior', 'numero_interior',
            'latitud', 'longitud'
        ]
        extra_kwargs = {
            'calle': {'help_text': 'Nombre de la calle'},
            'numero_exterior': {'help_text': 'Número exterior del domicilio'},
            'numero_interior': {'help_text': 'Número interior del domicilio (opcional)'},
            'latitud': {'help_text': 'Latitud de la dirección (opcional)'},
            'longitud': {'help_text': 'Longitud de la dirección (opcional)'}
        }

class DireccionClienteObjSerializer(serializers.ModelSerializer):
    estado = EstadoSerializer(read_only=True)
    municipio = MunicipioSerializer(read_only=True)
    codigo_postal = CodigoPostalSerializer(read_only=True)
    colonia = ColoniaSerializer(read_only=True)
    class Meta:
        model = DireccionCliente
        fields = [
            'id',
            'calle', 'numero_exterior', 'numero_interior',
            'estado', 'municipio', 'codigo_postal', 'colonia',
            'latitud', 'longitud'

        ]
        read_only_fields = ('id','calle', 'numero_exterior', 'numero_interior',)

class ClienteCreditoSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado para mostrar información del cliente en contexto de créditos
    """
    nombre_completo = serializers.SerializerMethodField(read_only=True)
    puede_pagar_credito = serializers.SerializerMethodField(read_only=True)
    disponible_credito = serializers.SerializerMethodField(read_only=True)
    
    
    class Meta:
        model = Cliente
        fields = [
            'id', 
            'codigo',
            'nombre_completo',
            'razon_social', 
            'rfc', 
            'telefono',
            'email',
            'sujeto_credito',
            'limite_credito', 
            'total_credito',
            'disponible_credito',
            'plazos_semanas', 
            'puede_pagar_credito'
        ]
        read_only_fields = fields  # Todos los campos son de solo lectura
    
    def get_nombre_completo(self, obj):
        """Retorna el nombre completo del cliente"""
        return obj.nombre_completo
    
    def get_puede_pagar_credito(self, obj):
        """Verifica si el cliente puede pagar a crédito"""
        return obj.puede_pagar_credito()
    
    def get_disponible_credito(self, obj):
        """Calcula el crédito disponible del cliente"""
        if not obj.sujeto_credito:
            return 0.0
       
        usado = obj.total_credito or 0.0
        return usado
    
    
class ClienteSerializer(BaseSerializer):
    limite_credito = serializers.FloatField(required=False, default=0.0, allow_null=True)
    total_credito = serializers.FloatField(required=False, default=0.0, read_only=True)
    plazos_semanas = serializers.IntegerField(required=False, default=0,allow_null=True)
    clasificacion = SerializerRelatedField(
        required=False,
        
        queryset=CategoriaCliente.objects.filter(status_model=CategoriaCliente.STATUS_MODEL_ACTIVE),
        help_text="ID de la clasificación del cliente o diccionario {'id': <pk>}"
    )
    tipo = serializers.ChoiceField(
        choices=Cliente.TIPO_LIST,
        default=Cliente.TIPO_ESTANDAR,
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Tipo de cliente"
    )

    precio_tipo = serializers.ChoiceField(
        choices=Cliente.TIPO_PRECIO_CHOICES,
        default=Cliente.PUBLICO,
        required=False,
        allow_null=True,  # ✅ Permitir null
        allow_blank=True,
        help_text="Tipo de precio"
    )
    clasificacion_name = serializers.SerializerMethodField(read_only=True, help_text="Nombre de la clasificación del cliente")
    vendedor = SerializerRelatedField(
        queryset=UsuarioMiniSerializer.Meta.model.objects.all(),
        allow_null=True,
        help_text="ID del vendedor asignado al cliente o diccionario {'id': <pk>}"
    )
    vendedor_name = serializers.CharField(source='vendedor.full_name', read_only=True, help_text="Nombre del vendedor")
    vendedor_detalle = UsuarioDetalleSerializer(read_only=True, source='vendedor', help_text="Detalle del vendedor asignado al cliente")

    direccion = DireccionClienteSerializer(many=True, required=False, allow_null=True, help_text="Direcciones asociadas al cliente",source='direccion_cliente')
    direccion_obj = serializers.SerializerMethodField(read_only=True)

    regimen_fiscal = SerializerRelatedField(
        queryset=RegimenFiscalDetailSerializer.Meta.model.objects.all(),
        help_text="ID del régimen fiscal del cliente o diccionario {'id': <pk>}"
    )
    regimen_fiscal_detalle = RegimenFiscalDetailSerializer(read_only=True, source='regimen_fiscal', help_text="Detalle del régimen fiscal del cliente")

    nombre_completo = serializers.SerializerMethodField(read_only=True, help_text="Nombre completo del cliente")

    puede_pagar_credito = serializers.SerializerMethodField(read_only=True, help_text="Indica si el cliente puede realizar pagos a crédito")

    def get_puede_pagar_credito(self, obj):
        # Lógica para determinar si el cliente puede pagar a crédito
        return obj.puede_pagar_credito()

    def get_clasificacion_name(self, obj):
        return obj.clasificacion.nombre if obj.clasificacion else None

    # Override para validar unicidad de RFC
    rfc = serializers.CharField(
        allow_blank=False,
        allow_null=False,
        validators=[
            UniqueValidator(
                queryset=Cliente.objects.all(),
                message="El RFC ya existe."
            )
        ],
        help_text="RFC del cliente",
        required=True
    )

    class Meta:
        model = Cliente
        fields = '__all__'
        read_only_fields = (
            'created_at', 'updated_at', 'created_by', 'updated_by',
            'status_model', 'vendedor_obj', 'vendedor_name', 'total_credito', 'codigo'
        )
        validators = [
            UniqueTogetherValidator(
                queryset=Cliente.objects.all(),
                fields=['nombre', 'apellido_paterno', 'apellido_materno'],
                message="El nombre completo ya existe."
            )
        ]
    def get_puede_pagar_credito(self, obj):
        # Lógica para determinar si el cliente puede pagar a crédito
        return obj.puede_pagar_credito()

    def create(self, validated_data):
        """
        Crear almacén con sus direcciones
        """
        # Extraer las direcciones de los datos validados
        direcciones_data = validated_data.pop('direccion_cliente', [])
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            validated_data['created_by_id'] = request.user.id

        # Crear el almacén sin las direcciones
        cliente = Cliente.objects.create(**validated_data)

        # Crear las direcciones y asociarlas al cliente
        for direccion_data in direcciones_data:
            DireccionCliente.objects.create(cliente=cliente, **direccion_data)

        return cliente

    def update(self, instance, validated_data):
        """
        Actualizar cliente y sus direcciones
        """
        # Extraer las direcciones de los datos validados
        direcciones_data = validated_data.pop('direccion_cliente', None)

        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            validated_data['updated_by_id'] = request.user.id

        # Actualizar los campos del cliente 
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Si se proporcionaron direcciones, reemplazar las existentes
        if direcciones_data is not None:
            # Eliminar direcciones existentes
            instance.direccion_cliente.all().delete()  # Ajusta 'direcciones' según tu related_name

            # Crear nuevas direcciones
            for direccion_data in direcciones_data:
                DireccionCliente.objects.create(cliente=instance, **direccion_data)

        return instance
    
    @extend_schema_field(DireccionClienteObjSerializer(many=True))
    def get_direccion_obj(self, obj):
        if hasattr(obj, 'direccion_principal') and obj.direccion_principal:
            return DireccionClienteObjSerializer(obj.direccion_principal).data
        return None

    def get_nombre_completo(self, obj):
        return obj.nombre_completo

    def validate(self, attrs):

        # ✅ Asegurar valores por defecto para campos críticos
        if attrs.get('tipo') in [None, "", "null"]:
            attrs['tipo'] = Cliente.TIPO_ESTANDAR
            
        if attrs.get('precio_tipo') in [None, "", "null"]:
            attrs['precio_tipo'] = Cliente.PUBLICO
            
        if attrs.get('limite_credito') in [None, ""]:
            attrs['limite_credito'] = 0.0
            
        if attrs.get('plazos_semanas') in [None, ""]:
            attrs['plazos_semanas'] = 0
        # Normalizar valores entrantes o existentes
        nombre = (attrs.get('nombre') or getattr(self.instance, 'nombre', '')).strip().upper()
        ap = (attrs.get('apellido_paterno') or getattr(self.instance, 'apellido_paterno', '')).strip().upper()
        am = (attrs.get('apellido_materno') or getattr(self.instance, 'apellido_materno', '')).strip().upper()
        # Excluir el registro actual en caso de update
        qs = Cliente.objects.filter(
            nombre=nombre,
            apellido_paterno=ap,
            apellido_materno=am
        )
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError({
                'nombre_completo': 'El nombre completo ya existe.'
            })
        return attrs






class ClienteMiniSerializer(serializers.ModelSerializer):
    get_full_name = serializers.ReadOnlyField()
    class Meta:
        model = Cliente
        fields = ['id',  'get_full_name', 'rfc', 'telefono', 'email', 'nombre', 'razon_social']


class InformacionClienteSerializer(serializers.ModelSerializer):
    """
    Serializer optimizado para información completa del cliente con sus últimas compras
    """
    # Especificar tipos explícitos para campos que vienen del modelo
    get_full_name = serializers.CharField(read_only=True)
    
    limite_credito = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_credito = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    # Campos calculados con documentación mejorada
    #direccion_principal = serializers.SerializerMethodField()
    ultimos_productos_comprados = serializers.SerializerMethodField()
    ventas_recientes = serializers.SerializerMethodField()
    productos_favoritos = serializers.SerializerMethodField()
    adeudo = serializers.SerializerMethodField()
    total_ventas = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Optimizar consultas si es una instancia específica
        if self.instance and not isinstance(self.instance, list):
            self._optimizar_consultas()
    
    def _optimizar_consultas(self):
        """
        Pre-cargar datos relacionados para optimizar las consultas
        """
        cliente = self.instance
        
        # Prefetch de direcciones con sus relaciones
        if not hasattr(cliente, '_direcciones_precargadas'):
            cliente._direcciones_precargadas = list(
                cliente.direccion_cliente.select_related(
                    'estado', 'municipio', 'codigo_postal', 'colonia'
                ).all()
            )
        
        # Prefetch de ventas terminadas con productos
        if not hasattr(cliente, '_ventas_terminadas'):
            cliente._ventas_terminadas = list(
                cliente.ventas.filter(fase=Venta.FASE_TERMINADA)
                .select_related()
                .prefetch_related('detalles__producto')
                .order_by('-created_at')[:50]  # Solo las últimas 50 para optimizar
            )
        
        # Pre-calcular estadísticas de ventas
        if not hasattr(cliente, '_estadisticas_ventas'):
            ventas_terminadas = cliente._ventas_terminadas
            total_ventas = len(ventas_terminadas)
            monto_total = sum(venta.total for venta in ventas_terminadas)
            
            cliente._estadisticas_ventas = {
                'cantidad_ventas': total_ventas,
                'monto_total': monto_total,
                'promedio_venta': monto_total / total_ventas if total_ventas > 0 else 0
            }
        
        # Pre-calcular productos favoritos
        if not hasattr(cliente, '_productos_favoritos'):
            productos_favoritos = VentaDetalle.objects.filter(
                venta__cliente=cliente,
                venta__fase__in=[Venta.FASE_TERMINADA, Venta.FASE_CANCELADA, Venta.FASE_PRE_VENTA]
            ).values(
                'producto_id', 'producto__codigo', 'producto__nombre'
            ).annotate(
                total_cantidad=models.Sum('cantidad'),
                veces_comprado=models.Count('venta_id', distinct=True)
            ).order_by('-total_cantidad')[:10]
            
            cliente._productos_favoritos = list(productos_favoritos)
    
    class Meta:
        model = Cliente
        fields = [
            'id', 'codigo', 'get_full_name', 'nombre', 'apellido_paterno', 'apellido_materno',
            'razon_social', 'tipo_persona', 'telefono', 'email', 'rfc', 'tipo',
            'limite_credito', 'total_credito', #'direccion_principal',
            'ultimos_productos_comprados', 'adeudo', 'total_ventas', 
            'productos_favoritos', 'ventas_recientes'
        ]
    
    
    @extend_schema_field({
        'type': 'array',
        'items': {
            'type': 'object',
            'properties': {
                'producto_id': {'type': 'integer'},
                'producto_codigo': {'type': 'string'},
                'producto_nombre': {'type': 'string'},
                'ultima_cantidad': {'type': 'integer'},
                'ultimo_precio': {'type': 'number', 'format': 'decimal'},
                'fecha_ultima_compra': {'type': 'string', 'format': 'date'},
                'venta_codigo': {'type': 'string'}
            }
        }
    })
    @cache_cliente_data(timeout=600)  # 10 minutos de caché
    def get_ultimos_productos_comprados(self, obj):
        """
        Retorna los últimos 5 productos comprados por el cliente (optimizada)
        """
        # Usar ventas pre-cargadas si están disponibles
        if hasattr(obj, '_ventas_terminadas'):
            ventas = obj._ventas_terminadas
        else:
            ventas = obj.ventas.filter(fase=Venta.FASE_TERMINADA).prefetch_related('detalles__producto').order_by('-created_at')[:20]
        
        # Agrupar por producto para evitar duplicados
        productos_vistos = set()
        productos_unicos = []
        
        for venta in ventas:
            if len(productos_unicos) >= 5:
                break
            for detalle in venta.detalles.all():
                if detalle.producto.id not in productos_vistos and len(productos_unicos) < 5:
                    productos_vistos.add(detalle.producto.id)
                    productos_unicos.append({
                        'producto_id': detalle.producto.id,
                        'producto_codigo': detalle.producto.codigo,
                        'producto_nombre': detalle.producto.nombre,
                        'ultima_cantidad': detalle.cantidad,
                        'ultimo_precio': float(detalle.precio_unitario),
                        'fecha_ultima_compra': venta.created_at.strftime('%Y-%m-%d'),
                        'venta_codigo': venta.codigo
                    })
        
        return productos_unicos
    
    @extend_schema_field({'type': 'boolean'})
    def get_adeudo(self, obj):
        """
        Por ahora retorna false, más adelante se implementará la lógica real
        """
        return False
    
    @extend_schema_field({
        'type': 'object',
        'properties': {
            'cantidad_ventas': {'type': 'integer'},
            'monto_total': {'type': 'number', 'format': 'decimal'},
            'promedio_venta': {'type': 'number', 'format': 'decimal'}
        }
    })
    @cache_cliente_data(timeout=300)  # 5 minutos de caché
    def get_total_ventas(self, obj):
        """
        Retorna estadísticas básicas de ventas del cliente (optimizada)
        """
        # Usar estadísticas pre-calculadas si están disponibles
        if hasattr(obj, '_estadisticas_ventas'):
            stats = obj._estadisticas_ventas
            return {
                'cantidad_ventas': stats['cantidad_ventas'],
                'monto_total': float(stats['monto_total']),
                'promedio_venta': float(stats['promedio_venta'])
            }
        
        # Fallback a consulta directa si no están pre-calculadas
        ventas = obj.ventas.filter(fase='TERMINADA')
        total_ventas = ventas.count()
        monto_total = ventas.aggregate(total=models.Sum('total'))['total'] or 0
        
        return {
            'cantidad_ventas': total_ventas,
            'monto_total': float(monto_total),
            'promedio_venta': float(monto_total / total_ventas) if total_ventas > 0 else 0
        }
    
    @extend_schema_field({
        'type': 'array',
        'items': {
            'type': 'object',
            'properties': {
                'id': {'type': 'integer', 'description': 'ID de la venta'},
                'codigo': {'type': 'string', 'description': 'Código de la venta'},
                'pertenece': {'type': 'string', 'description': 'Almacén al que pertenece la venta'},
                'ruta': {'type': 'string', 'description': 'Ruta de la venta'},
                'fase': {'type': 'string', 'description': 'Fase de la venta'},
                'total': {'type': 'number', 'format': 'decimal', 'description': 'Total de la venta'},
                'productos_count': {'type': 'integer', 'description': 'Cantidad de productos en la venta'},
                'created_at': {'type': 'string', 'format': 'date-time', 'description': 'Fecha de creación de la venta'},
                'updated_at': {'type': 'string', 'format': 'date-time', 'description': 'Fecha de actualización de la venta'},
                'created_by': {'type': 'string', 'description': 'Usuario que creó la venta'},
                'updated_by': {'type': 'string', 'description': 'Usuario que actualizó la venta'}
            }
        },
        'description': 'Últimas 10 ventas terminadas del cliente'
    })
    @cache_cliente_data(timeout=180)  # 3 minutos de caché para ventas recientes
    def get_ventas_recientes(self, obj):
        """
        Retorna las ventas recientes del cliente (optimizada)
        """
        # Usar ventas pre-cargadas si están disponibles
        if hasattr(obj, '_ventas_terminadas'):
            ventas = obj._ventas_terminadas[:10]  # Solo las primeras 10
        else:
            ventas = obj.ventas.filter(
                fase=Venta.FASE_TERMINADA
            ).prefetch_related('detalles').order_by('-created_at')[:10]
        
        data = []
        for venta in ventas:
            data.append({
                'id': venta.id,
                'codigo': venta.codigo,
                'ruta': venta.ruta.nombre if venta.ruta else '',
                'total': float(venta.total),
                'fase': venta.fase,
                'pertenece': venta.almacen.nombre if venta.almacen else '',
                'productos_count': len(venta.detalles.all()) if hasattr(obj, '_ventas_terminadas') else venta.detalles.count(),
                'created_at': venta.created_at.strftime('%Y-%m-%d'),
                'created_by': venta.created_by.username if venta.created_by else '',
                'updated_at': venta.updated_at.strftime('%Y-%m-%d') if venta.updated_at else '',
                'updated_by': venta.updated_by.username if venta.updated_by else '',
            })
        return data

    @extend_schema_field({
        'type': 'array',
        'items': {
            'type': 'object',
            'properties': {
                'producto_id': {'type': 'integer', 'description': 'ID del producto'},
                'producto_codigo': {'type': 'string', 'description': 'Código del producto'},
                'producto_nombre': {'type': 'string', 'description': 'Nombre del producto'},
                'veces_comprado': {'type': 'integer', 'description': 'Número de veces que ha comprado este producto'},
                'total_cantidad': {'type': 'number', 'format': 'decimal', 'description': 'Cantidad total comprada de este producto'}
            }
        },
        'description': 'Top 10 productos más comprados por el cliente'
    })
    @cache_cliente_data(timeout=900)  # 15 minutos de caché para productos favoritos
    def get_productos_favoritos(self, obj):
        """
        Retorna los productos favoritos del cliente (optimizada)
        """
        # Usar productos favoritos pre-calculados si están disponibles
        if hasattr(obj, '_productos_favoritos'):
            productos_favoritos = obj._productos_favoritos
        else:
            productos_favoritos = VentaDetalle.objects.filter(
                venta__cliente=obj,
                venta__fase=Venta.FASE_TERMINADA
            ).values(
                'producto_id', 'producto__codigo', 'producto__nombre'
            ).annotate(
                total_cantidad=models.Sum('cantidad'),
                veces_comprado=models.Count('venta_id', distinct=True)
            ).order_by('-total_cantidad')[:10]
        
        data = []
        for producto in productos_favoritos:
            data.append({
                'producto_id': producto['producto_id'],
                'producto_codigo': producto['producto__codigo'],
                'producto_nombre': producto['producto__nombre'],
                'veces_comprado': producto['veces_comprado'],
                'total_cantidad': producto['total_cantidad']
            })
        return data


# Serializer para mostrar estadísticas de performance de consultas
class ClientePerformanceSerializer(serializers.Serializer):
    """
    Serializer para mostrar estadísticas de performance de las consultas del cliente
    """
    cliente_id = serializers.IntegerField()
    cache_hits = serializers.DictField()
    query_count = serializers.IntegerField()
    execution_time_ms = serializers.FloatField()
    optimizations_applied = serializers.ListField(child=serializers.CharField())
    
    def to_representation(self, instance):
        """
        Generar estadísticas de performance
        """
        from django.core.cache import cache
        from django.db import connection
        import time
        
        start_time = time.time()
        initial_queries = len(connection.queries)
        
        # Verificar hits de caché
        cache_keys = [
            f"cliente_{instance.id}_get_ultimos_productos_comprados_v2",
            f"cliente_{instance.id}_get_total_ventas_v2",
            f"cliente_{instance.id}_get_productos_favoritos_v2",
            f"cliente_{instance.id}_get_ventas_recientes_v2"
        ]
        
        cache_hits = {}
        for key in cache_keys:
            method_name = key.split('_get_')[1].split('_v2')[0]
            cache_hits[method_name] = cache.get(key) is not None
        
        # Simular serialización para medir performance
        serializer = InformacionClienteSerializer(instance)
        data = serializer.data
        
        end_time = time.time()
        final_queries = len(connection.queries)
        
        optimizations = []
        if hasattr(instance, '_ventas_terminadas'):
            optimizations.append("prefetch_ventas_terminadas")
        if hasattr(instance, '_direcciones_precargadas'):
            optimizations.append("prefetch_direcciones")
        if hasattr(instance, '_estadisticas_ventas'):
            optimizations.append("estadisticas_precalculadas")
        if any(cache_hits.values()):
            optimizations.append("cache_activo")
        
        return {
            'cliente_id': instance.id,
            'cache_hits': cache_hits,
            'query_count': final_queries - initial_queries,
            'execution_time_ms': round((end_time - start_time) * 1000, 2),
            'optimizations_applied': optimizations
        }