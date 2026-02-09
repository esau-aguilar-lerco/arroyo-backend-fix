from django.contrib import admin
from .models import (
    Empresa, Categoria, Producto, Proveedor, Almacen, Sucursal,CategoriaCliente, Cliente,
    OrdenCompra, OrdenCompraDetalle, Compra, CompraDetalle, PagosCompra,
    Rutas, UnidadVehicular, 
    Notificacion,
    Caja, CajaApertura, CajaTransaccion,
    Venta, VentaDetalle, VentaDetalleLote, PagosVenta,
    incidencia, IncidenciaLote,
)
@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "rfc", "telefono", "email", "created_at", "updated_at", "status_model")
    search_fields = ("nombre", "rfc", "email")
    list_filter = ("status_model",)
    ordering = ("nombre",)


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "descripcion", "created_at", "updated_at", "status_model")
    search_fields = ("nombre", "descripcion")
    ordering = ("nombre",)


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "categoria", "precio_publico", "unidad_sat", "created_at", "updated_at", "status_model")
    search_fields = ("codigo", "nombre", "clave_sat")
    list_filter = ("categoria", "unidad_sat", "status_model")
    ordering = ("nombre",)


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "razon_social", "rfc", "telefono", "correo", "created_at", "updated_at", "status_model")
    search_fields = ("codigo", "nombre", "razon_social", "rfc", "correo")
    list_filter = ("origen", "status_model")
    ordering = ("nombre",)


@admin.register(Almacen)
class AlmacenAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "telefono", "encargado", "created_at", "updated_at", "status_model")
    search_fields = ("codigo", "nombre", "telefono")
    list_filter = ("status_model",)
    ordering = ("nombre",)


@admin.register(Rutas)
class RutasAdmin(admin.ModelAdmin):
    """
    Administrador para el modelo Rutas
    """
    list_display = (
        "codigo", "nombre", "origen", "destino", "unidad", 
        "asignado", "almacen_display", "created_at", "status_model"
    )
    list_filter = ("status_model", "created_at", "almacen__tipo")
    search_fields = ("codigo", "nombre", "origen", "destino", "unidad", "asignado__full_name")
    ordering = ("-created_at",)
    readonly_fields = ("codigo", "almacen", "created_at", "updated_at", "created_by", "updated_by")
    
    def almacen_display(self, obj):
        """
        Mostrar información del almacén virtual creado automáticamente
        """
        if obj.almacen:
            return f"{obj.almacen.nombre} ({obj.almacen.tipo})"
        return "Pendiente de creación"
    almacen_display.short_description = "Almacén Virtual"
    almacen_display.admin_order_field = "almacen__nombre"
    
    fieldsets = (
        ("Información Básica", {
            "fields": ("codigo", "nombre", "descripcion")
        }),
        ("Ruta", {
            "fields": ("origen", "destino", "unidad")
        }),
        ("Asignaciones", {
            "fields": ("asignado",)
        }),
        ("Almacén Virtual", {
            "fields": ("almacen",),
            "description": "El almacén virtual se crea automáticamente al guardar la ruta.",
            "classes": ("collapse",)
        }),
        ("Auditoría", {
            "fields": ("created_at", "updated_at", "created_by", "updated_by", "status_model"),
            "classes": ("collapse",)
        })
    )
    
    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        # El almacén se asigna automáticamente por el signal, siempre readonly
        if 'almacen' not in readonly:
            readonly.append('almacen')
        return readonly


@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "telefono", "encargado", "created_at", "updated_at", "status_model")
    search_fields = ("codigo", "nombre", "telefono")
    list_filter = ("status_model",)
    ordering = ("nombre",)
    

