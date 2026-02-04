from django.utils import timezone

from django.db import models
from apps.base.models import BaseModel
from apps.usuarios.models import Usuario

from apps.erp.models import Producto, Almacen, Rutas
from django.db import models, transaction
from django.core.exceptions import ValidationError


"""
==============================================================================
            MODELO PARA EL CONTROL DE ALMACEN CEDIS
==============================================================================
"""
class Piso(BaseModel):
    nombre = models.CharField(max_length=50)
    descripcion = models.TextField(blank=True, null=True)
    almacen = models.ForeignKey(Almacen, on_delete=models.CASCADE, related_name='pisos_almacen', null=False, blank=False)

    def clean(self):
        if not self.almacen.is_cedis:
            from django.core.exceptions import ValidationError
            raise ValidationError("Solo se pueden crear pisos para almacenes tipo CEDIS.")
    
    def __str__(self):
        return self.nombre


##ZONA
class Zona(BaseModel):
    piso = models.ForeignKey(Piso, on_delete=models.CASCADE, related_name='zonas')
    nombre = models.CharField(max_length=50)
    descripcion = models.TextField(blank=True, null=True)
    
    
    def tiene_racks_con_lotes(self):
        """
        Verifica si la zona tiene racks con lotes de inventario asignados
        """
        #qs = Rack.objects.filter(
        #    zona=self,
        #    status_model=BaseModel.STATUS_MODEL_ACTIVE,
        #    loteinventario__status_model=LoteInventario.STATUS_MODEL_ACTIVE,
        #    loteinventario__cantidad__gt=0
        #).only('id')
        #print(qs.query)
        
        return Rack.objects.filter(
            zona=self,
            status_model=BaseModel.STATUS_MODEL_ACTIVE,
            loteinventario__status_model=LoteInventario.STATUS_MODEL_ACTIVE,
            loteinventario__cantidad__gt=0
        ).only('id').exists()

    def __str__(self):
        return f"{self.piso.nombre} - {self.nombre}"

#TARA
class Rack(BaseModel):
    zona = models.ForeignKey(Zona, on_delete=models.CASCADE, related_name='racks')
    nombre = models.CharField(max_length=50)
    descripcion = models.TextField(blank=True, null=True)
    
    
    def tiene_lotes_asignados(self):
        """
        Verifica si el rack tiene lotes de inventario asignados
        """
        return LoteInventario.objects.filter(
            ubicacion=self,
            status_model=LoteInventario.STATUS_MODEL_ACTIVE,
            cantidad__gt=0
        ).only('id').exists()

    def __str__(self):
        return f"{self.zona} - Rack {self.nombre}"




"""
==============================================================================
            MODELO PARA EL CONTROL DE INVENTARIO POR LOTE
==============================================================================
"""
class LoteInventario(BaseModel):
    #folio = models.CharField(max_length=200, unique=True, help_text="Folio único del lote")
    referencia = models.CharField(max_length=250, null=True, blank=True)
    lote_herencia = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, help_text="Lote del cual se deriva este lote (en caso de transformaciones)")
    producto = models.ForeignKey(Producto, on_delete=models.SET_NULL, null=True, blank=True)
    almacen  = models.ForeignKey(Almacen, on_delete=models.SET_NULL, null=True, blank=True)
    ubicacion = models.ForeignKey(Rack, on_delete=models.SET_NULL, null=True, blank=True, help_text="Solo para almacenes CEDIS")
    cantidad = models.DecimalField(max_digits=25, decimal_places=2, default=0,)
    costo_unitario = models.DecimalField(max_digits=25, decimal_places=2, default=0)
    fecha_ingreso = models.DateTimeField(auto_now_add=True)
    fecha_vencimiento = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['almacen', 'status_model', 'cantidad']),
            models.Index(fields=['producto', 'almacen', 'status_model']),
            models.Index(fields=['status_model', 'cantidad']),
            models.Index(fields=['ubicacion', 'status_model', 'cantidad']),
            models.Index(fields=['producto', 'ubicacion', 'status_model']),
        ]
        verbose_name = "Lote de Inventario"
        verbose_name_plural = "Lotes de Inventario"
        ordering = ['fecha_ingreso']

    def __str__(self):
        return f"Lote {self.id} - {self.producto.nombre} ({self.cantidad})"

    #def ajustar_cantidad(self, cantidad, movimiento=None, user_id=None):
    #    if movimiento == MovimientoInventario.TIPO_SALIDA:
    #        self.cantidad -= cantidad
    #    elif movimiento == MovimientoInventario.TIPO_ENTRADA:
    #        self.cantidad += cantidad
    #    self.save()

    def save(self, *args, **kwargs):
       # Aquí puedes agregar lógica adicional antes de guardar el lote
        if self.cantidad <= 0:
            self.status_model = self.STATUS_MODEL_INACTIVE
            
        if self.cantidad > 0 and self.status_model != self.STATUS_MODEL_ACTIVE:
            self.status_model = self.STATUS_MODEL_ACTIVE
        # Por ejemplo, podrías validar o modificar campos antes de guardar
        if not self.fecha_vencimiento :
            self.fecha_vencimiento = (self.created_at or timezone.now()) + timezone.timedelta(days=self.producto.dias_caducidad)
        
        super().save(*args, **kwargs)
       
    





