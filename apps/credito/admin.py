from django.contrib import admin
from django.db.models import Sum
from django.utils import timezone
from .models import CreditoCliente, PagosCredito


# ================================================================
#           ADMINISTRADOR DE CRÉDITOS DE CLIENTES
# ================================================================

class PagosCreditoInline(admin.TabularInline):
    """
    Inline para mostrar pagos dentro de un crédito
    """
    model = PagosCredito
    extra = 0
    fields = ('monto', 'metodo_pago', 'created_at', 'created_by')
    readonly_fields = ('created_at', 'created_by')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        # Los pagos se registran desde la API
        return False


@admin.register(CreditoCliente)
class CreditoClienteAdmin(admin.ModelAdmin):
    """
    Administrador para CreditoCliente (Dispersiones de crédito)
    """
    list_display = (
        'id_display', 'cliente_display', 'monto_display',
        'monto_pagado_display', 'adeudo_display', 'estado_display',
        'fecha', 'fecha_vencimiento_display', 'dias_plazo', 'status_model'
    )
    list_filter = (
        'estado', 'is_pagado', 'fecha', 'fecha_vencimiento',
        'status_model', 'cliente'
    )
    search_fields = (
        'cliente__codigo', 'cliente__nombre', 'cliente__apellido_paterno',
        'cliente__apellido_materno', 'referencia', 'observaciones'
    )
    ordering = ('-fecha', '-created_at')
    readonly_fields = (
        'monto_pagado', 'is_pagado', 'fecha_pago', 'fecha_vencimiento',
        'adeudo_display', 'total_pagos_display', 'vencimiento_info',
        'created_at', 'updated_at', 'created_by', 'updated_by'
    )
    
    fieldsets = (
        ('Información del Cliente', {
            'fields': ('cliente', 'fecha'),
            'description': 'Cliente y fecha de la dispersión'
        }),
        ('Monto del Crédito', {
            'fields': (
                'monto', 'monto_pagado', 'adeudo_display', 'estado'
            ),
            'description': 'Montos y estado del crédito'
        }),
        ('Plazos y Vencimiento', {
            'fields': (
                'dias_plazo', 'fecha_vencimiento', 'vencimiento_info'
            ),
            'description': 'Información de plazos'
        }),
        ('Estado de Pago', {
            'fields': (
                'is_pagado', 'fecha_pago', 'total_pagos_display'
            ),
            'description': 'Estado de liquidación',
            'classes': ('collapse',)
        }),
        ('Información Adicional', {
            'fields': ('referencia', 'observaciones'),
            'description': 'Notas y referencias'
        }),
        ('Auditoría', {
            'fields': (
                'created_at', 'updated_at', 'created_by', 
                'updated_by', 'status_model'
            ),
            'classes': ('collapse',)
        })
    )
    
    inlines = [PagosCreditoInline]
    
    # Acciones personalizadas
    actions = ['verificar_vencimientos', 'calcular_totales']
    
    def id_display(self, obj):
        """Mostrar ID con ícono según estado"""
        iconos = {
            CreditoCliente.ACTIVA: "💳",
            CreditoCliente.PAGADA: "✅",
        }
        icono = iconos.get(obj.estado, "📄")
        
        if obj.ha_vencido and not obj.is_pagado:
            icono = "⚠️"
        
        return f"{icono} DISP-{obj.pk:08d}"
    id_display.short_description = 'ID Dispersión'
    id_display.admin_order_field = 'id'
    
    def cliente_display(self, obj):
        """Mostrar información del cliente"""
        return f"{obj.cliente.codigo} - {obj.cliente.get_full_name}"
    cliente_display.short_description = 'Cliente'
    cliente_display.admin_order_field = 'cliente__codigo'
    
    def monto_display(self, obj):
        """Mostrar monto formateado"""
        return f"💰 ${obj.monto:,.2f}"
    monto_display.short_description = 'Monto Dispersado'
    monto_display.admin_order_field = 'monto'
    
    def monto_pagado_display(self, obj):
        """Mostrar monto pagado formateado"""
        if obj.monto_pagado > 0:
            return f"✅ ${obj.monto_pagado:,.2f}"
        return "$0.00"
    monto_pagado_display.short_description = 'Pagado'
    monto_pagado_display.admin_order_field = 'monto_pagado'
    
    def adeudo_display(self, obj):
        """Mostrar adeudo actual con formato"""
        adeudo = obj.adeudo_actual()
        if adeudo > 0:
            if obj.ha_vencido:
                return f"⚠️ ${adeudo:,.2f} (VENCIDO)"
            return f"❌ ${adeudo:,.2f}"
        return "✅ $0.00 (LIQUIDADO)"
    adeudo_display.short_description = 'Adeudo Actual'
    
    def estado_display(self, obj):
        """Mostrar estado con color"""
        if obj.is_pagado:
            return "🟢 PAGADA"
        elif obj.ha_vencido:
            return "🔴 VENCIDA"
        else:
            return "🟡 ACTIVA"
    estado_display.short_description = 'Estado'
    estado_display.admin_order_field = 'estado'
    
    def fecha_vencimiento_display(self, obj):
        """Mostrar fecha de vencimiento con indicador"""
        if not obj.fecha_vencimiento:
            return "-"
        
        if obj.is_pagado:
            return f"✅ {obj.fecha_vencimiento.strftime('%d/%m/%Y')}"
        elif obj.ha_vencido:
            dias_vencido = (timezone.now().date() - obj.fecha_vencimiento).days
            return f"⚠️ {obj.fecha_vencimiento.strftime('%d/%m/%Y')} ({dias_vencido} días vencido)"
        else:
            dias_restantes = (obj.fecha_vencimiento - timezone.now().date()).days
            return f"🕒 {obj.fecha_vencimiento.strftime('%d/%m/%Y')} ({dias_restantes} días)"
    fecha_vencimiento_display.short_description = 'Vencimiento'
    fecha_vencimiento_display.admin_order_field = 'fecha_vencimiento'
    
    def total_pagos_display(self, obj):
        """Mostrar total de pagos registrados"""
        count = obj.pagos.count()
        total = obj.pagos.aggregate(Sum('monto'))['monto__sum'] or 0
        return f"💵 {count} pago(s) = ${total:,.2f}"
    total_pagos_display.short_description = 'Total Pagos'
    
    def vencimiento_info(self, obj):
        """Información sobre el vencimiento"""
        if not obj.fecha_vencimiento:
            return "No definido"
        
        if obj.is_pagado:
            return f"✅ Liquidado el {obj.fecha_pago.strftime('%d/%m/%Y') if obj.fecha_pago else 'N/A'}"
        elif obj.ha_vencido:
            dias_vencido = (timezone.now().date() - obj.fecha_vencimiento).days
            return f"⚠️ Vencido hace {dias_vencido} día(s)"
        else:
            dias_restantes = (obj.fecha_vencimiento - timezone.now().date()).days
            return f"🕒 Vence en {dias_restantes} día(s)"
    vencimiento_info.short_description = 'Estado de Vencimiento'
    
    def verificar_vencimientos(self, request, queryset):
        """Acción para verificar vencimientos"""
        activos = queryset.filter(is_pagado=False)
        vencidos = sum(1 for credito in activos if credito.ha_vencido)
        
        self.message_user(
            request,
            f"De {activos.count()} crédito(s) activo(s), {vencidos} está(n) vencido(s).",
            level='warning' if vencidos > 0 else 'info'
        )
    verificar_vencimientos.short_description = "Verificar vencimientos"
    
    def calcular_totales(self, request, queryset):
        """Acción para calcular totales de la selección"""
        total_dispersado = queryset.aggregate(Sum('monto'))['monto__sum'] or 0
        total_pagado = queryset.aggregate(Sum('monto_pagado'))['monto_pagado__sum'] or 0
        adeudo_total = total_dispersado - total_pagado
        
        self.message_user(
            request,
            f"Totales: Dispersado: ${total_dispersado:,.2f} | "
            f"Pagado: ${total_pagado:,.2f} | "
            f"Adeudo: ${adeudo_total:,.2f}",
            level='info'
        )
    calcular_totales.short_description = "Calcular totales"
    
    def get_readonly_fields(self, request, obj=None):
        """Campos readonly según el estado"""
        readonly = list(self.readonly_fields)
        
        # Si ya está pagado, hacer todo readonly
        if obj and obj.is_pagado:
            readonly.extend(['cliente', 'monto', 'fecha', 'dias_plazo', 'estado', 'referencia'])
        
        return readonly