@admin.register(CategoriaCliente)
class CategoriaClienteAdmin(admin.ModelAdmin):
    """
    Administrador para CategoriaCliente
    """
    list_display = (
        'nombre', 'limite_credito_min_display', 'limite_credito_max_display',
        'clientes_count', 'created_at', 'status_model'
    )
    list_filter = ('status_model', 'created_at')
    search_fields = ('nombre', 'descripcion')
    ordering = ('nombre',)
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by', 'clientes_count')
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'descripcion'),
            'description': 'Información general de la categoría'
        }),
        ('Límites de Crédito', {
            'fields': ('limite_credito_min', 'limite_credito_max'),
            'description': 'Rango de crédito permitido para esta categoría'
        }),
        ('Estadísticas', {
            'fields': ('clientes_count',),
            'description': 'Clientes en esta categoría',
            'classes': ('collapse',)
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by', 'status_model'),
            'classes': ('collapse',)
        })
    )
    
    def limite_credito_min_display(self, obj):
        """Mostrar límite mínimo formateado"""
        return f"${obj.limite_credito_min:,.2f}"
    limite_credito_min_display.short_description = 'Límite Mín.'
    limite_credito_min_display.admin_order_field = 'limite_credito_min'
    
    def limite_credito_max_display(self, obj):
        """Mostrar límite máximo formateado"""
        return f"${obj.limite_credito_max:,.2f}"
    limite_credito_max_display.short_description = 'Límite Máx.'
    limite_credito_max_display.admin_order_field = 'limite_credito_max'
    
    def clientes_count(self, obj):
        """Contar clientes en esta categoría"""
        count = obj.clientes_clasificacion.filter(status_model='ACTIVE').count()
        return f"👥 {count} cliente(s)"
    clientes_count.short_description = 'Clientes'


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    """
    Administrador mejorado para Cliente
    """
    list_display = (
        'codigo_display', 'nombre_completo_display', 'tipo_display',
        'precio_tipo_display', 'telefono', 'limite_credito_display',
        'vendedor', 'clasificacion', 'created_at', 'status_model'
    )
    list_filter = (
        'tipo', 'precio_tipo', 'tipo_persona', 'clasificacion',
        'status_model', 'created_at', 'vendedor'
    )
    search_fields = (
        'codigo', 'nombre', 'apellido_paterno', 'apellido_materno',
        'razon_social', 'email', 'rfc', 'telefono'
    )
    ordering = ('nombre',)
    readonly_fields = (
        'codigo_display', 'total_credito', 'created_at', 
        'updated_at', 'created_by', 'updated_by'
    )
    
    fieldsets = (
        ('Información Básica', {
            'fields': (
                'codigo_display', 'tipo_persona', 'nombre', 
                'apellido_paterno', 'apellido_materno', 'razon_social'
            ),
            'description': 'Información general del cliente'
        }),
        ('Contacto', {
            'fields': ('telefono', 'email'),
            'description': 'Información de contacto'
        }),
        ('Clasificación', {
            'fields': ('tipo', 'clasificacion', 'precio_tipo', 'vendedor'),
            'description': 'Tipo y categorización del cliente'
        }),
        ('Datos Fiscales', {
            'fields': ('rfc', 'uso_cfdi', 'regimen_fiscal'),
            'description': 'Información fiscal',
            'classes': ('collapse',)
        }),
        ('Crédito', {
            'fields': (
                'limite_credito', 'total_credito', 'plazos_semanas','sujeto_credito'
            ),
            'description': 'Información de crédito'
        }),
        ('Auditoría', {
            'fields': (
                'created_at', 'updated_at', 'created_by', 
                'updated_by', 'status_model'
            ),
            'classes': ('collapse',)
        })
    )
    
    # Acciones personalizadas
    actions = ['actualizar_vendedor', 'cambiar_tipo_precio']
    
    def codigo_display(self, obj):
        """Mostrar código con ícono según tipo"""
        iconos = {
            Cliente.TIPO_PREMIUM: "⭐",
            Cliente.TIPO_BUEN_CLIENTE: "👍",
            Cliente.TIPO_CREDITO_SEMANAL: "💳",
            Cliente.TIPO_NO_CREDITO: "💵",
            Cliente.TIPO_ESTANDAR: "👤",
            Cliente.TIPO_POTENCIAL: "🎯",
            Cliente.TIPO_EVENTUAL: "📋",
        }
        icono = iconos.get(obj.tipo, "👤")
        return f"{icono} {obj.codigo}"
    codigo_display.short_description = 'Código'
    codigo_display.admin_order_field = 'codigo'
    
    def nombre_completo_display(self, obj):
        """Mostrar nombre completo"""
        return obj.get_full_name
    nombre_completo_display.short_description = 'Nombre Completo'
    nombre_completo_display.admin_order_field = 'nombre'
    
    def tipo_display(self, obj):
        """Mostrar tipo con formato"""
        colores = {
            Cliente.TIPO_PREMIUM: "🟡",
            Cliente.TIPO_BUEN_CLIENTE: "🟢",
            Cliente.TIPO_CREDITO_SEMANAL: "🔵",
            Cliente.TIPO_NO_CREDITO: "⚪",
            Cliente.TIPO_ESTANDAR: "🟢",
            Cliente.TIPO_POTENCIAL: "🟣",
            Cliente.TIPO_EVENTUAL: "⚫",
        }
        icono = colores.get(obj.tipo, "⚪")
        return f"{icono} {obj.get_tipo_display()}"
    tipo_display.short_description = 'Tipo'
    tipo_display.admin_order_field = 'tipo'
    
    def precio_tipo_display(self, obj):
        """Mostrar tipo de precio con ícono"""
        iconos = {
            Cliente.MAYOREO: "💼",
            Cliente.SEMI_MAYOREO: "🏪",
            Cliente.PUBLICO: "🛒",
        }
        icono = iconos.get(obj.precio_tipo, "🛒")
        return f"{icono} {obj.precio_tipo}"
    precio_tipo_display.short_description = 'Lista Precios'
    precio_tipo_display.admin_order_field = 'precio_tipo'
    
    def limite_credito_display(self, obj):
        """Mostrar límite de crédito formateado"""
        if obj.limite_credito:
            return f"💰 ${obj.limite_credito:,.2f}"
        return "Sin crédito"
    limite_credito_display.short_description = 'Límite Crédito'
    limite_credito_display.admin_order_field = 'limite_credito'
    
    def actualizar_vendedor(self, request, queryset):
        """Acción placeholder para actualizar vendedor"""
        self.message_user(
            request,
            f"Seleccionados {queryset.count()} cliente(s). "
            "Función de actualización masiva de vendedor en desarrollo.",
            level='info'
        )
    actualizar_vendedor.short_description = "Actualizar vendedor (en desarrollo)"
    
    def cambiar_tipo_precio(self, request, queryset):
        """Acción placeholder para cambiar tipo de precio"""
        self.message_user(
            request,
            f"Seleccionados {queryset.count()} cliente(s). "
            "Función de cambio masivo de lista de precios en desarrollo.",
            level='info'
        )
    cambiar_tipo_precio.short_description = "Cambiar lista de precios (en desarrollo)"


# ===============================================================
#                ADMINISTRADOR DE NOTIFICACIONES
# ===============================================================