"""
==============================================================================
          MODELO PARA EL CONTROL DE MOVIMIENTOS DE INVENTARIO
==============================================================================
"""

class MovimientoInventario(BaseModel):
    TIPO_ENTRADA = "ENTRADA"
    TIPO_SALIDA = "SALIDA"
    TIPO_AJUSTE = "AJUSTE"

    ENTRADA_ABASTECIMIENTO = "ENTRADA ABASTECIMIENTO"
    ENTRADA_TRASPASO = "ENTRADA TRASPASO"
    ENTRADA_TRASPASO_VIRTUAL = "ENTRADA TRASPASO VIRTUAL"
    ENTRADA_EMBARQUE = "ENTRADA EMBARQUE"
    ENTRADA_VENTA = "ENTRADA VENTA CANCELADA"
    ENTRADA_TRANSFORMACION = "ENTRADA TRANSFORMACION"

    SALIDA_VENTA = "SALIDA VENTA"
    SALIDA_TRASPASO = "SALIDA TRASPASO"
    SALIDA_TRASPASO_VIRTUAL = "SALIDA TRASPASO VIRTUAL"
    SALIDA_MERMA = "SALIDA MERMA"
    SALIDA_TRANSFORMACION = "SALIDA TRANSFORMACION"
    SALIDA_EMBARQUE = "SALIDA EMBARQUE"

    TIPO_MOVIMIENTO = [
        (TIPO_SALIDA, TIPO_SALIDA),
        (TIPO_ENTRADA, TIPO_ENTRADA),
        (TIPO_AJUSTE, TIPO_AJUSTE),
    ]

    ENTRADAS_CHOICES = [
        (ENTRADA_ABASTECIMIENTO, ENTRADA_ABASTECIMIENTO),
        (ENTRADA_TRASPASO, ENTRADA_TRASPASO),
        (ENTRADA_TRASPASO_VIRTUAL, ENTRADA_TRASPASO_VIRTUAL),
        (ENTRADA_EMBARQUE, ENTRADA_EMBARQUE),
        (ENTRADA_VENTA, ENTRADA_VENTA),
        (ENTRADA_TRANSFORMACION, ENTRADA_TRANSFORMACION),
    ]
    SALIDAS_CHOICES = [
        (SALIDA_VENTA,  SALIDA_VENTA),
        (SALIDA_TRASPASO, SALIDA_TRASPASO),
        (SALIDA_MERMA, SALIDA_MERMA),
        (SALIDA_TRANSFORMACION, SALIDA_TRANSFORMACION),
        (SALIDA_TRASPASO_VIRTUAL, SALIDA_TRASPASO_VIRTUAL),
        (SALIDA_EMBARQUE, SALIDA_EMBARQUE),
    ]

    AJUSTE_MANUAL = "AJUSTE MANUAL"
    AJUSTE_CHOICES = [
        (AJUSTE_MANUAL, AJUSTE_MANUAL),
    ]

    FASE_PROCESO = 'FASE PROCESO'
    FASE_TERMINADA = 'FASE TERMINADA'

    FASES = [
        (FASE_PROCESO,FASE_PROCESO),
        (FASE_TERMINADA,FASE_TERMINADA),
    ]

    ALERTA_MAS = "MAS"
    ALERTA_MENOS = "MENOS"

    TIPO_ALERTA = [
        (ALERTA_MAS, ALERTA_MAS),
        (ALERTA_MENOS, ALERTA_MENOS),
    ]

    #producto = models.ForeignKey(Producto, on_delete=models.SET_NULL, null=True, blank=True)
    almacen = models.ForeignKey(Almacen, on_delete=models.SET_NULL, null=True, blank=True, help_text="Almacén donde se realiza el movimiento")
    almacen_destino = models.ForeignKey(Almacen, on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos_destino', help_text="Almacén de destino para el movimiento")
    tipo = models.CharField(max_length=20, choices=TIPO_MOVIMIENTO, default=TIPO_ENTRADA)
    movimiento = models.CharField(max_length=30, choices=ENTRADAS_CHOICES + SALIDAS_CHOICES + AJUSTE_CHOICES)
    cantidad = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    costo_unitario = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    #lote = models.ForeignKey(LoteInventario, on_delete=models.SET_NULL, null=True, blank=True)
    referencia = models.CharField(max_length=150, null=True, blank=True)
    detalle_nota = models.CharField(max_length=255, null=True, blank=True)
    nota = models.TextField(null=True, blank=True)
    fase = models.CharField(max_length=20, choices=FASES, default=FASE_PROCESO)
    alert_cantidad = models.BooleanField(default=False, help_text="Indica si la cantidad es menor a la que salió del traspaso")
    tipo_alerta = models.CharField(max_length=10, choices=TIPO_ALERTA, null=True, blank=True, help_text="Tipo de alerta para el movimiento")
    
    @property
    def folio(self):
        """
        Retorna el folio único del movimiento
        """
        return f"{self.pk:010d}" if self.pk else ""
    
    def generar_folio(self):
        """
        Genera un folio único según el tipo y movimiento.
        Ejemplo: ENTRADA-ABASTECIMIENTO-202508-00123 o SALIDA-VENTA-202508-00123
        """
        fecha = timezone.now()
        tipo = self.tipo if self.tipo else "MOV"
        movimiento = self.movimiento if self.movimiento else "GEN"
        almacen = self.almacen.nombre if self.almacen else "ALM-GENRICO"
        pk = self.pk if self.pk else ""
        folio = f"{almacen}-{movimiento}-{fecha.year}-{fecha.month:02d}-{fecha.day:02d}-{pk}"
        folio = folio.replace(' ', '-').replace('_', '-')
        return folio

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.referencia:
            self.referencia = self.generar_folio()
            super().save(update_fields=['referencia'])

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.movimiento} ({self.cantidad})"




