from django.utils import timezone
from datetime import timedelta

from django.db import models
from apps.base.models import BaseModel

from apps.usuarios.models import Usuario
from apps.erp.models import Cliente
from apps.contabilidad.models import MetodoPago

import uuid
from decimal import Decimal

    
class CreditoCliente(BaseModel):
    VENCIDA = "VENCIDA"
    PENDIENTE = "PENDIENTE"
    ACTIVA = "ACTIVA"
    PAGADA = "PAGADA"
    ESTADOS = [
        #(VENCIDA, VENCIDA),
        #(PENDIENTE, PENDIENTE),
        (ACTIVA, ACTIVA),
        (PAGADA, PAGADA),
    ]
    estado = models.CharField(max_length=20, choices=ESTADOS, default=ACTIVA)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="creditos")
    fecha = models.DateField(default=timezone.now)
    monto = models.DecimalField(max_digits=12, decimal_places=2,default=0)
    monto_pagado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    dias_plazo = models.PositiveIntegerField(default=1, verbose_name="Plazo en días")
    is_pagado = models.BooleanField(default=False)
    fecha_pago = models.DateField(blank=True, null=True, verbose_name="Fecha de liquidación de la dispersión")
    observaciones = models.TextField(blank=True, null=True)
    referencia = models.CharField(max_length=100, blank=True, null=True)
    venta = models.ForeignKey('erp.Venta', on_delete=models.SET_NULL, blank=True, null=True, related_name="creditos")
    fecha_vencimiento = models.DateField(blank=True, null=True)

    class Meta:
        verbose_name = "Dispersión de crédito"
        verbose_name_plural = "Dispersión de créditos"

    def __str__(self):
        return f"{self.cliente.codigo} - Disp. ${self.monto}"


    @property
    def ha_vencido(self):
        return timezone.now().date() > self.fecha_vencimiento

    def save(self, *args, **kwargs):
        if self.pk is None:
            self.dias_plazo = self.cliente.plazos_semanas
            self.fecha_vencimiento = self.fecha + timedelta(days=self.dias_plazo)
            self.actualizar_saldo_cliente_dispersion()
        super().save(*args, **kwargs)
    
    def adeudo_actual(self):
        monto = Decimal(str(self.monto or 0))
        monto_pagado = Decimal(str(self.monto_pagado or 0))
        adeudo = monto - monto_pagado
        if adeudo < Decimal('0.00'):
            adeudo = Decimal('0.00')
        return adeudo.quantize(Decimal('0.01'))
    
    def abonar(self, monto, metodo_pago=None, usuario=None):
        self.monto_pagado += monto
        self.actualizar_saldo_cliente_pago(monto)
        PagosCredito.objects.create(
            credito=self,
            monto=monto,
            metodo_pago=metodo_pago,
            created_by=usuario
        )
        self.save()
        if self.adeudo_actual() <= Decimal('0.00'):
           self.marcar_pagado()
        return self
        
    def actualizar_saldo_cliente_dispersion(self):
        total_credito = Decimal(str(self.cliente.total_credito or 0))
        monto = Decimal(str(self.monto or 0))
        self.cliente.total_credito = (total_credito - monto).quantize(Decimal('0.01'))
        self.cliente.save(update_fields=["total_credito"])

    def actualizar_saldo_cliente_pago(self, monto):
        total_credito = Decimal(str(self.cliente.total_credito or 0))
        monto = Decimal(str(monto or 0))
        self.cliente.total_credito = (total_credito + monto).quantize(Decimal('0.01'))
        self.cliente.save(update_fields=["total_credito"])


    def marcar_pagado(self):
        self.is_pagado = True
        self.estado = self.PAGADA
        self.fecha_pago = timezone.now().date()
        self.save(update_fields=["is_pagado", "fecha_pago", "estado"])
        #self.credito.actualizar_credito_usado()
        
        
class PagosCredito(BaseModel):
    credito = models.ForeignKey(
        CreditoCliente,
        on_delete=models.CASCADE,
        related_name="pagos",
        blank=True,
        null=True
    )
    monto = models.DecimalField(max_digits=20, decimal_places=2)
    metodo_pago = models.ForeignKey(MetodoPago, on_delete=models.SET_NULL, null=True, blank=True)