@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = (
        'titulo',
        'usuario',
        'tipo',
        'leida',
        'creada_el',
        'leida_el',
        'leida_por',
    )
    list_filter = (
        'tipo',
        'leida',
        'creada_el',
    )
    search_fields = (
        'titulo',
        'mensaje',
        'usuario__username',
        'leida_por__username',
    )
    readonly_fields = (
        'creada_el',
        'leida_el',
    )
    ordering = ('-creada_el',)
    list_per_page = 20

    # ✅ Acciones personalizadas
    actions = ['marcar_como_leidas', 'marcar_como_no_leidas']

    def marcar_como_leidas(self, request, queryset):
        updated = queryset.update(leida=True)
        self.message_user(request, f"{updated} notificaciones marcadas como leídas.")
    marcar_como_leidas.short_description = "Marcar seleccionadas como leídas"

    def marcar_como_no_leidas(self, request, queryset):
        updated = queryset.update(leida=False, leida_el=None, leida_por=None)
        self.message_user(request, f"{updated} notificaciones marcadas como no leídas.")
    marcar_como_no_leidas.short_description = "Marcar seleccionadas como no leídas"

# ================================================================
#                    ADMINISTRADOR DE ORDEN DE COMPRA
# ================================================================

class OrdenCompraDetalleInline(admin.TabularInline):
    """
    Inline para mostrar los detalles de la orden de compra dentro del admin de OrdenCompra
    """
    model = OrdenCompraDetalle
    extra = 1
    fields = ('producto', 'cantidad')
    #readonly_fields = ('subtotal',)

    def subtotal(self, obj):
        if obj.id:
            return f"${obj.subtotal:,.2f}"
        return "-"
    subtotal.short_description = "Subtotal"


class ComprasRelacionadasInline(admin.TabularInline):
    """
    Inline para mostrar las compras relacionadas con la orden de compra
    """
    model = Compra
    extra = 0
    fields = ('codigo', 'almacen_destino', 'estado', 'total', 'fecha_salida', 'existe_diferencia')
    readonly_fields = ('codigo', 'total', 'existe_diferencia')
    can_delete = False


@admin.register(OrdenCompra)
class OrdenCompraAdmin(admin.ModelAdmin):
    list_display = (
        "codigo", "proveedor", "estado", 
        "created_at", "updated_at", "created_by", "status_model"
    )
    list_filter = ("estado", "status_model", "created_at", "proveedor")
    search_fields = ("codigo", "proveedor__nombre", "proveedor__codigo")
    ordering = ("-created_at",)
    readonly_fields = ("codigo", "created_at", "updated_at", "created_by", "updated_by")
    
    fieldsets = (
        ("Información Básica", {
            "fields": ("codigo", "proveedor", "estado")
        }),
        ("Auditoría", {
            "fields": ("created_at", "updated_at", "created_by", "updated_by", "status_model"),
            "classes": ("collapse",)
        })
    )
    
    inlines = [OrdenCompraDetalleInline, ComprasRelacionadasInline]
    
    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if obj and obj.estado in ['FINALIZADA', 'CANCELADA']:
            # Si la orden está finalizada o cancelada, hacer todos los campos readonly
            readonly.extend(['proveedor', 'estado', 'total'])
        return readonly


@admin.register(OrdenCompraDetalle)
class OrdenCompraDetalleAdmin(admin.ModelAdmin):
    list_display = ("orden_compra", "producto", "cantidad")
    list_filter = ("orden_compra__estado",)
    search_fields = ("orden_compra__codigo", "producto__nombre", "producto__codigo")
    ordering = ("-orden_compra__created_at",)
    
    def subtotal_display(self, obj):
        return f"${obj.subtotal:,.2f}"
    subtotal_display.short_description = "Subtotal"


# ================================================================
#                    ADMINISTRADOR DE COMPRA
# ================================================================

class CompraDetalleInline(admin.TabularInline):
    """
    Inline para mostrar los detalles de la compra dentro del admin de Compra
    """
    model = CompraDetalle
    extra = 1
    fields = ('producto', 'cantidad', 'precio_unitario', 'subtotal')
    readonly_fields = ('subtotal',)