class ProductosMovimiento(BaseModel):
    """
    Modelo para los productos en un movimiento de inventario
    """
    movimiento = models.ForeignKey(MovimientoInventario, on_delete=models.CASCADE, related_name='productosMovimiento')
    producto = models.ForeignKey(Producto, on_delete=models.SET_NULL, null=True, blank=True)
    lote = models.ForeignKey(LoteInventario, on_delete=models.SET_NULL, null=True, blank=True)
    cantidad = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    costo_unitario = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    costo_total = models.DecimalField(max_digits=20, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Producto en Movimiento"
        verbose_name_plural = "Productos en Movimientos"

    def save(self, *args, **kwargs):
        with transaction.atomic():

            if self.cantidad and self.costo_unitario:
                self.costo_total = self.cantidad * self.costo_unitario

            is_new = self._state.adding  # 👈 CLAVE

            super().save(*args, **kwargs)

            if not self.lote:
                return

            # 🔥 AFECTAR INVENTARIO SOLO SI ES NUEVO
            if is_new:
                if self.movimiento.tipo == MovimientoInventario.TIPO_SALIDA:
                    if self.lote.cantidad < self.cantidad:
                        raise ValidationError("No hay suficiente inventario en el lote")
                    self.lote.cantidad -= self.cantidad

                elif self.movimiento.tipo == MovimientoInventario.TIPO_ENTRADA:
                    self.lote.cantidad += self.cantidad

                self.lote.save()


    def __str__(self):
        return f"{self.movimiento.referencia} - {self.producto.nombre} ({self.cantidad})"






class EmbarqueReparto(BaseModel):
    FASE_CARGA = 'CARGA'
    FASE_REPARTO = 'REPARTO'
    FASE_TERMINADO = 'TERMINADO'
    FASE_CANCELADO = 'CANCELADO'
    FASES = [
        (FASE_CARGA, FASE_CARGA),
        (FASE_REPARTO, FASE_REPARTO),
        (FASE_TERMINADO, FASE_TERMINADO),
        (FASE_CANCELADO, FASE_CANCELADO),
    ]
    ruta = models.ForeignKey(Rutas, on_delete=models.CASCADE, related_name='embarques')
    encargado = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='embarques_usuario')
    fase = models.CharField(max_length=20, choices=FASES, default=FASE_CARGA)
    ventas = models.ManyToManyField('erp.Venta', related_name='embarques_ruta')
    movimiento_inventario_pedidos_entrada = models.ForeignKey(MovimientoInventario, on_delete=models.SET_NULL, null=True, blank=True, related_name='embarques_reparto_entrada')
    movimiento_inventario_pedidos_salida = models.ForeignKey(MovimientoInventario, on_delete=models.SET_NULL, null=True, blank=True, related_name='embarques_reparto_salida')
    movimiento_inventario_tara_entrada = models.ForeignKey(MovimientoInventario, on_delete=models.SET_NULL, null=True, blank=True, related_name='embarques_reparto_tara_entrada')
    movimiento_inventario_tara_salida = models.ForeignKey(MovimientoInventario, on_delete=models.SET_NULL, null=True, blank=True, related_name='embarques_reparto_tara_salida')
    nota = models.TextField(null=True, blank=True)
    fecha_salida = models.DateTimeField(null=True, blank=True)
    fecha_finalizada = models.DateTimeField(null=True, blank=True)
    apertura_caja = models.ForeignKey('erp.CajaApertura', on_delete=models.SET_NULL, null=True, blank=True, related_name='caja_embarque_reparto')
    
    def add_fechas(self):
        if self.fase == self.FASE_REPARTO:
            self.fecha_salida = timezone.now()
        elif self.fase == self.FASE_TERMINADO:
            self.fecha_finalizada = timezone.now()
            
    #def save(self, *args, **kwargs):
    #    #self.add_fechas()
    #    super().save(*args, **kwargs)