@admin.register(PagosCredito)
class PagosCreditoAdmin(admin.ModelAdmin):
    """
    Administrador para PagosCredito
    """
    list_display = (
        'id_display', 'credito_display', 'cliente_display',
        'monto_display', 'metodo_pago', 'created_at', 'created_by', 'status_model'
    )
    list_filter = (
        'metodo_pago', 'created_at', 'status_model',
        'credito__cliente'
    )
    search_fields = (
        'credito__cliente__codigo', 'credito__cliente__nombre',
        'credito__referencia', 'created_by__username'
    )
    ordering = ('-created_at',)
    readonly_fields = (
        'credito', 'monto', 'metodo_pago',
        'created_at', 'updated_at', 'created_by', 'updated_by'
    )
    
    fieldsets = (
        ('Información del Pago', {
            'fields': ('credito', 'monto', 'metodo_pago'),
            'description': 'Detalles del pago realizado'
        }),
        ('Auditoría', {
            'fields': (
                'created_at', 'updated_at', 'created_by', 
                'updated_by', 'status_model'
            ),
            'classes': ('collapse',)
        })
    )
    
    def id_display(self, obj):
        """Mostrar ID con formato"""
        return f"💵 PAGO-{obj.pk:08d}"
    id_display.short_description = 'ID Pago'
    id_display.admin_order_field = 'id'
    
    def credito_display(self, obj):
        """Mostrar información del crédito"""
        if obj.credito:
            return f"DISP-{obj.credito.pk:08d} (${obj.credito.monto:,.2f})"
        return "N/A"
    credito_display.short_description = 'Dispersión'
    
    def cliente_display(self, obj):
        """Mostrar información del cliente"""
        if obj.credito and obj.credito.cliente:
            return f"{obj.credito.cliente.codigo} - {obj.credito.cliente.get_full_name}"
        return "N/A"
    cliente_display.short_description = 'Cliente'
    
    def monto_display(self, obj):
        """Mostrar monto formateado"""
        return f"✅ ${obj.monto:,.2f}"
    monto_display.short_description = 'Monto Pagado'
    monto_display.admin_order_field = 'monto'
    
    def has_add_permission(self, request):
        """Los pagos se registran desde la API"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """No permitir eliminar pagos para mantener registro contable"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """No permitir editar pagos una vez registrados"""
        return False