class PagosCompraInline(admin.TabularInline):
    """
    Inline para mostrar los pagos de la compra dentro del admin de Compra
    """
    model = PagosCompra
    extra = 0
    fields = ('monto', 'metodo_pago', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(Compra)
class CompraAdmin(admin.ModelAdmin):
    list_display = (
        "codigo", "orden_compra_display", "proveedor", "almacen_destino", "estado", "total", 
        "fecha_salida", "existe_diferencia", "created_at", "status_model"
    )
    list_filter = ("estado", "existe_diferencia", "status_model", "fecha_salida", "almacen_destino", "orden_compra__estado")
    search_fields = ("codigo", "orden_compra__codigo", "proveedor__nombre", "almacen_destino__nombre", "nota")
    ordering = ("-created_at",)
    readonly_fields = ("codigo", "created_at", "updated_at", "created_by", "updated_by")
    
    def orden_compra_display(self, obj):
        if obj.orden_compra:
            return f"{obj.orden_compra.codigo} ({obj.orden_compra.estado})"
        return "Sin orden"
    orden_compra_display.short_description = "Orden de Compra"
    orden_compra_display.admin_order_field = "orden_compra__codigo"
    
    fieldsets = (
        ("Información Básica", {
            "fields": ("codigo", "orden_compra", "proveedor", "estado", "total")
        }),
        ("Almacenes", {
            "fields": ("almacen_destino", "almacen_virtual")
        }),
        ("Logística", {
            "fields": ("fecha_salida", "tiempo_recorrido", "latitud", "longitud")
        }),
        ("Control", {
            "fields": ("existe_diferencia", "nota")
        }),
        ("Auditoría", {
            "fields": ("created_at", "updated_at", "created_by", "updated_by", "status_model"),
            "classes": ("collapse",)
        })
    )
    
    inlines = [CompraDetalleInline, PagosCompraInline]


@admin.register(CompraDetalle)
class CompraDetalleAdmin(admin.ModelAdmin):
    list_display = ("compra", "orden_compra_codigo", "producto", "cantidad", "precio_unitario", "subtotal")
    list_filter = ("compra__estado", "compra__orden_compra__estado")
    search_fields = ("compra__codigo", "compra__orden_compra__codigo", "producto__nombre", "producto__codigo")
    ordering = ("-compra__created_at",)
    
    def orden_compra_codigo(self, obj):
        if obj.compra.orden_compra:
            return obj.compra.orden_compra.codigo
        return "Sin orden"
    orden_compra_codigo.short_description = "Orden de Compra"
    orden_compra_codigo.admin_order_field = "compra__orden_compra__codigo"


@admin.register(PagosCompra)
class PagosCompraAdmin(admin.ModelAdmin):
    list_display = ("compra", "monto", "metodo_pago", "created_at", "status_model")
    list_filter = ("metodo_pago", "status_model", "created_at")
    search_fields = ("compra__codigo",)
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")


@admin.register(UnidadVehicular)
class UnidadVehicularAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'placas', 'tipo', 'marca', 'modelo', 'anio', 'capacidad_carga', 'status_model', 'created_at')
    list_filter = ('tipo', 'status_model', 'marca', 'anio', 'created_at')
    search_fields = ('nombre', 'placas', 'marca', 'modelo')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by', 'get_clave')
    
    fieldsets = (
        ('Información General', {
            'fields': ('nombre', 'tipo', 'placas'),
            'description': 'Información básica de la unidad vehicular'
        }),
        ('Especificaciones Técnicas', {
            'fields': ('marca', 'modelo', 'anio', 'capacidad_carga'),
            'description': 'Detalles técnicos del vehículo'
        }),
        ('Información Adicional', {
            'fields': ('fecha_adquisicion', 'status_model'),
            'description': 'Información complementaria'
        }),
        ('Información del Sistema', {
            'fields': ('get_clave', 'created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',),
            'description': 'Información de auditoría del sistema'
        }),
    )
    
    # Fieldsets para crear unidad vehicular (sin campos del sistema)
    add_fieldsets = (
        ('Información General', {
            'fields': ('nombre', 'tipo', 'placas'),
            'description': 'Información básica de la unidad vehicular'
        }),
        ('Especificaciones Técnicas', {
            'fields': ('marca', 'modelo', 'anio', 'capacidad_carga'),
            'description': 'Detalles técnicos del vehículo'
        }),
        ('Información Adicional', {
            'fields': ('fecha_adquisicion',),
            'description': 'Información complementaria'
        }),
    )
    
    def get_fieldsets(self, request, obj=None):
        """Usar fieldsets diferentes para creación vs edición"""
        if not obj:  # Creando nuevo objeto
            return self.add_fieldsets
        return super().get_fieldsets(request, obj)
    
    def get_clave(self, obj):
        """Mostrar la clave generada"""
        if obj and obj.id:
            return obj.get_clave()
        return "Se generará al guardar"
    get_clave.short_description = 'Clave del Sistema'


# ================================================================
#                    ADMINISTRADOR DE CAJAS
# ================================================================

@admin.register(Caja)
class CajaAdmin(admin.ModelAdmin):
    """
    Administrador para el modelo Caja
    """
    list_display = (
        'nombre', 'tipo', 'sucursal', 'ruta', 
        'aperturas_activas', 'created_at', 'status_model'
    )
    list_filter = ('tipo', 'status_model', 'created_at', 'sucursal')
    search_fields = ('nombre', 'tipo')
    ordering = ('nombre',)
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by', 'folio_display')
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'tipo', 'folio_display'),
            'description': 'Información general de la caja'
        }),
        ('Asignación', {
            'fields': ('sucursal', 'ruta'),
            'description': 'Ubicación o ruta asignada a la caja'
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by', 'status_model'),
            'classes': ('collapse',)
        })
    )
    
    def folio_display(self, obj):
        """Mostrar folio de la caja"""
        if obj and obj.pk:
            return obj.folio
        return "Se generará al guardar"
    folio_display.short_description = 'Folio'
    
    def aperturas_activas(self, obj):
        """Mostrar número de aperturas activas"""
        count = obj.aperturas.filter(
            is_abierta=True,
            status_model='ACTIVE'
        ).count()
        if count > 0:
            return f"✅ {count} abierta(s)"
        return "❌ Cerrada"
    aperturas_activas.short_description = 'Estado'


class CajaTransaccionInline(admin.TabularInline):
    """
    Inline para mostrar transacciones dentro de una apertura de caja
    """
    model = CajaTransaccion
    extra = 0
    fields = ('tipo', 'monto', 'metodo_pago', 'descripcion', 'created_at')
    readonly_fields = ('created_at',)
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        # No permitir agregar transacciones desde el inline
        return False