class ProductoEmbarque(BaseModel):
    TARA = 'TARA'
    PEDIDO = 'PEDIDO'
    TIPO_PRODUCTO = [
        (TARA, TARA),
        (PEDIDO, PEDIDO),
    ]
    tipo = models.CharField(max_length=20, choices=TIPO_PRODUCTO, default=TARA)
    embarque = models.ForeignKey(EmbarqueReparto, on_delete=models.CASCADE, default=None, related_name='productos')
    preventa = models.ForeignKey('erp.Venta', on_delete=models.CASCADE, related_name='productos_embarque_venta', null=True, blank=True, default=None)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='lotes_embarque')
    cantidad = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    is_cargado = models.BooleanField(default=False)
    precio_unitario = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    cantidad_solicitada = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    cantidad_entregada = models.DecimalField(max_digits=20, decimal_places=2, default=0)
class LoteProductoEmbarque(BaseModel):
    is_interno = models.BooleanField(default=False)
    producto_embarque = models.ForeignKey(ProductoEmbarque, on_delete=models.CASCADE, related_name='lotes')
    lote = models.ForeignKey(LoteInventario, on_delete=models.CASCADE, related_name='lotes_embarque')
    cantidad = models.DecimalField(max_digits=20, decimal_places=2, default=0)   
 


