from django.contrib import admin
from django.db.models import Sum, Count
from .models import (
    Piso, Zona, Rack, LoteInventario, 
    MovimientoInventario, ProductosMovimiento, 
    Transformacion, 
    ProductosSolicitud, 
)
from apps.erp.models import Almacen



@admin.register(Piso)
class PisoAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "almacen", "status_model", "created_at")
    list_filter = ("almacen", "status_model")
    search_fields = ("nombre",)

@admin.register(Zona)
class ZonaAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "piso", "status_model", "created_at")
    list_filter = ("piso", "status_model")
    search_fields = ("nombre",)

@admin.register(Rack)
class RackAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "zona", "status_model", "created_at")
    list_filter = ("zona", "status_model")
    search_fields = ("nombre",)

# ================================================================
#           ADMINISTRADOR MEJORADO DE LOTES DE INVENTARIO
# ================================================================

@admin.register(LoteInventario)
class LoteInventarioAdmin(admin.ModelAdmin):
	"""
	Administrador mejorado y super amigable para LoteInventario
	Con funcionalidad de traspaso entre almacenes
	"""
	list_display = (
		'id_display',
		'producto_display', 
		'almacen_display',
		'ubicacion_display',
		'cantidad_display',
		'costo_unitario_display',
		'costo_total_display',
		'estado_stock',
		'dias_inventario',
		'fecha_ingreso_display',
		'fecha_vencimiento_display',
		'status_badge'
	)
	
	list_filter = (
		('almacen', admin.RelatedOnlyFieldListFilter),
		('producto__categoria', admin.RelatedOnlyFieldListFilter),
		'status_model',
		('fecha_ingreso', admin.DateFieldListFilter),
		('fecha_vencimiento', admin.DateFieldListFilter),
	)
	
	search_fields = (
		'producto__nombre', 
		'producto__codigo',
		'almacen__nombre',
		'ubicacion__nombre',
		'id'
	)
	
	readonly_fields = (
		'id_display_readonly',
		'costo_total_readonly',
		'dias_inventario_readonly',
		'valor_inventario_readonly',
		'estado_stock_readonly',
		'historial_movimientos',
		'fecha_ingreso',
		'created_at', 
		'updated_at', 
		'created_by', 
		'updated_by'
	)
	
	ordering = ('-fecha_ingreso', '-id')
	
	list_per_page = 25
	
	date_hierarchy = 'fecha_ingreso'
	
	# Mostrar acciones arriba y abajo
	actions_on_top = True
	actions_on_bottom = True
	
	fieldsets = (
		('📦 Información del Lote', {
			'fields': (
				'id_display_readonly',
				('producto', 'almacen'),
			),
			'description': 'Información básica del lote de inventario'
		}),
		('📍 Ubicación (Solo CEDIS)', {
			'fields': ('ubicacion',),
			'description': 'Ubicación física del producto (solo para almacenes CEDIS)',
			'classes': ('collapse',)
		}),
		('📊 Cantidades y Costos', {
			'fields': (
				('cantidad', 'costo_unitario'),
				'costo_total_readonly',
				'valor_inventario_readonly',
				'estado_stock_readonly',
			),
			'description': 'Información de cantidades, costos y valorización'
		}),
		('📅 Fechas', {
			'fields': (
				'fecha_ingreso',
				'fecha_vencimiento',
				'dias_inventario_readonly',
			),
			'description': 'Control de fechas de ingreso y vencimiento'
		}),
		('📋 Historial', {
			'fields': ('historial_movimientos',),
			'description': 'Movimientos asociados a este lote',
			'classes': ('collapse',)
		}),
		('🔧 Auditoría', {
			'fields': (
				'status_model',
				('created_at', 'updated_at'),
				('created_by', 'updated_by'),
			),
			'classes': ('collapse',)
		})
	)
	
	# Acciones masivas personalizadas
	actions = [
		'marcar_como_activo',
		'marcar_como_inactivo',
		'mover_producto_entre_almacenes',
		'calcular_totales_seleccion'
	]
	
	# ============================================================
	#                  MÉTODOS DE DISPLAY
	# ============================================================
	
	def id_display(self, obj):
		"""ID con badge de color según estado"""
		from django.utils.html import format_html
		color = '#28a745' if obj.status_model == 'ACTIVE' else '#dc3545'
		lote_id = str(obj.pk).zfill(8)  # Convertir a string con padding de 8 dígitos
		return format_html(
			'<span style="background-color: {}; color: white; padding: 3px 8px; '
			'border-radius: 3px; font-weight: bold; font-size: 11px;">'
			'LOTE-{}</span>',
			color, lote_id
		)
	id_display.short_description = 'ID Lote'
	id_display.admin_order_field = 'id'
	
	def id_display_readonly(self, obj):
		"""ID para readonly fields"""
		if obj.pk:
			return self.id_display(obj)
		return "Se asignará automáticamente"
	id_display_readonly.short_description = 'ID del Lote'
	
	def producto_display(self, obj):
		"""Producto con código y categoría"""
		from django.utils.html import format_html
		if obj.producto:
			categoria = obj.producto.categoria.nombre if obj.producto.categoria else "Sin categoría"
			return format_html(
				'<div style="line-height: 1.4;">'
				'<strong style="font-size: 13px;">📦 {}</strong><br>'
				'<span style="color: #666; font-size: 11px;">Código: {} | {}</span>'
				'</div>',
				obj.producto.nombre,
				obj.producto.codigo,
				categoria
			)
		return format_html('<span style="color: #999;">Sin producto</span>')
	producto_display.short_description = 'Producto'
	producto_display.admin_order_field = 'producto__nombre'
	
	def almacen_display(self, obj):
		"""Almacén con icono"""
		from django.utils.html import format_html
		if obj.almacen:
			icono = '🏢' if obj.almacen.is_cedis else '🏪'
			tipo = 'CEDIS' if obj.almacen.is_cedis else 'PUNTO DE VENTA'
			return format_html(
				'<div style="line-height: 1.4;">'
				'<strong>{} {}</strong><br>'
				'<span style="color: #666; font-size: 11px;">{}</span>'
				'</div>',
				icono, obj.almacen.nombre, tipo
			)
		return format_html('<span style="color: #999;">Sin almacén</span>')
	almacen_display.short_description = 'Almacén'
	almacen_display.admin_order_field = 'almacen__nombre'
	
	def ubicacion_display(self, obj):
		"""Ubicación completa (Piso > Zona > Rack)"""
		from django.utils.html import format_html
		if obj.ubicacion:
			return format_html(
				'<div style="line-height: 1.4; font-size: 11px;">'
				'📍 <strong>{}</strong><br>'
				'<span style="color: #666;">Zona: {} | Piso: {}</span>'
				'</div>',
				obj.ubicacion.nombre,
				obj.ubicacion.zona.nombre,
				obj.ubicacion.zona.piso.nombre
			)
		return format_html('<span style="color: #999;">-</span>')
	ubicacion_display.short_description = 'Ubicación'
	ubicacion_display.admin_order_field = 'ubicacion__nombre'
	
	def cantidad_display(self, obj):
		"""Cantidad con formato y color según nivel"""
		from django.utils.html import format_html
		if obj.cantidad <= 0:
			color = '#dc3545'
			icono = '❌'
		elif obj.cantidad < 10:
			color = '#ffc107'
			icono = '⚠️'
		else:
			color = '#28a745'
			icono = '✅'
		
		unidad = obj.producto.unidad_sat.nombre if obj.producto and obj.producto.unidad_sat else 'unidades'
		cantidad_fmt = f"{obj.cantidad:,.2f}"
		
		return format_html(
			'<div style="text-align: center;">'
			'<span style="font-size: 20px;">{}</span><br>'
			'<strong style="color: {}; font-size: 14px;">{}</strong><br>'
			'<span style="color: #666; font-size: 10px;">{}</span>'
			'</div>',
			icono, color, cantidad_fmt, unidad
		)
	cantidad_display.short_description = 'Cantidad'
	cantidad_display.admin_order_field = 'cantidad'
	
	def costo_unitario_display(self, obj):
		"""Costo unitario formateado"""
		from django.utils.html import format_html
		costo_fmt = f"${obj.costo_unitario:,.2f}"
		return format_html(
			'<div style="text-align: right;">'
			'<strong style="font-size: 13px;">{}</strong><br>'
			'<span style="color: #666; font-size: 10px;">por unidad</span>'
			'</div>',
			costo_fmt
		)
	costo_unitario_display.short_description = 'Costo Unit.'
	costo_unitario_display.admin_order_field = 'costo_unitario'
	
	def costo_total_display(self, obj):
		"""Costo total del lote"""
		from django.utils.html import format_html
		total = obj.cantidad * obj.costo_unitario
		total_fmt = f"💰 ${total:,.2f}"
		return format_html(
			'<div style="text-align: right; background-color: #f8f9fa; padding: 5px; border-radius: 3px;">'
			'<strong style="color: #007bff; font-size: 14px;">{}</strong>'
			'</div>',
			total_fmt
		)
	costo_total_display.short_description = 'Valor Total'
	
	def costo_total_readonly(self, obj):
		"""Costo total para readonly"""
		if obj.pk:
			total = obj.cantidad * obj.costo_unitario
			return f"${total:,.2f} MXN"
		return "Se calculará automáticamente"
	costo_total_readonly.short_description = 'Valor Total del Lote'
	
	def valor_inventario_readonly(self, obj):
		"""Valor total del inventario"""
		if obj.pk:
			return self.costo_total_readonly(obj)
		return "-"
	valor_inventario_readonly.short_description = 'Valorización'
	
	def estado_stock(self, obj):
		"""Estado del stock con colores"""
		from django.utils.html import format_html
		if obj.cantidad <= 0:
			return format_html(
				'<span style="background-color: #dc3545; color: white; padding: 4px 10px; '
				'border-radius: 12px; font-size: 11px; font-weight: bold;">'
				'🚫 AGOTADO</span>'
			)
		elif obj.cantidad < 10:
			return format_html(
				'<span style="background-color: #ffc107; color: #000; padding: 4px 10px; '
				'border-radius: 12px; font-size: 11px; font-weight: bold;">'
				'⚠️ STOCK BAJO</span>'
			)
		elif obj.cantidad < 50:
			return format_html(
				'<span style="background-color: #17a2b8; color: white; padding: 4px 10px; '
				'border-radius: 12px; font-size: 11px; font-weight: bold;">'
				'📊 STOCK MEDIO</span>'
			)
		else:
			return format_html(
				'<span style="background-color: #28a745; color: white; padding: 4px 10px; '
				'border-radius: 12px; font-size: 11px; font-weight: bold;">'
				'✅ STOCK ALTO</span>'
			)
	estado_stock.short_description = 'Estado Stock'
	
	def estado_stock_readonly(self, obj):
		"""Estado del stock para readonly"""
		if obj.pk:
			return self.estado_stock(obj)
		return "-"
	estado_stock_readonly.short_description = 'Estado del Stock'
	
	def dias_inventario(self, obj):
		"""Días desde el ingreso"""
		from django.utils.html import format_html
		from django.utils import timezone
		dias = (timezone.now().date() - obj.fecha_ingreso.date()).days
		
		if dias == 0:
			color = '#28a745'
			texto = 'HOY'
		elif dias < 7:
			color = '#17a2b8'
			texto = f'{dias} día{"s" if dias > 1 else ""}'
		elif dias < 30:
			color = '#ffc107'
			texto = f'{dias} días'
		else:
			color = '#dc3545'
			texto = f'{dias} días'
		
		return format_html(
			'<span style="color: {}; font-weight: bold; font-size: 12px;">'
			'📅 {}</span>',
			color, texto
		)
	dias_inventario.short_description = 'Antigüedad'
	
	def dias_inventario_readonly(self, obj):
		"""Días de inventario para readonly"""
		if obj.pk:
			from django.utils import timezone
			dias = (timezone.now().date() - obj.fecha_ingreso.date()).days
			return f"{dias} día(s) desde el ingreso"
		return "-"
	dias_inventario_readonly.short_description = 'Antigüedad del Lote'
	
	def fecha_ingreso_display(self, obj):
		"""Fecha de ingreso formateada"""
		from django.utils.html import format_html
		return format_html(
			'<span style="font-size: 12px;">📥 {}</span>',
			obj.fecha_ingreso.strftime('%d/%m/%Y %H:%M')
		)
	fecha_ingreso_display.short_description = 'Fecha Ingreso'
	fecha_ingreso_display.admin_order_field = 'fecha_ingreso'
	
	def fecha_vencimiento_display(self, obj):
		"""Fecha de vencimiento con alerta"""
		from django.utils.html import format_html
		from django.utils import timezone
		if obj.fecha_vencimiento:
			dias_hasta_vencer = (obj.fecha_vencimiento.date() - timezone.now().date()).days
			
			if dias_hasta_vencer < 0:
				color = '#dc3545'
				icono = '❌'
				texto = 'VENCIDO'
			elif dias_hasta_vencer < 7:
				color = '#ffc107'
				icono = '⚠️'
				texto = f'{dias_hasta_vencer} días'
			else:
				color = '#28a745'
				icono = '✅'
				texto = f'{dias_hasta_vencer} días'
			
			return format_html(
				'<div style="line-height: 1.4;">'
				'<span style="font-size: 12px;">{} {}</span><br>'
				'<span style="color: {}; font-weight: bold; font-size: 10px;">{}</span>'
				'</div>',
				icono, obj.fecha_vencimiento.strftime('%d/%m/%Y'), color, texto
			)
		return format_html('<span style="color: #999;">Sin vencimiento</span>')
	fecha_vencimiento_display.short_description = 'Vencimiento'
	fecha_vencimiento_display.admin_order_field = 'fecha_vencimiento'
	
	def status_badge(self, obj):
		"""Badge del estado del modelo"""
		from django.utils.html import format_html
		if obj.status_model == 'ACTIVE':
			return format_html(
				'<span style="background-color: #28a745; color: white; padding: 3px 10px; '
				'border-radius: 12px; font-size: 10px; font-weight: bold;">'
				'✅ ACTIVO</span>'
			)
		else:
			return format_html(
				'<span style="background-color: #6c757d; color: white; padding: 3px 10px; '
				'border-radius: 12px; font-size: 10px; font-weight: bold;">'
				'🚫 INACTIVO</span>'
			)
	status_badge.short_description = 'Estado'
	status_badge.admin_order_field = 'status_model'
	
	def historial_movimientos(self, obj):
		"""Mostrar movimientos relacionados con este lote"""
		from django.utils.html import format_html
		if obj.pk:
			movimientos = ProductosMovimiento.objects.filter(
				lote=obj
			).select_related('movimiento', 'producto').order_by('-created_at')[:10]
			
			if movimientos:
				html = '<div style="max-height: 300px; overflow-y: auto;">'
				html += '<table style="width: 100%; border-collapse: collapse;">'
				html += '<thead><tr style="background-color: #f8f9fa;">'
				html += '<th style="padding: 8px; border: 1px solid #dee2e6;">Fecha</th>'
				html += '<th style="padding: 8px; border: 1px solid #dee2e6;">Tipo</th>'
				html += '<th style="padding: 8px; border: 1px solid #dee2e6;">Movimiento</th>'
				html += '<th style="padding: 8px; border: 1px solid #dee2e6;">Cantidad</th>'
				html += '</tr></thead><tbody>'
				
				for mov in movimientos:
					tipo_color = '#28a745' if mov.movimiento.tipo == 'ENTRADA' else '#dc3545'
					html += f'<tr>'
					html += f'<td style="padding: 8px; border: 1px solid #dee2e6; font-size: 11px;">{mov.created_at.strftime("%d/%m/%Y %H:%M")}</td>'
					html += f'<td style="padding: 8px; border: 1px solid #dee2e6;"><span style="color: {tipo_color}; font-weight: bold;">{mov.movimiento.tipo}</span></td>'
					html += f'<td style="padding: 8px; border: 1px solid #dee2e6; font-size: 11px;">{mov.movimiento.movimiento}</td>'
					html += f'<td style="padding: 8px; border: 1px solid #dee2e6; text-align: right; font-weight: bold;">{mov.cantidad:,.2f}</td>'
					html += f'</tr>'
				
				html += '</tbody></table></div>'
				return format_html(html)
			
			return format_html('<p style="color: #999;">No hay movimientos registrados para este lote.</p>')
		return "Guarde el lote para ver el historial"
	historial_movimientos.short_description = 'Historial de Movimientos'
	
	# ============================================================
	#                  ACCIONES MASIVAS
	# ============================================================
	
	def marcar_como_activo(self, request, queryset):
		"""Marcar lotes seleccionados como activos"""
		updated = queryset.update(status_model='ACTIVE')
		self.message_user(
			request,
			f'✅ {updated} lote(s) marcado(s) como ACTIVO.',
			level='success'
		)
	marcar_como_activo.short_description = '✅ Marcar como ACTIVO'
	
	def marcar_como_inactivo(self, request, queryset):
		"""Marcar lotes seleccionados como inactivos"""
		updated = queryset.update(status_model='INACTIVE')
		self.message_user(
			request,
			f'🚫 {updated} lote(s) marcado(s) como INACTIVO.',
			level='warning'
		)
	marcar_como_inactivo.short_description = '🚫 Marcar como INACTIVO'
	
	def calcular_totales_seleccion(self, request, queryset):
		"""Calcular totales de los lotes seleccionados"""
		from django.db.models import Sum, F, DecimalField
		from django.db.models.functions import Coalesce
		
		totales = queryset.aggregate(
			total_cantidad=Coalesce(Sum('cantidad'), 0, output_field=DecimalField()),
			total_valor=Coalesce(
				Sum(F('cantidad') * F('costo_unitario'), output_field=DecimalField()),
				0,
				output_field=DecimalField()
			)
		)
		
		self.message_user(
			request,
			f'📊 Totales calculados: {queryset.count()} lote(s) seleccionado(s) | '
			f'Cantidad Total: {totales["total_cantidad"]:,.2f} unidades | '
			f'Valor Total: ${totales["total_valor"]:,.2f} MXN',
			level='info'
		)
	calcular_totales_seleccion.short_description = '📊 Calcular totales de selección'
	
	def mover_producto_entre_almacenes(self, request, queryset):
		"""Mover productos entre almacenes FIJOS"""
		from django import forms
		from django.shortcuts import render
		from django.db import transaction
		from django.utils import timezone
		
		print(f"DEBUG INICIO: Método mover_producto_entre_almacenes llamado")
		print(f"DEBUG: request.method = {request.method}")
		print(f"DEBUG: request.POST = {request.POST}")
		print(f"DEBUG: 'aplicar_movimiento' in request.POST = {'aplicar_movimiento' in request.POST}")
		
		# Solo permitir seleccionar un lote a la vez
		if queryset.count() != 1:
			self.message_user(
				request,
				'⚠️ Debe seleccionar exactamente UN lote para mover entre almacenes.',
				level='warning'
			)
			return
		
		lote_origen = queryset.first()
		
		# Validar que el lote tenga almacén tipo FIJO
		if not lote_origen.almacen:
			self.message_user(
				request,
				'❌ El lote seleccionado no tiene almacén asignado.',
				level='error'
			)
			return
		
		if lote_origen.almacen.tipo != Almacen.TIPO_FIJO:
			self.message_user(
				request,
				f'❌ El almacén origen debe ser tipo FIJO. Actual: {lote_origen.almacen.get_tipo_display()}',
				level='error'
			)
			return
		
		# Clase del formulario de movimiento
		class MoverProductoForm(forms.Form):
			almacen_destino = forms.ModelChoiceField(
				queryset=Almacen.objects.filter(
					#tipo=Almacen.TIPO_FIJO,
					status_model='ACTIVE'
				).exclude(id=lote_origen.almacen.id),
				label="Almacén Destino",
				help_text="Seleccione el almacén destino (solo tipo FIJO, diferente al origen)",
				widget=forms.Select(attrs={'class': 'vTextField'})
			)
			
			cantidad = forms.DecimalField(
				label="Cantidad a mover",
				min_value=0.01,
				max_value=float(lote_origen.cantidad),
				decimal_places=2,
				initial=lote_origen.cantidad,
				help_text=f"Cantidad disponible: {lote_origen.cantidad:,.2f}",
				widget=forms.NumberInput(attrs={
					'class': 'vTextField',
					'step': '0.01'
				})
			)
			
			ubicacion_destino = forms.ModelChoiceField(
				queryset=Rack.objects.filter(status_model='ACTIVE').select_related('zona__piso'),
				label="Ubicación Destino (Rack)",
				required=False,
				help_text="Opcional: Solo si el almacén destino es CEDIS",
				widget=forms.Select(attrs={'class': 'vTextField'})
			)
			
			observaciones = forms.CharField(
				label="Observaciones",
				required=False,
				widget=forms.Textarea(attrs={
					'class': 'vLargeTextField',
					'rows': 3,
					'placeholder': 'Motivo del movimiento, detalles adicionales, etc.'
				})
			)
		
		# Si es la primera vez (GET), mostrar el formulario
		if 'aplicar_movimiento' not in request.POST:
			form = MoverProductoForm()
			
			context = {
				'form': form,
				'lote': {
					'id': lote_origen.id,
					'producto': lote_origen.producto.nombre if lote_origen.producto else 'Sin producto',
					'almacen_origen': lote_origen.almacen.nombre,
					'cantidad_disponible': lote_origen.cantidad,
					'costo_unitario': lote_origen.costo_unitario,
					'fecha_ingreso': lote_origen.fecha_ingreso,
					'fecha_vencimiento': lote_origen.fecha_vencimiento,
					'ubicacion_origen': lote_origen.ubicacion.nombre if lote_origen.ubicacion else 'Sin ubicación'
				},
				'opts': self.model._meta,
				'title': 'Mover Producto entre Almacenes',
			}
			
			return render(request, 'admin/inventario/mover_producto_form.html', context)
		
		# Si es POST, procesar el formulario
		print(f"DEBUG: POST recibido, request.POST = {request.POST}")
		form = MoverProductoForm(request.POST)
		
		print(f"DEBUG: Formulario creado, is_valid() = {form.is_valid()}")
		if not form.is_valid():
			print(f"DEBUG: ERRORES DEL FORMULARIO: {form.errors}")
		
		if form.is_valid():
			almacen_destino = form.cleaned_data['almacen_destino']
			cantidad = form.cleaned_data['cantidad']
			ubicacion_destino = form.cleaned_data['ubicacion_destino']
			observaciones = form.cleaned_data['observaciones']
			
			print(f"DEBUG: Datos del formulario - almacen_destino: {almacen_destino}, cantidad: {cantidad}")
			
			# Validaciones adicionales
			if cantidad > lote_origen.cantidad:
				self.message_user(
					request,
					f'❌ Cantidad insuficiente. Disponible: {lote_origen.cantidad:,.2f}, Solicitado: {cantidad:,.2f}',
					level='error'
				)
				return
			
			# Si el almacén destino NO es CEDIS, ubicacion_destino debe ser null
			if not almacen_destino.is_cedis:
				ubicacion_destino = None
			
			# Procesar movimiento
			print(f"DEBUG: Iniciando transacción atómica...")
			try:
				with transaction.atomic():
					print(f"DEBUG: Dentro de transaction.atomic()")
					# 1. Crear MovimientoInventario de SALIDA
					movimiento_salida = MovimientoInventario.objects.create(
						almacen=lote_origen.almacen,
						tipo=MovimientoInventario.TIPO_SALIDA,
						movimiento=MovimientoInventario.SALIDA_TRASPASO,
						nota=f'Movimiento hacia {almacen_destino.nombre}. {observaciones}'
					)
					print(f"DEBUG: MovimientoInventario SALIDA creado ID: {movimiento_salida.id}")
					
					# 2. Crear ProductosMovimiento de SALIDA
					prod_mov_salida = ProductosMovimiento.objects.create(
						movimiento=movimiento_salida,
						producto=lote_origen.producto,
						lote=lote_origen,
						cantidad=cantidad,
						costo_unitario=lote_origen.costo_unitario
					)
					print(f"DEBUG: ProductosMovimiento SALIDA creado ID: {prod_mov_salida.id}")
					
					# 3. Reducir cantidad del lote origen
					cantidad_antes = lote_origen.cantidad
					lote_origen.cantidad -= cantidad
					lote_origen.save(update_fields=['cantidad', 'status_model'])
					lote_origen.refresh_from_db()
					print(f"DEBUG: Lote origen ID {lote_origen.id} - Cantidad antes: {cantidad_antes}, después: {lote_origen.cantidad}")
					
					# 4. Crear MovimientoInventario de ENTRADA
					movimiento_entrada = MovimientoInventario.objects.create(
						almacen=almacen_destino,
						tipo=MovimientoInventario.TIPO_ENTRADA,
						movimiento=MovimientoInventario.ENTRADA_TRASPASO,
						nota=f'Movimiento desde {lote_origen.almacen.nombre}. {observaciones}'
					)
					
					# 5. Buscar lote existente en destino con las mismas características
					lote_destino = LoteInventario.objects.filter(
						producto=lote_origen.producto,
						almacen=almacen_destino,
						ubicacion=ubicacion_destino,
						costo_unitario=lote_origen.costo_unitario,
						fecha_vencimiento=lote_origen.fecha_vencimiento,
						status_model='ACTIVE'
					).first()
					
					if lote_destino:
						# Si existe, actualizar cantidad
						cantidad_destino_antes = lote_destino.cantidad
						lote_destino.cantidad += cantidad
						lote_destino.save(update_fields=['cantidad', 'status_model'])
						lote_destino.refresh_from_db()
						print(f"DEBUG: Lote destino ID {lote_destino.id} - Cantidad antes: {cantidad_destino_antes}, después: {lote_destino.cantidad}")
						mensaje_lote = f'actualizado (ID: {lote_destino.id})'
					else:
						# Si no existe, crear nuevo lote duplicando características del origen
						lote_destino = LoteInventario.objects.create(
							producto=lote_origen.producto,
							almacen=almacen_destino,
							ubicacion=ubicacion_destino,  # null si no es CEDIS
							cantidad=cantidad,
							costo_unitario=lote_origen.costo_unitario,
							fecha_ingreso=lote_origen.fecha_ingreso,  # Misma fecha de ingreso
							fecha_vencimiento=lote_origen.fecha_vencimiento,  # Misma fecha de vencimiento
							status_model='ACTIVE'
						)
						print(f"DEBUG: Nuevo lote creado ID {lote_destino.id} - Cantidad: {lote_destino.cantidad}")
						mensaje_lote = f'creado (ID: {lote_destino.id})'
					
					# 6. Crear ProductosMovimiento de ENTRADA
					prod_mov_entrada = ProductosMovimiento.objects.create(
						movimiento=movimiento_entrada,
						producto=lote_origen.producto,
						lote=lote_destino,
						cantidad=cantidad,
						costo_unitario=lote_origen.costo_unitario
					)
					print(f"DEBUG: ProductosMovimiento ENTRADA creado ID: {prod_mov_entrada.id}")
					print(f"DEBUG: ¡TRANSACCIÓN COMPLETADA EXITOSAMENTE!")
					
					# Mensaje de éxito
					ubicacion_info = f', Ubicación: {ubicacion_destino.nombre}' if ubicacion_destino else ''
					self.message_user(
						request,
						f'✅ Movimiento exitoso: {cantidad:,.2f} unidades de "{lote_origen.producto.nombre}" '
						f'movidas desde {lote_origen.almacen.nombre} hacia {almacen_destino.nombre}{ubicacion_info}. '
						f'Lote destino {mensaje_lote}. '
						f'Cantidad restante en origen: {lote_origen.cantidad:,.2f}',
						level='success'
					)
					
			except Exception as e:
				print(f"DEBUG: EXCEPCIÓN CAPTURADA: {type(e).__name__}: {str(e)}")
				import traceback
				print(f"DEBUG: Traceback completo:\n{traceback.format_exc()}")
				self.message_user(
					request,
					f'❌ Error al realizar el movimiento: {str(e)}',
					level='error'
				)
		else:
			print(f"DEBUG: Formulario NO válido, mostrando errores al usuario")
			self.message_user(
				request,
				'❌ Formulario inválido. Verifique los datos ingresados.',
				level='error'
			)
	
	mover_producto_entre_almacenes.short_description = '🚚 Mover producto entre almacenes FIJOS'
	
	# ============================================================
	#                  OPTIMIZACIÓN DE QUERYSET
	# ============================================================
	
	def get_queryset(self, request):
		"""Optimizar consultas con select_related y prefetch_related"""
		qs = super().get_queryset(request)
		return qs.select_related(
			'producto',
			'producto__categoria',
			'producto__unidad_sat',
			'almacen',
			'ubicacion',
			'ubicacion__zona',
			'ubicacion__zona__piso'
		)
	
	def formfield_for_foreignkey(self, db_field, request, **kwargs):
		"""Filtrar campos ForeignKey en el formulario"""
		if db_field.name == "almacen":
			# Solo mostrar almacenes tipo FIJO
			kwargs["queryset"] = Almacen.objects.filter(
				#tipo=Almacen.TIPO_FIJO,
				status_model='ACTIVE'
			)
		return super().formfield_for_foreignkey(db_field, request, **kwargs)