class CreditoProveedor(BaseModel):
    VENCIDA = "VENCIDA"
    PENDIENTE = "PENDIENTE"
    ACTIVA = "ACTIVA"
    PAGADA = "PAGADA"
    ESTADOS = [
        #(VENCIDA, VENCIDA),
        #(PENDIENTE, PENDIENTE),
        (ACTIVA, ACTIVA),
        (PAGADA, PAGADA),
    ]
    estado = models.CharField(max_length=20, choices=ESTADOS, default=ACTIVA)
    proveedor = models.ForeignKey('erp.Proveedor', on_delete=models.CASCADE, related_name="creditos_proveedor")
    fecha = models.DateField(default=timezone.now)
    monto = models.DecimalField(max_digits=12, decimal_places=2,default=0)
    monto_pagado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    dias_plazo = models.PositiveIntegerField(default=1, verbose_name="Plazo en días")
    is_pagado = models.BooleanField(default=False)
    fecha_pago = models.DateField(blank=True, null=True, verbose_name="Fecha de liquidación del crédito")
    observaciones = models.TextField(blank=True, null=True)
    referencia = models.CharField(max_length=100, blank=True, null=True)
    compra = models.ForeignKey('erp.Compra', on_delete=models.SET_NULL, blank=True, null=True, related_name="creditos_proveedor")
    fecha_vencimiento = models.DateField(blank=True, null=True)
    class Meta:
        verbose_name = "Crédito de proveedor"
        verbose_name_plural = "Créditos de proveedores"
    @property
    def ha_vencido(self):
        return timezone.now().date() > self.fecha_vencimiento

    def adeudo_actual(self):
        monto = Decimal(str(self.monto or 0))
        monto_pagado = Decimal(str(self.monto_pagado or 0))
        adeudo = monto - monto_pagado
        if adeudo < Decimal('0.00'):
            adeudo = Decimal('0.00')
        return adeudo.quantize(Decimal('0.01'))
    
    def abonar(self, monto, metodo_pago=None, usuario=None):
        self.monto_pagado += monto
        self.actualizar_saldo_proveedor_pago(monto)
        PagosCreditoProveedor.objects.create(
            credito_proveedor=self,
            monto=monto,
            metodo_pago=metodo_pago,
            created_by=usuario
        )
        self.save()
        if self.adeudo_actual() <= Decimal('0.00'):
           self.marcar_pagado()
        return self
    
    def marcar_pagado(self):
        self.estado = self.PAGADA
        self.is_pagado = True
        self.fecha_pago = timezone.now().date()
        self.save(update_fields=["estado", "is_pagado", "fecha_pago"])
    
    
    def actualizar_saldo_proveedor_pago(self, monto):
        total_credito = Decimal(str(self.proveedor.total_credito or 0))
        monto = Decimal(str(monto or 0))
        self.proveedor.total_credito = (total_credito - monto).quantize(Decimal('0.01'))
        self.proveedor.save(update_fields=["total_credito"])

    def actualizar_saldo_proveedor_dispersion(self):
        total_credito = Decimal(str(self.proveedor.total_credito or 0))
        monto = Decimal(str(self.monto or 0))
        self.proveedor.total_credito = (total_credito + monto).quantize(Decimal('0.01'))
        self.proveedor.save(update_fields=["total_credito"])
        
    def save(self, *args, **kwargs):
        if self.pk is None:
            self.dias_plazo = self.proveedor.plazo_credito
            self.fecha_vencimiento = self.fecha + timedelta(days=self.dias_plazo)
            # Crear un crédito de proveedor incrementa el saldo de crédito disponible.
            self.actualizar_saldo_proveedor_dispersion()
        super().save(*args, **kwargs)
    
    
    def __str__(self):
        return f"{self.proveedor.codigo} - Crédito ${self.monto}"
    
class PagosCreditoProveedor(BaseModel):
    #from django.db import models
    #poner uuid
    credito_proveedor = models.ForeignKey(
        CreditoProveedor,
        on_delete=models.CASCADE,
        related_name="pagos_proveedor",
        blank=True,
        null=True
    )
    monto = models.DecimalField(max_digits=20, decimal_places=2)
    metodo_pago = models.ForeignKey(MetodoPago, on_delete=models.SET_NULL, null=True, blank=True)
    referencia = models.CharField(max_length=100, blank=True, null=True)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    
    def save(self, *args, **kwargs):
        if not self.token:
            self.token = uuid.uuid4()
        super().save(*args, **kwargs)


class OperacionPrelacionPago(BaseModel):
    """
    Registro de operaciones de prelación para garantizar idempotencia y auditoría.
    """
    TIPO_CLIENTE = "CLIENTE"
    TIPO_PROVEEDOR = "PROVEEDOR"
    TIPO_CHOICES = [
        (TIPO_CLIENTE, "Cliente"),
        (TIPO_PROVEEDOR, "Proveedor"),
    ]

    ESTADO_IN_PROGRESS = "IN_PROGRESS"
    ESTADO_COMPLETED = "COMPLETED"
    ESTADO_FAILED = "FAILED"
    ESTADO_CHOICES = [
        (ESTADO_IN_PROGRESS, "En proceso"),
        (ESTADO_COMPLETED, "Completada"),
        (ESTADO_FAILED, "Fallida"),
    ]

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, db_index=True)
    entidad_id = models.PositiveIntegerField(db_index=True)
    idempotency_key = models.CharField(max_length=128)
    request_hash = models.CharField(max_length=64)
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default=ESTADO_IN_PROGRESS,
        db_index=True,
    )
    response_payload = models.JSONField(blank=True, null=True)
    http_status = models.PositiveSmallIntegerField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Operación de prelación de pago"
        verbose_name_plural = "Operaciones de prelación de pago"
        constraints = [
            models.UniqueConstraint(
                fields=["tipo", "entidad_id", "idempotency_key"],
                name="credito_unique_prelacion_idempotency",
            )
        ]

    def __str__(self):
        return (
            f"{self.tipo} #{self.entidad_id} - key={self.idempotency_key} - "
            f"{self.estado}"
        )
