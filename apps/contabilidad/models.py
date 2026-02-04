from django.db import models
from apps.base.models import BaseModel


class CondicionPago(models.Model):
    CONDICION_CONTADO = 'CONTADO'
    CONDICION_CREDITO = 'CRÉDITO'
    CONDICION_MIXTA = 'MIXTA'
    
    CONDICIONES_LIST = [
        (CONDICION_CONTADO, CONDICION_CONTADO),
        (CONDICION_CREDITO, CONDICION_CREDITO),
        (CONDICION_MIXTA, CONDICION_MIXTA),
    ]
    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    #dias = models.PositiveIntegerField(default=0, verbose_name="Días")
    #activo = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        verbose_name = "Condición de Pago"
        verbose_name_plural = "Condiciones de Pago"
       
    def __str__(self):
        return self.nombre
    
    def save(self, *args, **kwargs):
        self.nombre = self.nombre.upper().strip()
        super().save(*args, **kwargs) 

class MetodoPago(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    tipo = models.CharField(max_length=50, verbose_name="Tipo")
    is_credito = models.BooleanField(default=False, verbose_name="Es Crédito")
    activo = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        verbose_name = "Método de Pago"
        verbose_name_plural = "Métodos de Pago"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre
    

    def save(self, *args, **kwargs):
        self.nombre = self.nombre.upper().strip()
        self.tipo = self.tipo.upper().strip()
        super().save(*args, **kwargs)





class UnidadSat(BaseModel):
    clave = models.CharField(max_length=10, unique=True, verbose_name="Clave")
    nombre = models.CharField(max_length=100, verbose_name="Nombre")

    class Meta:
        verbose_name = "Unidad SAT"
        verbose_name_plural = "Unidades SAT"
        ordering = ["clave"]

    def __str__(self):
        return f"({self.clave}) {self.nombre} "
    
    @property
    def name(self):
        return f"{self.clave} - {self.nombre}"
    
    def save(self, *args, **kwargs):
        self.clave = self.clave.upper().strip()
        self.nombre = self.nombre.upper().strip()
        super().save(*args, **kwargs)


class RegimenFiscal(BaseModel):
    class Meta:
        verbose_name = "Régimen Fiscal"
        verbose_name_plural = "Regímenes Fiscales"
        ordering = ["codigo"]
        
    codigo = models.CharField(max_length=20, verbose_name="Código", unique=True)
    nombre = models.CharField(max_length=200, verbose_name="Nombre")

    @property
    def full_name(self):
        return f"{self.codigo} - {self.nombre}"

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

    def save(self, *args, **kwargs):
        self.nombre = (self.nombre or "").upper().strip()
        super().save(*args, **kwargs)