class ProductosMovimientoInline(admin.TabularInline):
	"""Inline para mostrar productos dentro de un movimiento"""
	model = ProductosMovimiento
	extra = 0
	fields = ('producto', 'lote', 'cantidad', 'costo_unitario', 'costo_total')
	readonly_fields = ('costo_total',)
	can_delete = True


# ================================================================
#           ADMINISTRADOR DE MOVIMIENTOS DE INVENTARIO
# ================================================================

@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
	"""
	Administrador mejorado para MovimientoInventario
	"""
	list_display = (
		'referencia_display', 'tipo_display', 'movimiento_display',
		'almacen_display', 'almacen_destino_display', 
		'productos_count', 'cantidad_total_display', 'fase_display',
		'created_at', 'status_model'
	)
	list_filter = (
		'tipo', 'movimiento', 'fase', 'alert_cantidad', 
		'tipo_alerta', 'almacen', 'almacen_destino', 
		'created_at', 'status_model'
	)
	search_fields = (
		'referencia', 'almacen__nombre', 'almacen_destino__nombre', 
		'nota', 'productosMovimiento__producto__nombre'
	)
	readonly_fields = (
		'referencia_display', 'productos_count', 'cantidad_total_display',
		'costo_total_display', 'created_at', 'updated_at', 
		'created_by', 'updated_by'
	)
	ordering = ('-created_at',)
	
	fieldsets = (
		('Información Básica', {
			'fields': ('referencia_display', 'tipo', 'movimiento', 'fase'),
			'description': 'Información general del movimiento'
		}),
		('Almacenes', {
			'fields': ('almacen', 'almacen_destino'),
			'description': 'Almacén origen y destino (si aplica)'
		}),
		('Alertas', {
			'fields': ('alert_cantidad', 'tipo_alerta'),
			'description': 'Alertas de cantidad',
			'classes': ('collapse',)
		}),
		('Resumen', {
			'fields': (
				'productos_count', 'cantidad_total_display', 
				'costo_total_display'
			),
			'description': 'Totales calculados',
			'classes': ('collapse',)
		}),
		('Notas', {
			'fields': ('nota',),
			'description': 'Información adicional'
		}),
		('Auditoría', {
			'fields': (
				'created_at', 'updated_at', 'created_by', 
				'updated_by', 'status_model'
			),
			'classes': ('collapse',)
		})
	)
	
	inlines = [ProductosMovimientoInline]
	
	# Acciones personalizadas
	actions = ['marcar_como_terminado', 'generar_reporte']
	
	def referencia_display(self, obj):
		"""Mostrar referencia con ícono según tipo"""
		iconos = {
			MovimientoInventario.TIPO_ENTRADA: "📥",
			MovimientoInventario.TIPO_SALIDA: "📤",
			MovimientoInventario.TIPO_AJUSTE: "⚙️",
		}
		icono = iconos.get(obj.tipo, "📦")
		return f"{icono} {obj.referencia or 'Sin referencia'}"
	referencia_display.short_description = 'Referencia'
	referencia_display.admin_order_field = 'referencia'
	
	def tipo_display(self, obj):
		"""Mostrar tipo con color"""
		colores = {
			MovimientoInventario.TIPO_ENTRADA: "🟢",
			MovimientoInventario.TIPO_SALIDA: "🔴",
			MovimientoInventario.TIPO_AJUSTE: "🟡",
		}
		icono = colores.get(obj.tipo, "⚪")
		return f"{icono} {obj.tipo}"
	tipo_display.short_description = 'Tipo'
	tipo_display.admin_order_field = 'tipo'
	
	def movimiento_display(self, obj):
		"""Mostrar movimiento con formato"""
		return obj.movimiento.replace('_', ' ').title()
	movimiento_display.short_description = 'Movimiento'
	movimiento_display.admin_order_field = 'movimiento'
	
	def almacen_display(self, obj):
		"""Mostrar almacén origen"""
		if obj.almacen:
			return f"📍 {obj.almacen.nombre}"
		return "N/A"
	almacen_display.short_description = 'Almacén Origen'
	almacen_display.admin_order_field = 'almacen__nombre'
	
	def almacen_destino_display(self, obj):
		"""Mostrar almacén destino"""
		if obj.almacen_destino:
			return f"🎯 {obj.almacen_destino.nombre}"
		return "-"
	almacen_destino_display.short_description = 'Almacén Destino'
	almacen_destino_display.admin_order_field = 'almacen_destino__nombre'
	
	def fase_display(self, obj):
		"""Mostrar fase con color"""
		if obj.fase == MovimientoInventario.FASE_TERMINADA:
			return "✅ TERMINADO"
		return "⏳ EN PROCESO"
	fase_display.short_description = 'Fase'
	fase_display.admin_order_field = 'fase'
	
	def productos_count(self, obj):
		"""Contar productos en el movimiento"""
		count = obj.productosMovimiento.count()
		return f"📦 {count} producto(s)"
	productos_count.short_description = 'Productos'
	
	def cantidad_total_display(self, obj):
		"""Calcular cantidad total del movimiento"""
		total = obj.productosMovimiento.aggregate(
			Sum('cantidad')
		)['cantidad__sum'] or 0
		return f"{total:,.2f}"
	cantidad_total_display.short_description = 'Cantidad Total'
	
	def costo_total_display(self, obj):
		"""Calcular costo total del movimiento"""
		total = obj.productosMovimiento.aggregate(
			Sum('costo_total')
		)['costo_total__sum'] or 0
		return f"💰 ${total:,.2f}"
	costo_total_display.short_description = 'Costo Total'
	
	def marcar_como_terminado(self, request, queryset):
		"""Acción para marcar movimientos como terminados"""
		updated = queryset.filter(
			fase=MovimientoInventario.FASE_PROCESO
		).update(fase=MovimientoInventario.FASE_TERMINADA)
		
		self.message_user(
			request, 
			f"{updated} movimiento(s) marcado(s) como terminado(s).",
			level='success' if updated > 0 else 'warning'
		)
	marcar_como_terminado.short_description = "Marcar como terminados"
	
	def generar_reporte(self, request, queryset):
		"""Acción placeholder para generar reporte"""
		self.message_user(
			request, 
			f"Función de reporte en desarrollo. {queryset.count()} movimiento(s) seleccionado(s).",
			level='info'
		)
	generar_reporte.short_description = "Generar reporte de movimientos"
	
	def get_readonly_fields(self, request, obj=None):
		"""Campos readonly según el estado"""
		readonly = list(self.readonly_fields)
		
		# Si está terminado, hacer campos principales readonly
		if obj and obj.fase == MovimientoInventario.FASE_TERMINADA:
			readonly.extend(['tipo', 'movimiento', 'almacen', 'almacen_destino'])
		
		return readonly


