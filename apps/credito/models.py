from django.utils import timezone
from datetime import timedelta

from django.db import models
from apps.base.models import BaseModel

from apps.usuarios.models import Usuario
from apps.erp.models import Cliente
from apps.contabilidad.models import MetodoPago

import uuid

    
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
        return float(self.monto) - float(self.monto_pagado)
    
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
        if self.adeudo_actual() == 0:
           self.marcar_pagado()
        return self
        
    def actualizar_saldo_cliente_dispersion(self):
        self.cliente.total_credito = float(self.cliente.total_credito) - float(self.monto)
        self.cliente.save(update_fields=["total_credito"])
        
    def actualizar_saldo_cliente_pago(self, monto):
        self.cliente.total_credito = float(self.cliente.total_credito) + float(monto)
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
        return float(self.monto) - float(self.monto_pagado)
    
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
        if self.adeudo_actual() == 0:
           self.marcar_pagado()
        return self
    
    def marcar_pagado(self):
        self.estado = self.PAGADA
        self.is_pagado = True
        self.fecha_pago = timezone.now().date()
        self.save(update_fields=["is_pagado", "fecha_pago"])
    
    
    def actualizar_saldo_proveedor_pago(self, monto):
        self.proveedor.total_credito = float(self.proveedor.total_credito) - float(monto)
        self.proveedor.save(update_fields=["total_credito"])
        
    def actualizar_saldo_proveedor_dispersion(self):
        self.proveedor.total_credito = float(self.proveedor.total_credito) + float(self.monto)
        self.proveedor.save(update_fields=["total_credito"])
        
    def save(self, *args, **kwargs):
        if self.pk is None:
            self.dias_plazo = self.proveedor.plazo_credito
            self.fecha_vencimiento = self.fecha + timedelta(days=self.dias_plazo)
            self.actualizar_saldo_proveedor_pago(self.monto)
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
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    
    def save(self, *args, **kwargs):
        if not self.token:
            self.token = uuid.uuid4()
        super().save(*args, **kwargs)