class ProductosSolicitud(BaseModel):
    """
    Modelo para los productos que generan solicitud por baja existencia
    """
    SOLICITUD = 'SOLICITUD'
    #PROCESO = 'PROCESO'
    ATENDIDO = 'ATENDIDO'
    CANCELADO = 'CANCELADO'
    ESTADOS = [
        (SOLICITUD, SOLICITUD),
        #(PROCESO, PROCESO),
        (ATENDIDO, ATENDIDO),
        (CANCELADO, CANCELADO),
    ]
    
    MOTIVO_BAJA = 'BAJA EXISTENCIA'
    MOTIVO_PREVENTA = 'PREVENTA INCOMPLETA'
    MOTIVOS_SOLICITUD = [
        (MOTIVO_BAJA, MOTIVO_BAJA),
        (MOTIVO_PREVENTA, MOTIVO_PREVENTA),
    ]
    class Meta:
        verbose_name = "Producto en Solicitud"
        verbose_name_plural = "Productos en Solicitudes"
        ordering = ['-created_at']
    almacen = models.ForeignKey(Almacen, on_delete=models.CASCADE, null=True, blank=True, related_name='solicitud_almacen', default=None)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, null=True, blank=True, related_name='solicitud_producto' , default=None)
    cantidad = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    motivo = models.CharField(max_length=30, choices=MOTIVOS_SOLICITUD, default=MOTIVO_BAJA)
    fase = models.CharField(max_length=20, choices=ESTADOS, default=SOLICITUD)  



#==============================================================================
#                            SOLICITUD DE PRODUCTOS
#==============================================================================

class SolicitudTraspaso(BaseModel):
    """
    Registro principal de una solicitud de traspaso entre almacenes
    """
    APROBADO = 'APROBADO'
    RECHAZADO = 'RECHAZADO'
    PENDIENTE = 'PENDIENTE'
    ESTADOS_LIST = [
        (APROBADO, APROBADO),
        (RECHAZADO, RECHAZADO),
        (PENDIENTE, PENDIENTE),
    ]
    almacen_solicitante = models.ForeignKey(Almacen, on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitudes_almacen_solicitante')
    almacen_surtidor = models.ForeignKey(Almacen, on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitudes_almacen_surtidor')
    estado = models.CharField(max_length=20, choices=ESTADOS_LIST, default=PENDIENTE)
    nota = models.TextField(null=True, blank=True)
    referencia = models.CharField(max_length=150, null=True, blank=True)
    aprobado_el = models.DateTimeField(default=None, null=True, blank=True)
    aprobado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True,
                                        blank=True, related_name='solicitudes_traspaso_usuario_aprobado')
    rechazado_el = models.DateTimeField(default=None, null=True, blank=True)
    rechazado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True,
                                        blank=True, related_name='solicitudes_traspaso_usuario_rechazado')
    movimiento = models.ForeignKey(MovimientoInventario, on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitudes_traspaso_movimiento')

class SolicitudTraspasoDetalle(models.Model):
    solicitud = models.ForeignKey(SolicitudTraspaso, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.SET_NULL, null=True, blank=True)
    cantidad = models.DecimalField(max_digits=20, decimal_places=5, default=0)
    








"""
============================================================================================
                            MODELOS PARA EL CONTROL DE TRANSFORMACION
============================================================================================
"""
class Transformacion(BaseModel):
    """
    Registro principal de una transformación de insumos a producto final
    """
    TIPO_MERMA = 'MERMA'
    TIPO_TRANSFORMACION = 'TRANSFORMACION'
    TIPOS = [
        (TIPO_MERMA, TIPO_MERMA),
        (TIPO_TRANSFORMACION, TIPO_TRANSFORMACION),
    ]
    tipo = models.CharField(max_length=20, choices=TIPOS, default=TIPO_TRANSFORMACION)
    almacen = models.ForeignKey(Almacen, on_delete=models.SET_NULL, null=True, blank=True)
    referencia = models.CharField(max_length=150, null=True, blank=True)
    nota = models.TextField(null=True, blank=True)
    movimiento_salida = models.ForeignKey(MovimientoInventario, on_delete=models.SET_NULL, null=True, blank=True, related_name='transformaciones_salida',help_text="Movimiento de salida asociado a la transformación o merma productos a transformar")
    movimiento_entrada = models.ForeignKey(MovimientoInventario, on_delete=models.SET_NULL, null=True, blank=True, related_name='transformaciones_entrada' ,help_text="Movimiento de entrada asociado a la transformación productos resultantes")

    
    

    
    