@admin.register(CajaApertura)
class CajaAperturaAdmin(admin.ModelAdmin):
    """
    Administrador para el modelo CajaApertura
    """
    list_display = (
        'folio_display', 'caja', 'usuario', 'monto_inicial', 
        'monto_final', 'diferencia_display', 'estado_display', 
        'fecha_apertura', 'fecha_cierre'
    )
    list_filter = ('is_abierta', 'caja', 'fecha_apertura', 'status_model')
    search_fields = ('caja__nombre', 'usuario__username', 'usuario__first_name', 'usuario__last_name')
    ordering = ('-fecha_apertura',)
    readonly_fields = (
        'folio_display', 'fecha_apertura', 'fecha_cierre',
        'diferencia_display', 'created_at', 'updated_at', 'created_by', 'updated_by',
        'total_entradas_display', 'total_salidas_display', 'saldo_actual_display'
    )
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('folio_display', 'caja', 'usuario', 'is_abierta'),
            'description': 'Información general de la apertura'
        }),
        ('Montos', {
            'fields': (
                'monto_inicial', 'monto_final'
            ),
            'description': 'Montos de apertura y cierre'
        }),
        ('Resumen de Movimientos', {
            'fields': (
                'diferencia_display', 'total_entradas_display', 'total_salidas_display', 'saldo_actual_display'
            ),
            'description': 'Totales calculados de transacciones (solo lectura)',
            'classes': ('collapse',)
        }),
        ('Fechas', {
            'fields': ('fecha_apertura', 'fecha_cierre'),
            'description': 'Fechas de apertura y cierre'
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by', 'status_model'),
            'classes': ('collapse',)
        })
    )
    
    inlines = [CajaTransaccionInline]
    
    def folio_display(self, obj):
        """Mostrar folio con ícono según estado"""
        icono = "🟢" if obj.is_abierta else "🔴"
        return f"{icono} {obj.folio}"
    folio_display.short_description = 'Folio'
    folio_display.admin_order_field = 'id'
    
    def estado_display(self, obj):
        """Mostrar estado con formato"""
        if obj.is_abierta:
            return "🟢 ABIERTA"
        return "🔴 CERRADA"
    estado_display.short_description = 'Estado'
    estado_display.admin_order_field = 'is_abierta'
    
    def diferencia_display(self, obj):
        """Mostrar diferencia con color"""
        if obj.monto_final is None:
            return "-"
        
        diferencia = obj.monto_final - obj.monto_inicial
        
        if diferencia > 0:
            return f"✅ +${diferencia:,.2f}"
        elif diferencia < 0:
            return f"❌ ${diferencia:,.2f}"
        else:
            return f"✔️ ${diferencia:,.2f}"
    diferencia_display.short_description = 'Diferencia'
    
    def total_entradas_display(self, obj):
        """Mostrar total de entradas"""
        from django.db.models import Sum
        total = obj.transacciones.filter(
            tipo=CajaTransaccion.TIPO_ENTRADA,
            status_model='ACTIVE'
        ).aggregate(Sum('monto'))['monto__sum'] or 0
        return f"💰 ${total:,.2f}"
    total_entradas_display.short_description = 'Total Entradas'
    
    def total_salidas_display(self, obj):
        """Mostrar total de salidas"""
        from django.db.models import Sum
        total = obj.transacciones.filter(
            tipo=CajaTransaccion.TIPO_SALIDA,
            status_model='ACTIVE'
        ).aggregate(Sum('monto'))['monto__sum'] or 0
        return f"💸 ${total:,.2f}"
    total_salidas_display.short_description = 'Total Salidas'
    
    def saldo_actual_display(self, obj):
        """Mostrar saldo actual calculado"""
        from django.db.models import Sum, Case, When, DecimalField, F
        
        saldo_transacciones = obj.transacciones.filter(
            status_model='ACTIVE'
        ).aggregate(
            saldo=Sum(
                Case(
                    When(tipo=CajaTransaccion.TIPO_ENTRADA, then='monto'),
                    When(tipo=CajaTransaccion.TIPO_SALIDA, then=-F('monto')),
                    output_field=DecimalField()
                )
            )
        )['saldo'] or 0
        
        saldo_total = obj.monto_inicial + saldo_transacciones
        return f"💵 ${saldo_total:,.2f}"
    saldo_actual_display.short_description = 'Saldo Actual'
    
    def get_readonly_fields(self, request, obj=None):
        """Campos readonly según el estado"""
        readonly = list(self.readonly_fields)
        
        # Si la caja está cerrada, hacer todos los campos readonly excepto observaciones
        if obj and not obj.is_abierta:
            readonly.extend(['caja', 'usuario', 'monto_inicial', 'is_abierta'])
        
        return readonly
    
    # Acciones personalizadas
    actions = ['cerrar_cajas_seleccionadas']
    
    def cerrar_cajas_seleccionadas(self, request, queryset):
        """Acción para cerrar múltiples cajas"""
        cajas_abiertas = queryset.filter(is_abierta=True)
        count = cajas_abiertas.count()
        
        if count == 0:
            self.message_user(request, "No hay cajas abiertas en la selección.", level='warning')
            return
        
        # Esta acción solo marca para revisión, no cierra automáticamente
        self.message_user(
            request, 
            f"Se encontraron {count} caja(s) abierta(s). "
            "Por favor, ciérrelas individualmente con el monto final correcto.",
            level='info'
        )
    cerrar_cajas_seleccionadas.short_description = "Verificar cajas abiertas seleccionadas"