@admin.register(ProductosMovimiento)
class ProductosMovimientoAdmin(admin.ModelAdmin):
	"""
	Administrador para productos en movimientos de inventario
	"""
	list_display = (
		'id_display', 'movimiento_ref', 'producto', 'lote_display',
		'cantidad_display', 'costo_unitario_display', 'costo_total_display',
		'created_at'
	)
	list_filter = (
		'producto', 'movimiento__tipo', 'movimiento__movimiento',
		'movimiento__almacen', 'movimiento__fase', 'created_at'
	)
	search_fields = (
		'producto__nombre', 'producto__codigo',
		'movimiento__referencia', 'lote__id'
	)
	readonly_fields = (
		'costo_total_display', 'created_at', 'updated_at',
		'created_by', 'updated_by'
	)
	ordering = ('-created_at',)
	
	fieldsets = (
		('Información del Producto', {
			'fields': ('movimiento', 'producto', 'lote'),
			'description': 'Producto y lote asociado al movimiento'
		}),
		('Cantidades y Costos', {
			'fields': ('cantidad', 'costo_unitario', 'costo_total_display'),
			'description': 'Información de cantidades y costos'
		}),
		('Auditoría', {
			'fields': ('created_at', 'updated_at', 'created_by', 'updated_by', 'status_model'),
			'classes': ('collapse',)
		})
	)
	
	def id_display(self, obj):
		"""Mostrar ID con formato"""
		tipo_icono = {
			MovimientoInventario.TIPO_ENTRADA: "📥",
			MovimientoInventario.TIPO_SALIDA: "📤",
			MovimientoInventario.TIPO_AJUSTE: "⚙️",
		}
		icono = tipo_icono.get(obj.movimiento.tipo, "📦") if obj.movimiento else "📦"
		return f"{icono} PM-{obj.pk:08d}"
	id_display.short_description = 'ID'
	id_display.admin_order_field = 'id'
	
	def movimiento_ref(self, obj):
		"""Mostrar referencia del movimiento"""
		if obj.movimiento:
			return obj.movimiento.referencia or f"MOV-{obj.movimiento.pk}"
		return "N/A"
	movimiento_ref.short_description = 'Movimiento'
	movimiento_ref.admin_order_field = 'movimiento__referencia'
	
	def lote_display(self, obj):
		"""Mostrar información del lote"""
		if obj.lote:
			return f"🏷️ Lote-{obj.lote.pk}"
		return "-"
	lote_display.short_description = 'Lote'
	
	def cantidad_display(self, obj):
		"""Mostrar cantidad formateada"""
		return f"{obj.cantidad:,.2f}"
	cantidad_display.short_description = 'Cantidad'
	cantidad_display.admin_order_field = 'cantidad'
	
	def costo_unitario_display(self, obj):
		"""Mostrar costo unitario formateado"""
		return f"${obj.costo_unitario:,.2f}"
	costo_unitario_display.short_description = 'Costo Unit.'
	costo_unitario_display.admin_order_field = 'costo_unitario'
	
	def costo_total_display(self, obj):
		"""Mostrar costo total formateado"""
		return f"💰 ${obj.costo_total:,.2f}"
	costo_total_display.short_description = 'Costo Total'
	costo_total_display.admin_order_field = 'costo_total'
	
	def save_model(self, request, obj, form, change):
		"""Calcular costo total automáticamente"""
		if obj.cantidad and obj.costo_unitario:
			obj.costo_total = obj.cantidad * obj.costo_unitario
		super().save_model(request, obj, form, change)
	
	def has_delete_permission(self, request, obj=None):
		"""Solo permitir eliminar si el movimiento está en proceso"""
		if obj and obj.movimiento:
			return obj.movimiento.fase == MovimientoInventario.FASE_PROCESO
		return True