@admin.register(CajaTransaccion)
class CajaTransaccionAdmin(admin.ModelAdmin):
    """
    Administrador para el modelo CajaTransaccion
    """
    list_display = (
        'id_display', 'caja_display', 'tipo_display',
        'monto_display', 'metodo_pago', 'created_at', 'created_by'
    )
    list_filter = ('tipo', 'metodo_pago', 'created_at', 'status_model')
    search_fields = (
        'caja_apertura__caja__nombre', 'descripcion', 'referencia',
        'caja_apertura__usuario__username'
    )
    ordering = ('-created_at',)
    readonly_fields = (
        'id_display', 'monto_con_signo_display', 'created_at', 
        'updated_at', 'created_by', 'updated_by'
    )
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('id_display', 'caja_apertura', 'tipo'),
            'description': 'Información general de la transacción'
        }),
        ('Monto', {
            'fields': ('monto', 'metodo_pago', 'monto_con_signo_display'),
            'description': 'Detalles del monto'
        }),
        ('Descripción', {
            'fields': ('descripcion', 'referencia'),
            'description': 'Información adicional'
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by', 'status_model'),
            'classes': ('collapse',)
        })
    )
    
    def id_display(self, obj):
        """Mostrar ID con ícono según tipo"""
        icono = "💰" if obj.tipo == CajaTransaccion.TIPO_ENTRADA else "💸"
        return f"{icono} TXN-{obj.pk:08d}"
    id_display.short_description = 'ID Transacción'
    id_display.admin_order_field = 'id'
    
    def tipo_display(self, obj):
        """Mostrar tipo con color"""
        if obj.tipo == CajaTransaccion.TIPO_ENTRADA:
            return "🟢 ENTRADA"
        return "🔴 SALIDA"
    tipo_display.short_description = 'Tipo'
    tipo_display.admin_order_field = 'tipo'
    
    def monto_display(self, obj):
        """Mostrar monto formateado"""
        return f"${obj.monto:,.2f}"
    monto_display.short_description = 'Monto'
    monto_display.admin_order_field = 'monto'
    
    def monto_con_signo_display(self, obj):
        """Mostrar monto con signo según tipo"""
        if obj.tipo == CajaTransaccion.TIPO_ENTRADA:
            return f"+${obj.monto:,.2f}"
        else:
            return f"-${obj.monto:,.2f}"
    monto_con_signo_display.short_description = 'Monto con Signo'
    
    def caja_display(self, obj):
        """Mostrar información de la caja"""
        if obj.caja_apertura:
            return f"{obj.caja_apertura.caja.nombre} ({obj.caja_apertura.folio})"
        return "N/A"
    caja_display.short_description = 'Caja'
    caja_display.admin_order_field = 'caja_apertura__caja__nombre'
    
    def has_add_permission(self, request):
        """Deshabilitar agregar transacciones desde admin"""
        # Las transacciones deben crearse desde la API
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Deshabilitar eliminar transacciones"""
        # Las transacciones no deben eliminarse
        return False


# ================================================================
#                    ADMINISTRADOR DE VENTAS
# ================================================================

class VentaDetalleInline(admin.TabularInline):
    """
    Inline para mostrar los detalles de la venta
    """
    model = VentaDetalle
    extra = 0
    fields = ('producto', 'cantidad', 'precio_unitario', 'subtotal', 'is_cargado', 'is_entregado')
    readonly_fields = ('subtotal',)


class PagosVentaInline(admin.TabularInline):
    """
    Inline para mostrar los pagos de la venta
    """
    model = PagosVenta
    extra = 0
    fields = ('monto', 'metodo_pago', 'referencia', 'created_at')
    readonly_fields = ('created_at', 'clave_display')
    
    def clave_display(self, obj):
        """Mostrar clave del pago"""
        if obj and obj.pk:
            return obj.clave
        return "Se generará al guardar"
    clave_display.short_description = 'Clave'


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    """
    Administrador para el modelo Venta
    """
    list_display = (
        'codigo_display', 'cliente', 'almacen', 'fase_display', 
        'tipo_venta', 'total_display', 'adeudo_display', 
        'vendedor', 'created_at', 'status_model'
    )
    list_filter = ('fase', 'tipo_venta', 'condicion_pago', 'was_preventa', 'is_entregado', 'created_at', 'status_model', 'almacen', 'ruta')
    search_fields = ('codigo', 'cliente__nombre', 'cliente__codigo', 'vendedor__username', 'vendedor__first_name', 'vendedor__last_name')
    ordering = ('-created_at',)
    readonly_fields = (
        'codigo_display', 'was_preventa', 'falta_inventario', 
        'is_total_cargado', 'total_pagado', 'adeudo_display',
        'created_at', 'updated_at', 'created_by', 'updated_by'
    )
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('codigo_display', 'cliente', 'almacen', 'fase', 'tipo_venta','ya_terminada','ignorada'),
            'description': 'Información general de la venta'
        }),
        ('Ruta y Vendedor', {
            'fields': ('ruta', 'vendedor'),
            'description': 'Asignación de ruta y vendedor'
        }),
        ('Montos', {
            'fields': ('total', 'total_pagado', 'adeudo_display', 'condicion_pago'),
            'description': 'Información de montos y pagos'
        }),
        ('Estado', {
            'fields': (
                'was_preventa', 'falta_inventario', 
                'is_total_cargado', 'is_entregado'
            ),
            'description': 'Estados de la venta',
            'classes': ('collapse',)
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by', 'status_model'),
            'classes': ('collapse',)
        })
    )
    
    inlines = [VentaDetalleInline, PagosVentaInline]
    
    def codigo_display(self, obj):
        """Mostrar código con ícono según fase"""
        iconos = {
            Venta.FASE_PRE_VENTA: "📋",
            Venta.FASE_VENTA_COMANDA: "🍽️",
            Venta.FASE_EN_PROCESO: "⏳",
            Venta.FASE_TERMINADA: "✅",
            Venta.FASE_CANCELADA: "❌",
        }
        icono = iconos.get(obj.fase, "📄")
        return f"{icono} {obj.codigo}"
    codigo_display.short_description = 'Código'
    codigo_display.admin_order_field = 'codigo'
    
    def fase_display(self, obj):
        """Mostrar fase con formato"""
        colores = {
            Venta.FASE_PRE_VENTA: "🔵",
            Venta.FASE_VENTA_COMANDA: "🟡",
            Venta.FASE_EN_PROCESO: "🟠",
            Venta.FASE_TERMINADA: "🟢",
            Venta.FASE_CANCELADA: "🔴",
        }
        icono = colores.get(obj.fase, "⚪")
        return f"{icono} {obj.fase}"
    fase_display.short_description = 'Fase'
    fase_display.admin_order_field = 'fase'
    
    def total_display(self, obj):
        """Mostrar total formateado"""
        return f"${obj.total:,.2f}"
    total_display.short_description = 'Total'
    total_display.admin_order_field = 'total'
    
    def adeudo_display(self, obj):
        """Mostrar adeudo con formato"""
        adeudo = obj.adeudo()
        if adeudo > 0:
            return f"❌ ${adeudo:,.2f}"
        return "✅ $0.00"
    adeudo_display.short_description = 'Adeudo'
    
    def get_readonly_fields(self, request, obj=None):
        """Campos readonly según el estado"""
        readonly = list(self.readonly_fields)
        
        # Si la venta está cancelada o terminada, hacer campos principales readonly
        if obj and obj.fase in [Venta.FASE_CANCELADA, Venta.FASE_TERMINADA]:
            readonly.extend(['cliente', 'almacen', 'fase', 'tipo_venta', 'total'])
        
        return readonly
    
    # Acciones personalizadas
    actions = ['marcar_como_entregada', 'cambiar_a_en_proceso']
    
    def marcar_como_entregada(self, request, queryset):
        """Acción para marcar ventas como entregadas"""
        ventas_actualizadas = queryset.filter(
            fase=Venta.FASE_EN_PROCESO
        ).update(
            is_entregado=True,
            fase=Venta.FASE_TERMINADA
        )
        
        if ventas_actualizadas == 0:
            self.message_user(
                request, 
                "No hay ventas en proceso en la selección.",
                level='warning'
            )
        else:
            self.message_user(
                request, 
                f"{ventas_actualizadas} venta(s) marcada(s) como entregada(s).",
                level='success'
            )
    marcar_como_entregada.short_description = "Marcar como entregadas"
    
    def cambiar_a_en_proceso(self, request, queryset):
        """Acción para cambiar ventas a estado EN PROCESO"""
        ventas_actualizadas = queryset.filter(
            fase=Venta.FASE_PRE_VENTA,
            is_total_cargado=True
        ).update(fase=Venta.FASE_EN_PROCESO)
        
        if ventas_actualizadas == 0:
            self.message_user(
                request, 
                "No hay preventas cargadas en la selección.",
                level='warning'
            )
        else:
            self.message_user(
                request, 
                f"{ventas_actualizadas} venta(s) cambiada(s) a EN PROCESO.",
                level='success'
            )
    cambiar_a_en_proceso.short_description = "Cambiar a EN PROCESO (preventas cargadas)"


@admin.register(VentaDetalle)
class VentaDetalleAdmin(admin.ModelAdmin):
    """
    Administrador para el modelo VentaDetalle
    """
    list_display = (
        'id_display', 'venta_codigo', 'producto', 'cantidad', 
        'precio_unitario', 'subtotal_display', 'is_cargado', 'is_entregado'
    )
    list_filter = ('is_cargado', 'is_entregado', 'venta__fase', 'venta__tipo_venta')
    search_fields = (
        'venta__codigo', 'producto__nombre', 'producto__codigo',
        'venta__cliente__nombre'
    )
    ordering = ('-venta__created_at',)
    readonly_fields = ('subtotal_display',)
    
    def id_display(self, obj):
        """Mostrar ID con formato"""
        return f"DET-{obj.pk:08d}"
    id_display.short_description = 'ID Detalle'
    id_display.admin_order_field = 'id'
    
    def venta_codigo(self, obj):
        """Mostrar código de la venta"""
        return obj.venta.codigo
    venta_codigo.short_description = 'Venta'
    venta_codigo.admin_order_field = 'venta__codigo'
    
    def subtotal_display(self, obj):
        """Mostrar subtotal formateado"""
        return f"${obj.subtotal:,.2f}"
    subtotal_display.short_description = 'Subtotal'
    
    def has_add_permission(self, request):
        """Los detalles se agregan desde la venta"""
        return False


@admin.register(VentaDetalleLote)
class VentaDetalleLoteAdmin(admin.ModelAdmin):
    """
    Administrador para el modelo VentaDetalleLote (trazabilidad)
    """
    list_display = (
        'id_display', 'venta_codigo', 'producto_display', 
        'lote_codigo', 'cantidad_utilizada', 'costo_unitario_lote', 'created_at'
    )
    list_filter = ('created_at', 'venta_detalle__venta__fase')
    search_fields = (
        'venta_detalle__venta__codigo', 
        'lote_inventario__codigo',
        'venta_detalle__producto__nombre'
    )
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'costo_unitario_lote')
    
    def id_display(self, obj):
        """Mostrar ID con formato"""
        return f"LOTE-{obj.pk:08d}"
    id_display.short_description = 'ID'
    id_display.admin_order_field = 'id'
    
    def venta_codigo(self, obj):
        """Mostrar código de la venta"""
        return obj.venta_detalle.venta.codigo
    venta_codigo.short_description = 'Venta'
    venta_codigo.admin_order_field = 'venta_detalle__venta__codigo'
    
    def producto_display(self, obj):
        """Mostrar nombre del producto"""
        return obj.venta_detalle.producto.nombre
    producto_display.short_description = 'Producto'
    
    def lote_codigo(self, obj):
        """Mostrar código del lote"""
        if obj.lote_inventario:
            return obj.lote_inventario.codigo if hasattr(obj.lote_inventario, 'codigo') else f"LOTE-{obj.lote_inventario.pk}"
        return "N/A"
    lote_codigo.short_description = 'Lote'
    
    def has_add_permission(self, request):
        """Los lotes se asignan automáticamente desde la API"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """No permitir eliminar para mantener trazabilidad"""
        return False


@admin.register(PagosVenta)
class PagosVentaAdmin(admin.ModelAdmin):
    """
    Administrador para el modelo PagosVenta
    """
    list_display = (
        'clave_display', 'venta_codigo', 'monto_display', 
        'metodo_pago', 'referencia', 'created_at', 'status_model'
    )
    list_filter = ('metodo_pago', 'created_at', 'status_model')
    search_fields = (
        'venta__codigo', 'referencia', 'venta__cliente__nombre'
    )
    ordering = ('-created_at',)
    readonly_fields = ('clave_display', 'created_at', 'updated_at', 'created_by', 'updated_by')
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('clave_display', 'venta', 'monto', 'metodo_pago', 'referencia'),
            'description': 'Información del pago'
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by', 'status_model'),
            'classes': ('collapse',)
        })
    )
    
    def clave_display(self, obj):
        """Mostrar clave del pago"""
        if obj and obj.pk:
            return f"💰 {obj.clave}"
        return "Se generará al guardar"
    clave_display.short_description = 'Clave'
    
    def venta_codigo(self, obj):
        """Mostrar código de la venta"""
        return obj.venta.codigo
    venta_codigo.short_description = 'Venta'
    venta_codigo.admin_order_field = 'venta__codigo'
    
    def monto_display(self, obj):
        """Mostrar monto formateado"""
        return f"${obj.monto:,.2f}"
    monto_display.short_description = 'Monto'
    monto_display.admin_order_field = 'monto'
    
    def has_delete_permission(self, request, obj=None):
        """No permitir eliminar pagos para mantener registro contable"""
        return False


# =======================================================================
#                    ADMIN DE incidencias
# =======================================================================

class IncidenciaLoteInline(admin.TabularInline):
    """
    Inline para agregar lotes a una incidencia
    """
    model = IncidenciaLote
    extra = 1
    autocomplete_fields = ['lote']
    fields = ('lote', 'cantidad', 'atendida', 'fecha_atencion', 'nota')
    readonly_fields = ('fecha_atencion',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('lote__producto', 'lote__almacen')


@admin.register(incidencia)
class IncidenciaAdmin(admin.ModelAdmin):
    """
    Admin para gestionar incidencias
    """
    list_display = (
        'id', 'descripcion_corta', 'resuelta', 'total_lotes', 
        'lotes_atendidos', 'created_at', 'status_model'
    )
    list_filter = ('resuelta', 'status_model', 'created_at')
    search_fields = ('descripcion', 'solucion')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    inlines = [IncidenciaLoteInline]
    
    fieldsets = (
        ('Información de la incidencia', {
            'fields': ('descripcion', 'solucion', 'resuelta'),
            'description': 'Datos principales de la incidencia'
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by', 'status_model'),
            'classes': ('collapse',)
        })
    )
    
    def descripcion_corta(self, obj):
        """Mostrar descripción truncada"""
        if obj.descripcion:
            return obj.descripcion[:50] + '...' if len(obj.descripcion) > 50 else obj.descripcion
        return '-'
    descripcion_corta.short_description = 'Descripción'
    
    def total_lotes(self, obj):
        """Mostrar total de lotes en la incidencia"""
        return obj.lotes_incidencia.count()
    total_lotes.short_description = 'Total Lotes'
    
    def lotes_atendidos(self, obj):
        """Mostrar cantidad de lotes atendidos"""
        atendidos = obj.lotes_incidencia.filter(atendida=True).count()
        total = obj.lotes_incidencia.count()
        return f"{atendidos}/{total}"
    lotes_atendidos.short_description = 'Atendidos'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(IncidenciaLote)
class IncidenciaLoteAdmin(admin.ModelAdmin):
    """
    Admin para gestionar Lotes de incidencias individualmente
    """
    list_display = (
        'id', 'incidencia_id', 'lote_info', 'producto_nombre', 
        'cantidad', 'atendida', 'fecha_atencion', 'status_model'
    )
    list_filter = ('atendida', 'status_model', 'created_at')
    search_fields = (
        'incidencia__descripcion', 
        'lote__producto__nombre', 
        'lote__producto__codigo',
        'nota'
    )
    ordering = ('-created_at',)
    autocomplete_fields = ['incidencia', 'lote']
    readonly_fields = ('fecha_atencion', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Relaciones', {
            'fields': ('incidencia', 'lote'),
        }),
        ('Detalles', {
            'fields': ('cantidad', 'atendida', 'fecha_atencion', 'nota'),
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at', 'status_model'),
            'classes': ('collapse',)
        })
    )
    
    def incidencia_id(self, obj):
        return f"incidencia #{obj.incidencia.id}"
    incidencia_id.short_description = 'incidencia'
    incidencia_id.admin_order_field = 'incidencia__id'
    
    def lote_info(self, obj):
        if obj.lote:
            return f"Lote #{obj.lote.id}"
        return '-'
    lote_info.short_description = 'Lote'
    
    def producto_nombre(self, obj):
        if obj.lote and obj.lote.producto:
            return obj.lote.producto.nombre
        return '-'
    producto_nombre.short_description = 'Producto'
    producto_nombre.admin_order_field = 'lote__producto__nombre'