#@admin.register(Transformacion)
#class TransformacionAdmin(admin.ModelAdmin):
#	list_display = ("id", "producto_final", "cantidad_final", "almacen", "costo_unitario_final", "costo_total_final", "referencia")
#	list_filter = ("almacen", "producto_final")
#	search_fields = ("producto_final__nombre", "almacen__nombre", "referencia")




# ================================================================
#           ADMINISTRADOR DE SOLICITUDES DE PRODUCTOS
# ================================================================

@admin.register(ProductosSolicitud)
class ProductosSolicitudAdmin(admin.ModelAdmin):
	"""
	Administrador para solicitudes de productos
	"""
	list_display = (
		'id_display', 'producto', 'almacen', 'cantidad_display',
		'motivo_display', 'fase_display', 'created_at', 'status_model'
	)
	list_filter = (
		'fase', 'motivo', 'almacen', 'producto', 'created_at', 'status_model'
	)
	search_fields = (
		'producto__nombre', 'producto__codigo', 
		'almacen__nombre', 'created_by__username'
	)
	readonly_fields = (
		'created_at', 'updated_at', 'created_by', 'updated_by'
	)
	ordering = ('-created_at',)
	
	fieldsets = (
		('Información del Producto', {
			'fields': ('producto', 'almacen', 'cantidad'),
			'description': 'Producto y almacén solicitado'
		}),
		('Estado de la Solicitud', {
			'fields': ('motivo', 'fase'),
			'description': 'Motivo y estado actual'
		}),
		('Auditoría', {
			'fields': ('created_at', 'updated_at', 'created_by', 'updated_by', 'status_model'),
			'classes': ('collapse',)
		})
	)
	
	# Acciones personalizadas
	actions = ['marcar_como_atendido', 'marcar_como_cancelado']
	
	def id_display(self, obj):
		"""Mostrar ID con formato"""
		iconos = {
			ProductosSolicitud.SOLICITUD: "📝",
			ProductosSolicitud.ATENDIDO: "✅",
			ProductosSolicitud.CANCELADO: "❌",
		}
		icono = iconos.get(obj.fase, "📋")
		return f"{icono} SOL-{obj.pk:08d}"
	id_display.short_description = 'ID Solicitud'
	id_display.admin_order_field = 'id'
	
	def cantidad_display(self, obj):
		"""Mostrar cantidad formateada"""
		return f"{obj.cantidad:,.2f}"
	cantidad_display.short_description = 'Cantidad'
	cantidad_display.admin_order_field = 'cantidad'
	
	def motivo_display(self, obj):
		"""Mostrar motivo con ícono"""
		iconos = {
			ProductosSolicitud.MOTIVO_BAJA: "📉",
			ProductosSolicitud.MOTIVO_PREVENTA: "🛒",
		}
		icono = iconos.get(obj.motivo, "ℹ️")
		return f"{icono} {obj.motivo}"
	motivo_display.short_description = 'Motivo'
	motivo_display.admin_order_field = 'motivo'
	
	def fase_display(self, obj):
		"""Mostrar fase con color"""
		colores = {
			ProductosSolicitud.SOLICITUD: "🟡",
			ProductosSolicitud.ATENDIDO: "🟢",
			ProductosSolicitud.CANCELADO: "🔴",
		}
		icono = colores.get(obj.fase, "⚪")
		return f"{icono} {obj.fase}"
	fase_display.short_description = 'Estado'
	fase_display.admin_order_field = 'fase'
	
	def marcar_como_atendido(self, request, queryset):
		"""Acción para marcar solicitudes como atendidas"""
		updated = queryset.filter(
			fase=ProductosSolicitud.SOLICITUD
		).update(fase=ProductosSolicitud.ATENDIDO)
		
		self.message_user(
			request, 
			f"{updated} solicitud(es) marcada(s) como atendida(s).",
			level='success' if updated > 0 else 'warning'
		)
	marcar_como_atendido.short_description = "Marcar como atendidas"
	
	def marcar_como_cancelado(self, request, queryset):
		"""Acción para cancelar solicitudes"""
		updated = queryset.filter(
			fase=ProductosSolicitud.SOLICITUD
		).update(fase=ProductosSolicitud.CANCELADO)
		
		self.message_user(
			request, 
			f"{updated} solicitud(es) cancelada(s).",
			level='success' if updated > 0 else 'warning'
		)
	marcar_como_cancelado.short_description = "Cancelar solicitudes"
	
	def get_readonly_fields(self, request, obj=None):
		"""Campos readonly según el estado"""
		readonly = list(self.readonly_fields)
		
		# Si está atendido o cancelado, hacer campos readonly
		if obj and obj.fase in [ProductosSolicitud.ATENDIDO, ProductosSolicitud.CANCELADO]:
			readonly.extend(['producto', 'almacen', 'cantidad', 'motivo'])
		
		return readonly


# ================================================================
#           ADMINISTRADOR DE EMBARQUES Y PRODUCTOS
# ================================================================
