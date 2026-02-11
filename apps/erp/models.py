from django.db import models
from django.utils import timezone

from apps.base.models import BaseModel, BaseDireccion
from apps.usuarios.models import Usuario
from apps.contabilidad.models import CondicionPago,MetodoPago
from datetime import timedelta

class Empresa(BaseModel):
    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"
        ordering = ['id']

        permissions = [
            (  f"can_view_{verbose_name}".lower(),         f"Ver {verbose_name_plural}".upper()),
            (f"can_update_{verbose_name}".lower(),  f"Actualizar {verbose_name_plural}".upper()),
            (f"can_create_{verbose_name}".lower(),       f"Crear {verbose_name_plural}".upper()),
            (f"can_delete_{verbose_name}".lower(),    f"Eliminar {verbose_name_plural}".upper()),
        ]
    
    nombre = models.CharField(max_length=255, null=False, blank=False, verbose_name="Nombre o Razón Social")
    rfc = models.CharField(max_length=13, unique=True, null=False, blank=False, verbose_name="RFC")
    telefono = models.CharField(max_length=15, blank=True, null=True, verbose_name="Teléfono")
    email = models.EmailField(blank=True, null=True, verbose_name="Correo Electrónico")
    cuenta_clave = models.CharField(max_length=20, verbose_name="Cuenta Clave", blank=True, null=True)
    regimen_fiscal = models.ForeignKey('contabilidad.RegimenFiscal', on_delete=models.SET_NULL, blank=False, null=True,verbose_name="Régimen Fiscal")
    direccion_fiscal = models.TextField(verbose_name="Dirección Fiscal", blank=True, null=True, help_text="Dirección fiscal de la empresa")
    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"

    def __str__(self):
        return self.nombre
    
    def save(self, *args, **kwargs):
        self.nombre = (self.nombre or "").strip().upper()
        self.rfc = (self.rfc or "").strip().upper()
        super().save(*args, **kwargs)



"""
===============================================================
                Proveedor Model
===============================================================
"""

class Proveedor(BaseModel):
    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        ordering = ["nombre"]

    ORIGEN_MEX = "MÉXICO"
    ORIGEN_USA = "ESTADOS UNIDOS"
    ORIGEN_OTRO = "OTRO"
    ORIGEN_LIST = [
        (ORIGEN_MEX, "MÉXICO"),
        (ORIGEN_USA, "ESTADOS UNIDOS"),
        (ORIGEN_OTRO, "OTRO"),
    ]

    origen = models.CharField(max_length=20, choices=ORIGEN_LIST, verbose_name="Origen", default=ORIGEN_MEX, blank=True, null=True)
    codigo = models.CharField(max_length=20, verbose_name="Código", unique=True, blank=True, null=True)
    razon_social = models.CharField(max_length=180, blank=True, null=True, default=None, verbose_name="Razón Social")
    nombre = models.CharField(max_length=200, verbose_name="Nombre del Proveedor", blank=False, null=False)
    monto = models.DecimalField(max_digits=20, decimal_places=2, default=0.0, verbose_name="Monto de Crédito", blank=True, null=True)
    plazo_credito = models.PositiveIntegerField(default=0, verbose_name="Plazo de Crédito (días)", blank=True, null=True)
    total_credito = models.DecimalField(max_digits=20, decimal_places=2, default=0.0, verbose_name="Total de Crédito", blank=True, null=True)
    rfc = models.CharField(max_length=15, verbose_name="RFC", blank=True, null=True)
    telefono = models.CharField(max_length=20, verbose_name="Teléfono", blank=True, null=True)
    correo = models.EmailField(max_length=254, verbose_name="Correo Electrónico", blank=True, null=True)
    cuenta_clave = models.CharField(max_length=20, verbose_name="Cuenta Clave", blank=True, null=True)
    #regimen_fiscal = models.ForeignKey('contabilidad.RegimenFiscal', on_delete=models.SET_NULL, blank=False, null=False,verbose_name="Régimen Fiscal")


    @property
    def full_name(self):
        return f"{self.codigo} - {self.razon_social or self.nombre}".strip()

    def __str__(self):
        if self.razon_social != "":
            return f"{self.codigo} - {self.razon_social}"
        else:
            return f"{self.codigo} - {self.nombre}"

    def generar_folio(self):
        """
        Genera un folio único para el proveedor basado en el prefijo 'PROV' y el ID.
        Si el objeto aún no tiene ID (no está guardado), retorna None.
        """
        if self.pk:
            return f"PROV-{self.pk:05d}"
        return None

    def save(self, *args, **kwargs):
        self.rfc = (self.rfc or "").upper().strip()
        self.razon_social = (self.razon_social or "").upper().strip()
        self.nombre = (self.nombre or "").upper().strip()
        self.codigo = (self.codigo or "").upper().strip()
        self.telefono = (self.telefono or "").upper().strip()
        self.correo = (self.correo or "").strip()

        if not self.pk:
            self.total_credito = self.monto or 0.0
        # Si no hay código, genera uno automáticamente después de guardar (para tener el ID)
        if not self.codigo:
            super().save(*args, **kwargs)
            self.codigo = self.generar_folio()
            # Evita recursión infinita
            super().save(update_fields=["codigo"])
            return
        return super().save(*args, **kwargs)
    

class DireccionProveedor(BaseDireccion):
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE, related_name="direccion_proveedor")
    def __str__(self):
        return f"{self.calle}, {self.colonia or ''}, {self.municipio.nombre or ''}, {self.estado.nombre or '' }"



# ================================================================
#             PARA PRODUCTOS Y CATEGORÍAS
# =================================================================
class Categoria(BaseModel):
    """
    Modelo que representa una categoría de productos.

    Atributos:
        nombre (str): Nombre de la categoría.
        descripcion (str): Descripción opcional de la categoría.
    """

    nombre = models.CharField(max_length=50, blank=False, null=False, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, null=True,  verbose_name="Descripción")

    def __str__(self):
        return self.nombre
    
    def save(self, *args, **kwargs):
        self.nombre = (self.nombre or "").strip().upper()
        self.descripcion = (self.descripcion or "").strip()
        super().save(*args, **kwargs)


class Producto(BaseModel):
    
    COMPRA_LOCAL = 'Local'
    COMPRA_FORANEA = 'Foranea'
    COMPRAS_LIST = [
        (COMPRA_LOCAL, 'Local'),
        (COMPRA_FORANEA, 'Foranea'),
    ]
    NUMERO_COMPRAS  = 3
    UT_MAYOREO      = 15 / 100
    UT_SEMI_MAYOREO = 20 / 100
    UT_MENUDEO      = 25 / 100
    
    CANT_AUMENTO = 5.0

    codigo = models.CharField(max_length=30, unique=True, verbose_name="Código", blank=True, null=True)
    nombre = models.CharField(max_length=150, verbose_name="Nombre", blank=False, null=False)
    categoria = models.ForeignKey(Categoria,on_delete=models.SET_NULL,blank=True,null=True,verbose_name="Categoría",related_name="productos_categoria")
    #stock = models.PositiveIntegerField(default=0, verbose_name="Stock Global", blank=True, null=False)
    stock_minimo = models.DecimalField(
        max_digits=20,          # Total de dígitos (ajusta según tus necesidades)
        decimal_places=2,       # Número de decimales
        default=0,
        verbose_name="Stock Mínimo",
        blank=True,
        null=False
    )
    tipo_compra = models.CharField(max_length=20, choices=COMPRAS_LIST, default=COMPRA_LOCAL, verbose_name="Tipo de Compra", blank=True, null=True)
    imagen = models.ImageField(upload_to="productos/", blank=True, null=True)
    horas_caducidad = models.PositiveIntegerField(default=0, verbose_name="Horas de Caducidad", blank=True, null=True, help_text="Número de horas para que un lote caduque después de su creación. 0 = No caduca")
    proveedores = models.ManyToManyField('Proveedor',blank=True)
    precio_base = models.DecimalField(max_digits=20, decimal_places=2, default=0.0, verbose_name="Precio Base")
    precio_mayoreo = models.DecimalField(max_digits=20, decimal_places=2, default=0.0, verbose_name="Precio Mayoreo")
    precio_publico = models.DecimalField(max_digits=20, decimal_places=2, default=0.0, verbose_name="Precio Público")
    unidad_sat = models.ForeignKey('contabilidad.UnidadSat', on_delete=models.PROTECT, blank=True, null=True, default=None, verbose_name="Unidad SAT")
    clave_sat = models.CharField(max_length=10, blank=True, null=True, default="", verbose_name="Clave SAT (Producto o Servicio)")
    iva = models.DecimalField(max_digits=5, decimal_places=2, default=0.0 , verbose_name="IVA",blank=True, null=True)
    otro_impuesto = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, verbose_name="Otro Impuesto", blank=True, null=True)    
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción") 


    def generar_codigo(self):
        if self.pk:
            return f"PROD-{self.pk:06d}"
        return None
    

    @property
    def dias_caducidad(self):
        """Retorna las horas de caducidad convertidas a días (redondeando hacia arriba)"""
        if self.horas_caducidad and self.horas_caducidad > 0:
            return self.horas_caducidad // 24        
        return self.horas_caducidad 

    def __str__(self):
        return f"({self.codigo}) {self.nombre} - {(self.unidad_sat.clave if self.unidad_sat else '')}"

    def save(self, *args, **kwargs):
        # Formatea nombre y descripción antes de guardar
        self.nombre = (self.nombre or "").strip().upper()
        self.descripcion = self.descripcion if self.descripcion else ""
        self.clave_sat = (self.clave_sat or "").strip()
        #CONVERTIR DIAS A HORAS 
        if self.horas_caducidad > 0:
            self.horas_caducidad = self.horas_caducidad * 24
        super().save(*args, **kwargs)
        # Si no hay código, guarda primero para obtener el pk y luego genera el código
        if self.codigo == "" or self.codigo is None:
            self.codigo = self.generar_codigo()
            super().save(update_fields=["codigo"])
            
            return
        super().save(*args, **kwargs)
        
    def get_mi_stock_almacen(self, almacen_id=None):
        if not almacen_id:
            return 0
        from apps.inventario.models import LoteInventario
        lote_inventario = LoteInventario.objects.filter(
            producto=self,
            almacen_id=almacen_id,
            status_model=BaseModel.STATUS_MODEL_ACTIVE, 
            cantidad__gt=0
        ).aggregate(total_stock=models.Sum('cantidad'))
        return lote_inventario['total_stock'] or 0
    
    
    @property
    def precio_ultima_compra(self):
        object_compra = CompraDetalle.objects.filter(producto=self).order_by('-compra__created_at').first()
        if object_compra:
            return object_compra.precio_unitario
        return self.precio_base


    def get_mi_precio_cliente(self, cliente_id=None):
        if not cliente_id:
            return self.get_precio_menudeo()
        data_cliente = Cliente.objects.filter(id=cliente_id).values('precio_tipo').first()
        tipo_cliente = data_cliente['precio_tipo'] if data_cliente else Cliente.PUBLICO
        match tipo_cliente:
            case Cliente.MAYOREO:
                return self.get_precio_mayoreo()
            case Cliente.SEMI_MAYOREO:
                return self.get_precio_semi_mayoreo()
            case Cliente.PUBLICO:
                return self.get_precio_menudeo()
            case _:
                return self.get_precio_menudeo()

    def get_precio_mayoreo(self):
        return round(self.get_precio_unitario() * (1 + self.UT_MAYOREO), 2) + self.CANT_AUMENTO
    
    def get_precio_semi_mayoreo(self):
        return round(self.get_precio_unitario() * (1 + self.UT_SEMI_MAYOREO), 2) + self.CANT_AUMENTO

    def get_precio_menudeo(self):
        return round(self.get_precio_unitario() * (1 + self.UT_MENUDEO), 2) + self.CANT_AUMENTO


    def get_precio_unitario(self):
        """
        PROMEDIO PONDERADO
        Calcula el precio unitario ponderado:
        (C1*Q1 + C2*Q2 + ... + Cn*Qn) / (Q1 + Q2 + ... + Qn)
        """
        ultimas_compras = self._get_ultimas_compras(self.NUMERO_COMPRAS)
        if not ultimas_compras:
            return float(self.precio_ultima_compra)

        suma_q = 0
        suma_producto_precio = 0

        for compra in ultimas_compras:
            precio = float(compra.get('precio_unitario', 0))
            cantidad = float(compra.get('cantidad_entrada', 0))
            suma_producto_precio += precio * cantidad
            suma_q += cantidad

        return float(round(suma_producto_precio / suma_q, 2)) if suma_q else float(self.precio_ultima_compra)


    def _get_ultimas_compras(self, n=3):
        """
        Retorna las últimas n compras del producto
        
        Returns:
            QuerySet de diccionarios con precio_unitario, cantidad y cantidad_entrada
            [
                {'precio_unitario': Decimal('10.50'), 'cantidad': 100, 'cantidad_entrada': 100},
                {'precio_unitario': Decimal('10.00'), 'cantidad': 50, 'cantidad_entrada': 50},
                ...
            ]
        """
        return list(CompraDetalle.objects.filter(
            producto=self
        ).order_by('-compra__created_at')[:n].values(
            'precio_unitario', 'cantidad', 'cantidad_entrada'
        ))
# =================================================================
#                    ALAMCEN
# ================================================================
class Almacen(BaseModel):
    TIPO_FIJO = 'FIJO'
    TIPO_VIRTUAL = 'VIRT'
    TIPO_TRASPASO = 'TRAS'
    TIPO_COMPRA = 'COMP'
    TIPO_RUTA =  'RUTA'
    TIPO_HELP_CEDIS = 'HELP'
    TIPO_EMBARQUE = 'EMBA'
    TIPO_INCIDENCIAS = 'INSD'

    TIPO_CHOICES = [
        (TIPO_FIJO, 'FIJO'),
        (TIPO_VIRTUAL, 'VIRTUAL'),
        (TIPO_RUTA,'RUTA'),
        (TIPO_COMPRA,'COMPRA'),
        (TIPO_HELP_CEDIS,'HELP CEDIS'),
        (TIPO_EMBARQUE,'EMBARQUE'),
        (TIPO_TRASPASO,'TRASPASO'),
        (TIPO_INCIDENCIAS,'incidencias'),
    ] 
    
    class Meta:
        verbose_name = "Almacén"
        verbose_name_plural = "Almacenes"
        ordering = ["nombre"]
    nombre = models.CharField(max_length=200, verbose_name="Nombre", blank=False, null=False)
    codigo = models.CharField(max_length=20,verbose_name="Código",blank=False,null=True,unique=True)
    telefono = models.CharField(max_length=20, verbose_name="Teléfono", blank=True, null=True)
    encargado = models.ForeignKey(Usuario,on_delete=models.SET_NULL,null=True,blank=True,related_name="almacen_encargado",verbose_name="Encargado")
    comentarios = models.TextField(blank=True, null=True, verbose_name="Comentarios")
    info_extra = models.TextField(blank=True, null=True, verbose_name="Información Extra")
    is_cedis = models.BooleanField(default=False, verbose_name="Es CEDIS")
    is_ruta_fijo = models.BooleanField(default=False, verbose_name="Es Ruta Fijo")
    tipo = models.CharField(max_length=4,choices=TIPO_CHOICES, default=TIPO_FIJO, verbose_name='Tipo de almacen',blank=True,null=True)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="almacenes", verbose_name="Empresa", blank=False, null=False, default=1)
    pertence = models.ForeignKey('self', on_delete=models.SET_NULL, blank=True, null=True, verbose_name="Pertenece a o (obtener almacen tara)", related_name="almacenes_pertence")
    @property
    def direccion_principal(self):
        return self.direccion_almacen.first() if self.direccion_almacen.exists() else None

    def __str__(self):
        return f"[{self.codigo}] {self.nombre}" 
    
    def generar_codigo(self):
        if self.pk:
            return f"ALM-{self.pk:05d}"
        return None

    def save(self, *args, **kwargs):
        self.nombre = self.nombre.upper().strip()
        super().save(*args, **kwargs)
        # Si no hay código, guarda primero para obtener el pk y luego genera el código
        if self.codigo == "" or self.codigo is None:
            self.codigo = self.generar_codigo()
            super().save(update_fields=["codigo"])
            
            return
        super().save(*args, **kwargs)
        


class DireccionAlmacen(BaseDireccion):
    almacen = models.ForeignKey(
        Almacen, on_delete=models.CASCADE, related_name="direccion_almacen"
    )
    latitud = models.FloatField(blank=True, null=True, default=None, verbose_name="Latitud")
    longitud = models.FloatField(blank=True, null=True, default=None, verbose_name="Longitud")

    def __str__(self):
        return f"{self.calle}, {self.colonia or ''}, {self.municipio or ''}, {self.estado or ''}"



# =================================================================
#                    SUCURSAL
# ================================================================
class Sucursal(BaseModel):
    class Meta:
        verbose_name = "Sucursal"
        verbose_name_plural = "Sucursales"
        ordering = ["nombre"]
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="sucursales", verbose_name="Empresa")
    nombre = models.CharField(max_length=200, verbose_name="Nombre", blank=False, null=False)
    codigo = models.CharField(max_length=20, verbose_name="Código", blank=False, null=True, unique=True)
    telefono = models.CharField(max_length=20, verbose_name="Teléfono", blank=True, null=True)
    encargado = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name="sucursal_encargado", verbose_name="Encargado")
    comentarios = models.TextField(blank=True, null=True, verbose_name="Comentarios")
    
    # ✅ Relación muchos a muchos simple (sin through)
    almacenes = models.ManyToManyField(
        Almacen, 
        related_name="sucursales", 
        blank=True, 
        verbose_name="Almacenes"
    )
    
    @property
    def direccion_principal(self):
        return self.direccion_sucursal.first() if self.direccion_sucursal.exists() else None
    
    @property
    def mi_empresa(self):
        return self.empresa.nombre if self.empresa else "Sin Empresa"
    
    @property
    def nombre_completo(self):
        almacenes_nombres = ", ".join([almacen.nombre for almacen in self.almacenes.all()])
        return f"{self.nombre} ({self.codigo}) [{almacenes_nombres or 'Sin Almacenes'}] [{self.encargado.username if self.encargado else 'Sin Encargado'}]"
    
    @property
    def total_almacenes(self):
        """Retorna el número total de almacenes asignados a la sucursal"""
        return self.almacenes.count()
        
    def generar_codigo(self):
        if self.pk:
            return f"SUC-{self.pk:05d}"
        return None
    
    def __str__(self):
        return f"[{self.codigo}] {self.nombre}" 
    
    def save(self, *args, **kwargs):
        self.nombre = self.nombre.upper().strip()
        
        # Si no hay código, genera uno automáticamente
        if not self.codigo:
            super().save(*args, **kwargs)
            self.codigo = self.generar_codigo()
            super().save(update_fields=["codigo"])
            return
        
        super().save(*args, **kwargs)


class DireccionSucursal(BaseDireccion):
    sucursal = models.ForeignKey(
        Sucursal, on_delete=models.CASCADE, related_name="direccion_sucursal"
    )
    latitud = models.FloatField(blank=True, null=True, default=None, verbose_name="Latitud")
    longitud = models.FloatField(blank=True, null=True, default=None, verbose_name="Longitud")

    def __str__(self):
        return f"{self.calle}, {self.colonia or ''}, {self.municipio or ''}, {self.estado.nombre or ''}"



#=====================================================
#                  CLIENTES
#=====================================================
class CategoriaCliente(BaseModel):
    nombre = models.CharField(max_length=100, verbose_name="Nombre", blank=False, null=False)
    limite_credito_max = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="Límite de Crédito máximo", default=0.00)
    limite_credito_min = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="Límite de Crédito mínimo", default=0.00)
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")

    def __str__(self):
        return self.nombre
    
    def save(self, *args, **kwargs):
        self.nombre = (self.nombre or "").strip().upper()
        self.descripcion = (self.descripcion or "").strip()
        super().save(*args, **kwargs)
    
class Cliente(BaseModel):    
    TIPO_POTENCIAL       = "POTENCIAL"
    TIPO_ESTANDAR        = "ESTANDAR"
    TIPO_NO_CREDITO      = "NO CREDITO"
    TIPO_CREDITO_SEMANAL = "CREDITO SEMANAL"
    TIPO_EVENTUAL        = "EVENTUAL"
    TIPO_BUEN_CLIENTE    = "BUEN CLIENTE"
    TIPO_PREMIUM         = "PREMIUM"

    TIPO_LIST = [
        (TIPO_POTENCIAL, "Potencial"),
        (TIPO_ESTANDAR, "Estándar"),
        (TIPO_NO_CREDITO, "No Crédito"),
        (TIPO_CREDITO_SEMANAL, "Crédito Semanal"),
        (TIPO_EVENTUAL, "Eventual"),
        (TIPO_BUEN_CLIENTE, "Buen Cliente"),
        (TIPO_PREMIUM, "Premium"),
    ]

    SEMI_MAYOREO = "SEMI MAYOREO"
    MAYOREO = "MAYOREO"
    PUBLICO = "PÚBLICO"
    TIPO_PRECIO_CHOICES = [
        (SEMI_MAYOREO, SEMI_MAYOREO),
        (MAYOREO, MAYOREO),
        (PUBLICO, PUBLICO),
    ]
    
    PERSONA_FISICA = "PERSONA FISICA"
    PERSONA_MORAL = "PERSONA MORAL"
    PERSONA_CHOICES = [
        (PERSONA_FISICA, "Persona Física"),
        (PERSONA_MORAL, "Persona Moral"),
    ]
    
    codigo = models.CharField(max_length=20, verbose_name="Código", blank=False, null=True, unique=True)
    nombre = models.CharField(max_length=200, verbose_name="Nombres", blank=True, null=False,default=None)
    apellido_paterno = models.CharField(max_length=200, verbose_name="Apellido Paterno", blank=True, null=True)
    apellido_materno = models.CharField(max_length=200, verbose_name="Apellido Materno", blank=True, null=True)
    razon_social = models.CharField(max_length=180, verbose_name="Razón social", blank=True, null=True)
    tipo_persona = models.CharField(max_length=20, choices=PERSONA_CHOICES, verbose_name="Tipo de Persona", default=PERSONA_FISICA, blank=True, null=True)
    telefono = models.CharField(max_length=15, verbose_name="Teléfono", blank=True, null=True)
    email = models.EmailField(max_length=150,verbose_name="Correo Electrónico", blank=True, null=True)
    tipo = models.CharField(max_length=20, choices=TIPO_LIST, verbose_name="Tipo de Cliente", default=TIPO_ESTANDAR)
    rfc = models.CharField(max_length=15, verbose_name="RFC", blank=True, null=True)
    uso_cfdi = models.CharField(max_length=100, verbose_name="Uso CFDI", blank=True, null=True,default=None)
    regimen_fiscal = models.ForeignKey('contabilidad.RegimenFiscal', on_delete=models.SET_NULL, blank=True, null=True,default=None, verbose_name="Régimen Fiscal", related_name="cliente_regimen_fiscal")
    limite_credito = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="Límite de crédito", default=None, blank=True, null=True)
    total_credito = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="Total de crédito", default=0.00, blank=True, null=True)
    plazos_semanas = models.IntegerField(verbose_name="Plazos en semanas", default=0, blank=True, null=True)
    precio_tipo = models.CharField(max_length=15, choices=TIPO_PRECIO_CHOICES, verbose_name="Lista de precios", default=PUBLICO)
    vendedor = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name="cliente_vendedor", verbose_name="Vendedor Asignado")
    clasificacion = models.ForeignKey(CategoriaCliente, on_delete=models.SET_NULL, blank=True, null=True, verbose_name="Clasificación de Cliente", related_name="clientes_clasificacion")
    sujeto_credito = models.BooleanField(default=False, verbose_name="Sujeto a Crédito")
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['nombre', 'apellido_paterno', 'apellido_materno'],
                name='unique_nombre_completo'
            )
        ]
    
    def __str__(self):
        return self.get_full_name

    def puede_pagar_credito(self, monto=0):
        
        #SI M ONTOP ES MAYOR A CERO, ENTONCES PUEDE PAGAR
        monto = float(monto)
        if monto > self.total_credito:
            print(f"El monto {monto} excede el crédito total {self.total_credito}.")
            return False
        
        if self.sujeto_credito is False:
            print(f"El cliente {self.nombre} no es sujeto a crédito.")
            return False
        if self.total_credito == 0:
            print(f"El cliente {self.nombre} no tiene crédito disponible.")
            return False
        #from apps.credito.models import CreditoCliente
        creditos_activos = self.creditos.filter(is_pagado=False)
        creditos_vencidos_count = 0
        for credito in creditos_activos:
            if credito.ha_vencido:
                creditos_vencidos_count += 1
                
        if creditos_vencidos_count > 0:
            print(f"El cliente {self.nombre} tiene {creditos_vencidos_count} créditos vencidos.")
            return False
        
        return True

    @property
    def get_full_name(self):
        if self.nombre.strip() == "":
            return f"{self.codigo} - {self.razon_social or ''}".strip()
        return f"{self.codigo} - {self.nombre} {self.apellido_paterno} {self.apellido_materno or ''}".strip()
    @property
    def nombre_completo(self):
        return f"{self.nombre or ''} {self.apellido_paterno or ''} {self.apellido_materno or ''}".strip()

    @property
    def direccion_principal(self):
        return self.direccion_cliente.first()
    
    def generar_codigo(self):
        if self.pk:
            return f"CLI-{self.pk:05d}"
        return None

    def save(self, *args, **kwargs):
        # Normalizar datos ANTES de guardar
        self.email = (self.email or "").lower().strip()
        self.telefono = (self.telefono or "").strip()
        self.rfc = (self.rfc or "").strip().upper()
        self.uso_cfdi = (self.uso_cfdi or "").strip().upper()
        self.razon_social = (self.razon_social or "").strip().upper()
        self.nombre = (self.nombre or "").strip().upper()
        self.apellido_materno = (self.apellido_materno or "").strip().upper()
        self.apellido_paterno = (self.apellido_paterno or "").strip().upper()
        if self.pk is None:
            self.total_credito = self.limite_credito if self.sujeto_credito else 0.00

        # Si no hay código, genera uno automáticamente
        if not self.codigo:
            super().save(*args, **kwargs)
            self.codigo = self.generar_codigo()
            super().save(update_fields=["codigo"])
            return
        
        super().save(*args, **kwargs)

class DireccionCliente(BaseDireccion):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="direccion_cliente")
    latitud = models.FloatField(blank=True, null=True, default=None, verbose_name="Latitud")
    longitud = models.FloatField(blank=True, null=True, default=None, verbose_name="Longitud")


"""
=======================================================================
                    MODELO DE ORDEN DE COMPRA
=======================================================================
"""
class OrdenCompra(BaseModel):
    class Meta:
        verbose_name = "Orden de Compra"
        verbose_name_plural = "Órdenes de Compra"
    SOLICITUD = "SOLICITUD"
    PENDIENTE = "PENDIENTE"
    EN_PROCESO = "EN PROCESO"
    CANCELADA = "CANCELADA"
    FINALIZADA = "FINALIZADA"
    #FINALIZADA_DIFERIDO = "FINALIZADA CON DIFERIDO"

    ESTADO_ORDEN_COMPRA_CHOICES = [
        (SOLICITUD, SOLICITUD),
        (PENDIENTE, PENDIENTE),
        (EN_PROCESO, EN_PROCESO),
        (CANCELADA, CANCELADA),
        (FINALIZADA, FINALIZADA)
        #(FINALIZADA_DIFERIDO, FINALIZADA_DIFERIDO),
    ]
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE, related_name="ordenes_compra", verbose_name="Proveedor")
    condicion_pago = models.CharField(
        max_length=50,
        choices=CondicionPago.CONDICIONES_LIST,
        default=CondicionPago.CONDICION_CONTADO,
        null=False,
        blank=False,
        verbose_name="Condición de Pago"
    )
    codigo = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="Folio")
    estado = models.CharField(max_length=30, choices=ESTADO_ORDEN_COMPRA_CHOICES, default=SOLICITUD, verbose_name="Estado")
    #total = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total")
    encargado = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name="orden_compra_encargado", verbose_name="Encargado")
    # asignado_a = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name="orden_compra_asignado", verbose_name="Asignado a")

    def recalcular_pagos(self):
            total = sum(
                d.cantidad * d.precio
                for d in self.detalles.all()
            )

            self.pagos_orden_compra.update(monto=total)
    def get_total(self):
        return sum(detalle.subtotal * detalle.cantidad for detalle in self.detalles.all())
    
    def generar_codigo(self):
        if self.pk:
            return f"OC-{self.pk:09d}"
        return None

    def save(self, *args, **kwargs):
       # Si no hay código, genera uno automáticamente
        if not self.codigo:
            super().save(*args, **kwargs)
            self.codigo = self.generar_codigo()
            super().save(update_fields=["codigo"])
            return
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Orden de Compra {self.codigo} - {self.proveedor.nombre}"

class OrdenCompraDetalle(models.Model):
    orden_compra = models.ForeignKey(OrdenCompra, on_delete=models.CASCADE, related_name="detalles", verbose_name="Orden de Compra")
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="ordenes_compra", verbose_name="Producto")
    cantidad = models.DecimalField(max_digits=25, decimal_places=5, verbose_name="Cantidad")
    precio = models.DecimalField(max_digits=25, decimal_places=5, verbose_name="Precio Unitario" , blank=False, null=False, default=0.0)
    #subtotal = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Subtotal", default=0.0 )

    @property
    def subtotal(self):
        return self.cantidad * self.precio

    def __str__(self):
        return f"Detalle {self.pk} - {self.producto.nombre}: {self.cantidad} x {self.precio_unitario} = {self.subtotal}"



"""
=======================================================================
                    MODELO DE UNIDADES
=======================================================================
"""
class UnidadVehicular(BaseModel):
    class Meta:
        verbose_name = "Unidad Vehicular"
        verbose_name_plural = "Unidades Vehiculares"
        ordering = ["id"]
    
    CAMION = "CAMIÓN"
    CAMIONETA = "CAMIONETA"
    TRAILER = "TRÁILER"
    OTRO = "OTRO"

    TIPO_CHOICES = [
        (CAMION, CAMION),
        (CAMIONETA, CAMIONETA),
        (TRAILER, TRAILER),
        (OTRO, OTRO),
    ]
    nombre = models.CharField(max_length=100, verbose_name="Nombre de la Unidad", blank=False, null=False)
    tipo   = models.CharField(max_length=20, choices=TIPO_CHOICES, verbose_name="Tipo de Vehículo", default=CAMION, blank=False, null=False)
    placas = models.CharField(max_length=20, verbose_name="Placas", blank=True, null=True, unique=True)
    marca  = models.CharField(max_length=50, verbose_name="Marca",   blank=True, null=True)
    modelo = models.CharField(max_length=50, verbose_name="Modelo", blank=True, null=True)
    anio   = models.PositiveIntegerField(verbose_name="Año", blank=True, null=True)
    capacidad_carga = models.DecimalField(null=True, blank=True,max_digits=20, decimal_places=2, verbose_name="Capacidad de Carga (Tons)",help_text="Capacidad de carga en toneladas")
    fecha_adquisicion = models.DateField(null=True, blank=True, verbose_name="Fecha de Adquisición")

    def __str__(self):
        return f"{self.nombre} - {self.placas} ({self.tipo})"
    
    def get_clave(self):
        if self.id:
            return f"UV-{self.id:06d}"
        return "UV-PENDIENTE"


"""
=======================================================================
                    MODELO DE RUTAS
=======================================================================
"""
class Rutas(BaseModel):
    class Meta:
        verbose_name = "Ruta de Entrega"
        verbose_name_plural = "Rutas de Entrega"
        ordering = ["nombre"]

    codigo = models.CharField(max_length=20, verbose_name="Código", blank=False, null=True, unique=True)
    asignado = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name="rutas_asignadas", verbose_name="Chofer Asignado")
    unidad = models.ForeignKey(UnidadVehicular, on_delete=models.PROTECT, null=False, blank=False, related_name="rutas_unidad", verbose_name="Unidad Vehicular Asignada")

    nombre = models.CharField(max_length=100, verbose_name="Nombre de la Ruta", blank=False, null=False)
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción de la Ruta")
    
    origen = models.CharField(max_length=100, verbose_name="Origen", blank=False, null=False)
    destino = models.CharField(max_length=100, verbose_name="Destino", blank=False, null=False)

    almacen = models.ForeignKey(Almacen, on_delete=models.SET_NULL, related_name="rutas", verbose_name="Almacén para vender (tara abierta)", default=None, blank=True, null=True)
    almacen_embarque = models.ForeignKey(Almacen, on_delete=models.SET_NULL, related_name="rutas_embarque", verbose_name="Almacén de pedidos", default=None, blank=True, null=True)
    def generar_codigo(self):
        if self.pk:
            return f"RUTA-{self.pk:08d}"
        return None
    
    def save(self, *args, **kwargs):
        # Si no hay código, genera uno automáticamente
        self.nombre = (self.nombre or "").strip().upper()
        #self.unidad = (self.unidad or "").strip().upper()
        self.origen = (self.origen or "").strip().upper()
        self.destino = (self.destino or "").strip().upper()

        if not self.codigo:
            super().save(*args, **kwargs)
            self.codigo = self.generar_codigo()
            super().save(update_fields=["codigo"])
            return
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

"""
=======================================================================
                    MODELO DE COMPRA
=======================================================================
"""
class Compra(BaseModel):

    class Meta:
        verbose_name = "Compra"
        verbose_name_plural = "Compras"

    PROCESANDO = "PROCESANDO"
    EN_CAMINO = "EN CAMINO"
    FINALIZADA = "FINALIZADA"
    CANCELED = "CANCELADA"
    
    ALMACEN_VIRTUAL = "ALMACEN VIRTUAL"
    ALMACEN = "ALMACEN"


    ESTADO_COMPRA_CHOICES = [
        (PROCESANDO, PROCESANDO),
        (EN_CAMINO, EN_CAMINO),
        (FINALIZADA, FINALIZADA),
        (CANCELED, CANCELED),
        #(ALMACEN_VIRTUAL, ALMACEN_VIRTUAL),
        #(ALMACEN, ALMACEN),

    ]
    condicion_pago = models.CharField(
        max_length=50,
        choices=CondicionPago.CONDICIONES_LIST,
        default=CondicionPago.CONDICION_CONTADO,
        null=False,
        blank=False,
        verbose_name="Condición de Pago"
    )
    orden_compra = models.ForeignKey(OrdenCompra, on_delete=models.SET_NULL, blank=True, null=True, related_name="compras", verbose_name="Orden de Compra")
    codigo = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="Folio")
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE, related_name="compras", verbose_name="Proveedor")
    almacen_destino = models.ForeignKey(Almacen, on_delete=models.CASCADE, related_name="compras", verbose_name="Almacén")
    almacen_virtual = models.ForeignKey(Almacen, on_delete=models.CASCADE, related_name="compras_virtuales", verbose_name="Almacén Virtual")
    tiempo_recorrido = models.IntegerField(blank=True, null=True, default=None, verbose_name="Tiempo Recorrido")
    fecha_salida = models.DateField(blank=True, null=True, default=None, verbose_name="Fecha de Salida")
    fecha_vencimiento = models.DateField(blank=True, null=True, verbose_name="Fecha de Vencimiento")
    estado = models.CharField(max_length=20, choices=ESTADO_COMPRA_CHOICES, default=ALMACEN_VIRTUAL, verbose_name="Estado")
    total = models.DecimalField(max_digits=25, decimal_places=2, verbose_name="Total")
    latitud = models.FloatField(blank=True, null=True, default=None, verbose_name="Latitud")
    longitud = models.FloatField(blank=True, null=True, default=None, verbose_name="Longitud")
    existe_diferencia = models.BooleanField(default=False, verbose_name="Existe Diferencia")
    nota = models.TextField(blank=True, null=True, verbose_name="Nota")
    is_app = models.BooleanField(default=True, verbose_name="Creado desde App Móvil")

    def generar_codigo(self):
        if self.pk:
            return f"COMPRA-{self.pk:08d}"
        return None
    

    def __str__(self):
        return f"Compra {self.codigo} - {self.proveedor.nombre}"
    
    def save(self, *args, **kwargs):        
        if isinstance(self.codigo, str):
            self.codigo = self.codigo.strip()

        # Fecha vencimiento
        if not self.fecha_vencimiento:
            producto = getattr(self, "producto", None)
            dias = getattr(producto, "dias_caducidad", None)
            try:
                dias = int(dias) if dias is not None else 0
            except (TypeError, ValueError):
                dias = 0

            if 0 < dias <= 36500:
                try:
                    self.fecha_vencimiento = (self.created_at or timezone.now()) + timedelta(days=dias)
                except OverflowError:
                    self.fecha_vencimiento = None
            else:
                self.fecha_vencimiento = None

        # Si no hay folio, guarda primero para obtener pk
        creating_without_code = not self.codigo
        super().save(*args, **kwargs)

        # Genera folio solo después de tener pk
        if creating_without_code and self.pk:
            new_code = self.generar_codigo()
            if new_code and self.codigo != new_code:
                # update() evita reentrar al save
                type(self).objects.filter(pk=self.pk).update(codigo=new_code)
                self.codigo = new_code


class CompraDetalle(models.Model):
    class Meta:
        verbose_name = "Detalle de Compra"
        verbose_name_plural = "Detalles de Compra"

    compra = models.ForeignKey(Compra, on_delete=models.CASCADE, related_name="detalles", verbose_name="Compra")
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="compras", verbose_name="Producto")
    cantidad = models.DecimalField(max_digits=25, decimal_places=5, verbose_name="Cantidad")
    precio_unitario = models.DecimalField(max_digits=25, decimal_places=5, verbose_name="Precio Unitario")
    subtotal = models.DecimalField(max_digits=25, decimal_places=5, verbose_name="Subtotal", editable=False)
    existe_diferencia = models.BooleanField(default=False, verbose_name="Existe Diferencia")
    es_producto_nuevo = models.BooleanField(default=False, verbose_name="Es Nuevo")
    cantidad_entrada = models.DecimalField(max_digits=25, decimal_places=3, verbose_name="Diferencia", default=0.00)
    def save(self, *args, **kwargs):
        from decimal import Decimal
        if self.cantidad is not None and not isinstance(self.cantidad, Decimal):
            self.cantidad = Decimal(str(self.cantidad))
        if self.precio_unitario is not None and not isinstance(self.precio_unitario, Decimal):
            self.precio_unitario = Decimal(str(self.precio_unitario))
        self.subtotal = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Detalle {self.pk} - {self.producto.nombre}: {self.cantidad} x {self.precio_unitario} = {self.subtotal}"


class PagosCompra(BaseModel):
    class Meta:
        verbose_name = "Pago de Compra"
        verbose_name_plural = "Pagos de Compras"

    compra = models.ForeignKey(Compra, on_delete=models.SET_NULL, blank=True, null=True, related_name="pagos", verbose_name="Compra")
    orden_compra = models.ForeignKey(OrdenCompra, on_delete=models.SET_NULL, blank=True, null=True, related_name="pagos_orden_compra", verbose_name="Orden de Compra")
    monto = models.DecimalField(max_digits=25, decimal_places=5, verbose_name="Monto")
    metodo_pago = models.ForeignKey('contabilidad.MetodoPago', on_delete=models.SET_NULL, blank=True, null=True, verbose_name="Método de Pago")
    fecha_pagar = models.DateField(blank=True, null=True, default=None, verbose_name="Fecha a Pagar")
    referencia = models.CharField(max_length=100, verbose_name="Referencia", blank=True, null=True)

    def __str__(self):
        return f"Pago {self.pk} - {self.compra.codigo}: {self.monto}"
   
class GastosCompra(BaseModel):
    class Meta:
        verbose_name = "Gasto de Compra"
        verbose_name_plural = "Gastos de Compras"

    compra = models.ForeignKey(Compra, on_delete=models.SET_NULL, blank=True, null=True, related_name="gastos", verbose_name="Compra")
    concepto = models.CharField(max_length=150, verbose_name="Concepto", blank=False, null=False)
    descripcion = models.CharField(max_length=250, verbose_name="Descripción", blank=False, null=False)
    monto = models.DecimalField(max_digits=25, decimal_places=5, verbose_name="Monto")
    
    
    @property
    def folio(self):
        return f"GASTO-{self.pk:08d}"

    def __str__(self):
        return f"Gasto {self.pk} - {self.compra.codigo}: {self.concepto} - {self.monto}"
    
"""
=======================================================================
                    MODELOS DE VENTA
=======================================================================
"""
class Venta(BaseModel):
    class Meta:
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"
    FASE_PRE_VENTA  = "PRE VENTA"
    FASE_VENTA_COMANDA = "VENTA COMANDERA"
    FASE_EN_PROCESO = "EN CURSO"
    FASE_TERMINADA  = "TERMINADA"
    FASE_CANCELADA  = "CANCELADA"
    FASE_CHOICES = [
        (FASE_PRE_VENTA, FASE_PRE_VENTA),
        (FASE_VENTA_COMANDA, FASE_VENTA_COMANDA),
        (FASE_EN_PROCESO, FASE_EN_PROCESO),
        (FASE_TERMINADA, FASE_TERMINADA),
        (FASE_CANCELADA, FASE_CANCELADA),
    ]
    COMANDERA = "COMANDERA"
    MOSTRADOR = "MOSTRADOR"
    TIPO_VENTA_CHOICES = [
        (COMANDERA, COMANDERA),
        (MOSTRADOR, MOSTRADOR),
    ]
    
    
    almacen = models.ForeignKey(Almacen, on_delete=models.CASCADE, related_name="ventas", verbose_name="Almacén afectado")
    codigo = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="Folio")
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="ventas", verbose_name="Cliente")
    fase = models.CharField(max_length=20, choices=FASE_CHOICES, default=FASE_TERMINADA, verbose_name="Fase")
    tipo_venta = models.CharField(max_length=20, choices=TIPO_VENTA_CHOICES, default=MOSTRADOR, verbose_name="Tipo de Venta")
    ruta = models.ForeignKey(Rutas, on_delete=models.SET_NULL, blank=True, null=True, related_name="ventas", verbose_name="Ruta")
    was_preventa = models.BooleanField(default=False, verbose_name="Fue Preventa")
    falta_inventario = models.BooleanField(default=False, verbose_name="Falta producto en Inventario")
    is_total_cargado = models.BooleanField(default=False, verbose_name="Total Cargado", help_text="Indica si el total de mercancia en la preventa ya fue cargada al almacen de su ruta fue ingresado en su totalidad")
    is_entregado = models.BooleanField(default=False, verbose_name="Entregado", help_text="Indica si la venta ya fue entregada al cliente")
    total = models.DecimalField(max_digits=25, decimal_places=5, verbose_name="Total")
    condicion_pago = models.CharField(
        max_length=50,
        choices=CondicionPago.CONDICIONES_LIST,
        default=CondicionPago.CONDICION_CONTADO,
        null=False,
        blank=False,
        verbose_name="Condición de Pago"
    )
    vendedor = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name="ventas_vendedor", verbose_name="Vendedor Asignado",default=None)
    total_pagado = models.DecimalField(max_digits=25, decimal_places=5, verbose_name="Total Pagado", default=0.00)
    ya_terminada = models.BooleanField(default=False, verbose_name="Ya Terminada", help_text="Indica si la venta ya fue finalizada")
    ignorada = models.BooleanField(default=False, verbose_name="Venta Ignorada", help_text="Indica si la venta fue ignorada en el sistema para cierre")
    cambio = models.DecimalField(max_digits=25, decimal_places=5, verbose_name="Cambio Entregado", default=0.00)
    
    
    
    
    def referencia_busqueda(self):
        return f"VENTA-{self.pk}"
    
    def adeudo(self):
        return float(self.total) - float(self.total_pagado)

    def generar_codigo(self):
        if self.pk:
            if self.fase == self.FASE_PRE_VENTA:
                return f"PREV-{self.pk:08d}"
            elif self.fase == self.FASE_VENTA_COMANDA:
                return f"VENTA-C-{self.pk:08d}"
            else:
                return f"VENTA-{self.pk:08d}"
        return None
    
    def clean(self):
        """
        Validaciones del modelo
        """
        from django.core.exceptions import ValidationError
        
        # Si es FASE_PRE_VENTA, la ruta es obligatoria
        if self.fase == self.FASE_PRE_VENTA and not self.ruta:
            raise ValidationError({
                'ruta': 'La ruta es obligatoria cuando la fase es PRE VENTA.'
            })
        
    def ventas_abiertas_count(self, fecha=None,cajero=None):
        
        """
        Retorna el número de ventas abiertas (no terminadas ni canceladas) para el cliente
        """
        if not fecha:
            fecha = timezone.now()
        
        return self.objects.filter(
            ya_terminada=False,
            ignorada=False,
            created_at__date=fecha.date(),
            created_by=cajero,
        ).count() 
    
    def __str__(self):
        return f"{self.codigo} - {self.cliente.nombre}: {self.total}"
    

    def save(self, *args, **kwargs):
        # Ejecutar validaciones antes de guardar
        self.clean()
        if self.fase == self.FASE_VENTA_COMANDA:
            self.tipo_venta = self.COMANDERA
        if self.fase == self.FASE_PRE_VENTA:
            self.was_preventa = True
        if self.is_total_cargado:
            #print("La venta ya fue cargada al almacén de la ruta fase Procesando")
            self.fase = self.FASE_EN_PROCESO
        
        if not self.codigo:
            super().save(*args, **kwargs)
            self.codigo = self.generar_codigo()
            super().save(update_fields=["codigo"])
            return
        
        if self.fase == self.FASE_CANCELADA:
            self.is_entregado = False
            self.ya_terminada = True
        
         # Verificar si el adeudo es cero o negativo para marcar como terminada
        # 🔑 Si ya no hay adeudo, es CONTADO
        if float(self.adeudo()) <= 0:
            self.condicion_pago = CondicionPago.CONDICION_CONTADO

        if float(self.adeudo()) <= 0.0:
            self.ya_terminada = True
        super().save(*args, **kwargs)

class VentaDetalle(models.Model):
    class Meta:
        verbose_name = "Detalle de Venta"
        verbose_name_plural = "Detalles de Venta"

    venta = models.ForeignKey(Venta,on_delete=models.CASCADE, related_name="detalles", verbose_name="Venta")
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="ventas", verbose_name="Producto")
    cantidad = models.DecimalField(max_digits=20, decimal_places=5, verbose_name="Cantidad")
    cantidad_entregada = models.DecimalField(max_digits=20, decimal_places=5, verbose_name="Cantidad Entregada", default=0.00)
    cantidad_cargada = models.DecimalField(max_digits=20, decimal_places=5, verbose_name="Cantidad Cargada", default=0.00)
    cantidad_logistica = models.DecimalField(max_digits=20, decimal_places=5, verbose_name="Cantidad Logística", default=0.00)
    precio_unitario = models.DecimalField(max_digits=20, decimal_places=5, verbose_name="Precio Unitario")
    subtotal = models.DecimalField(max_digits=25, decimal_places=5, verbose_name="Subtotal", editable=False)
    is_cargado = models.BooleanField(default=False, verbose_name="Cargado en Almacén", help_text="Indica si este lote ya fue cargado en el almacén de la ruta")
    is_entregado = models.BooleanField(default=False, verbose_name="Entregado", help_text="Indica si este lote ya fue entregado al cliente")
    
    def save(self, *args, **kwargs):
        from decimal import Decimal
        if self.cantidad is not None and not isinstance(self.cantidad, Decimal):
            self.cantidad = Decimal(str(self.cantidad))
        if self.precio_unitario is not None and not isinstance(self.precio_unitario, Decimal):
            self.precio_unitario = Decimal(str(self.precio_unitario))
        self.subtotal = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Detalle {self.pk} - {self.producto.nombre}: {self.cantidad} x {self.precio_unitario} = {self.subtotal}"

class VentaDetalleLote(models.Model):
    """
    Modelo para controlar qué lotes específicos se utilizan en cada detalle de venta
    Permite trazabilidad completa del inventario por lotes en las ventas
    """
    class Meta:
        verbose_name = "Lote en Detalle de Venta"
        verbose_name_plural = "Lotes en Detalles de Venta"
        constraints = [
            models.UniqueConstraint(
                fields=['venta_detalle', 'lote_inventario'],
                name='unique_venta_detalle_lote'
            )
        ]

    venta_detalle = models.ForeignKey(
        VentaDetalle, 
        on_delete=models.CASCADE, 
        related_name="lotes_utilizados", 
        verbose_name="Detalle de Venta"
    )
    lote_inventario = models.ForeignKey(
        'inventario.LoteInventario', 
        on_delete=models.PROTECT,  # No permitir eliminar lotes con ventas
        related_name="ventas_realizadas", 
        verbose_name="Lote de Inventario"
    )
    cantidad_utilizada = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        verbose_name="Cantidad Utilizada del Lote"
    )
    costo_unitario_lote = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        verbose_name="Costo Unitario del Lote",
        help_text="Costo del producto en este lote específico"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Registro")

    def clean(self):
        """
        Validaciones del modelo
        """
        from django.core.exceptions import ValidationError
        
        # Validar que el producto del detalle coincida con el del lote
        if (self.venta_detalle and self.lote_inventario and 
            self.venta_detalle.producto != self.lote_inventario.producto):
            raise ValidationError(
                "El producto del detalle de venta debe coincidir con el producto del lote."
            )
        
        # Validar que haya suficiente cantidad en el lote
        if self.lote_inventario and self.cantidad_utilizada:
            if self.cantidad_utilizada > self.lote_inventario.cantidad:
                raise ValidationError(
                    f"No hay suficiente cantidad en el lote. "
                    f"Disponible: {self.lote_inventario.cantidad}, "
                    f"Solicitado: {self.cantidad_utilizada}"
                )

    def save(self, *args, **kwargs):
        """
        Guardar y actualizar automáticamente el costo del lote
        """
        # Auto-completar el costo unitario del lote si no se proporciona
        if not self.costo_unitario_lote and self.lote_inventario:
            self.costo_unitario_lote = self.lote_inventario.costo_unitario
        
        self.clean()  # Ejecutar validaciones
        super().save(*args, **kwargs)

    def __str__(self):
        return (f"Lote {self.lote_inventario.id} → Venta {self.venta_detalle.venta.codigo}: "
                f"{self.cantidad_utilizada} unidades")

class PagosVenta(BaseModel):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name="pagos", verbose_name="Venta")
    monto = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="Monto")
    metodo_pago = models.ForeignKey(MetodoPago, on_delete=models.SET_NULL, blank=True, null=True, verbose_name="Método de Pago")
    #fecha_pagar = models.DateField(blank=True, null=True, default=None, verbose_name="Fecha a Pagar")
    referencia = models.CharField(max_length=100, blank=True, null=True, verbose_name="Referencia de Pago")

    class Meta:
        verbose_name = "Pago de Venta"
        verbose_name_plural = "Pagos de Ventas"
        
    @property
    def clave(self):
        return f"PV-{self.pk:08d}"

    def __str__(self):
        return f"Pago {self.clave} - Venta {self.venta.codigo}: {self.monto} ({self.metodo_pago})"




"""
=======================================================================
                    MODELO DE NOTIFICACIONES
=======================================================================
"""
class Notificacion(models.Model):
    TIPO_INFO = 'info'
    TIPO_SUCCESS = 'success'
    TIPO_WARNING = 'warning'
    TIPO_ERROR = 'error'
    TIPO_MENSAJE = 'mensaje'
    TIPO_CHOICES = [
        (TIPO_INFO, TIPO_INFO),
        (TIPO_SUCCESS, TIPO_SUCCESS),
        (TIPO_WARNING, TIPO_WARNING),
        (TIPO_ERROR, TIPO_ERROR),
        (TIPO_MENSAJE, TIPO_MENSAJE),
    ]

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='notificaciones',
        help_text="Usuario que recibirá la notificación."
    )
    titulo = models.CharField(max_length=255)
    mensaje = models.TextField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='info')
    url_destino = models.URLField(
        blank=True, null=True,
        help_text="Enlace opcional al que redirige la notificación."
    )
    leida = models.BooleanField(default=False)
    creada_el = models.DateTimeField(default=timezone.now)
    leida_el = models.DateTimeField(blank=True, null=True)
    leida_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name='notificaciones_leidas',
        help_text="Usuario que marcó la notificación como leída."
    )

    class Meta:
        ordering = ['-creada_el']
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"

    def __str__(self):
        return f"{self.titulo} ({'Leída' if self.leida else 'No leída'})"

    def marcar_como_leida(self):
        """Marca la notificación como leída."""
        if not self.leida:
            self.leida = True
            self.leida_el = timezone.now()
            self.save()
            

"""
=======================================================================
                        MODELO DE CAJA
=======================================================================
"""

class Caja(BaseModel):
    RUTA = "RUTA"
    SUCURSAL = "SUCURSAL"
    TIPO_CHOICES = [
        (RUTA, RUTA),
        (SUCURSAL, SUCURSAL),
    ]
    class Meta:
        verbose_name = "Caja"
        verbose_name_plural = "Cajas"
        ordering = ["nombre"]
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, verbose_name="Tipo de Caja", default=SUCURSAL)
    nombre = models.CharField(max_length=100, verbose_name="Nombre de la Caja", unique=True)
    ruta = models.ForeignKey(Rutas, on_delete=models.SET_NULL, blank=True, null=True, related_name="cajas_ruta", verbose_name="Caja de Ruta")
    sucursal = models.ForeignKey(Sucursal, on_delete=models.SET_NULL, blank=True, null=True, related_name="cajas_sucursal", verbose_name="Ubicación (Sucursal)")
    
    @property
    def folio(self):
        return f"CAJA-{self.pk:06d}"
    
    def save(self, *args, **kwargs):
        self.nombre = (self.nombre or "").strip().upper()
        return super().save(*args, **kwargs)
    
    
    
    def __str__(self):
        return f"Caja: {self.nombre} [{self.sucursal.nombre if self.sucursal else 'Sin Sucursal'}]"
    
class CajaApertura(BaseModel):
    class Meta:
        verbose_name = "Apertura de Caja"
        verbose_name_plural = "Aperturas de Caja"
        ordering = ["-fecha_apertura"]
        
        constraints = [
            ## Solo puede haber UNA caja abierta por caja a la vez
            #models.UniqueConstraint(
            #    fields=['caja'],
            #    condition=models.Q(is_abierta=True, status_model=BaseModel.STATUS_MODEL_ACTIVE),
            #    name='unique_caja_abierta'
            #),
            # Solo puede haber UNA apertura activa por usuario
            models.UniqueConstraint(
                fields=['usuario'],
                condition=models.Q(is_abierta=True, status_model=BaseModel.STATUS_MODEL_ACTIVE),
                name='unique_usuario_apertura_abierta'
            )
        ]
        
    caja = models.ForeignKey(Caja, on_delete=models.CASCADE, related_name="aperturas", verbose_name="Caja")
    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, blank=True, null=True, related_name="aperturas_caja", verbose_name="Usuario que abre la caja")
    monto_inicial = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="Monto Inicial")
    fecha_apertura = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Apertura")
    fecha_cierre = models.DateTimeField(blank=True, null=True, verbose_name="Fecha de Cierre")
    monto_final = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True, verbose_name="Monto Final")
    is_abierta = models.BooleanField(default=True, verbose_name="Caja Abierta")

    @property
    def folio(self):
        return f"AP-CJA-{self.pk:08d}"

    def cerrar_caja(self, monto_final, usuario_cierre):
        self.monto_final = monto_final
        self.updated_by = usuario_cierre
        self.fecha_cierre = timezone.now()
        self.is_abierta = False
        self.save()
    
class CajaTransaccion(BaseModel):
    TIPO_ENTRADA = "ENTRADA"
    TIPO_SALIDA = "SALIDA"
    TIPO_GASTO = "GASTO"
    TIPO_CHOICES = [
        (TIPO_ENTRADA, TIPO_ENTRADA),
        (TIPO_SALIDA, TIPO_SALIDA),
        (TIPO_GASTO, TIPO_GASTO),
    ]
    GASTO_V_XALAPA = "GASTO VIATICO XALAPA"
    GASTO_V_COR = "GASTO VIATICO CORDOBA"
    GASTO_INSUMOS = "GASTO INSUMOS PLASTICOS"
    GASTO_MECANICO = "GASTO MECANICO"
    GASTO_OTRO = "OTRO"
    
    GASTO_TIPO_CHOICES = [
        (GASTO_V_XALAPA, GASTO_V_XALAPA),
        (GASTO_V_COR, GASTO_V_COR),
        (GASTO_INSUMOS, GASTO_INSUMOS),
        (GASTO_MECANICO, GASTO_MECANICO),
        (GASTO_OTRO, GASTO_OTRO),
    ]
    
    referencia = models.CharField(max_length=100, blank=True, null=True, verbose_name="Referencia de la Transacción")
    caja_apertura = models.ForeignKey(CajaApertura, on_delete=models.CASCADE, related_name="transacciones", verbose_name="Apertura de Caja")
    monto = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="Monto")
    metodo_pago = models.ForeignKey(MetodoPago, on_delete=models.SET_NULL, blank=True, null=True, verbose_name="Método de Pago")
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, verbose_name="Tipo de Transacción", default=TIPO_ENTRADA)
    gasto_tipo = models.CharField(max_length=50, blank=True, null=True, verbose_name="Tipo de Gasto", choices=GASTO_TIPO_CHOICES,default="")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    
    
"""
=======================================================================
                        MODELO DE incidencias
=======================================================================
"""

class incidencia(BaseModel):
    
    class Meta:
        verbose_name = "incidencia"
        verbose_name_plural = "incidencias"
    DEFAULT_DESCRIPCION = "Pendiente de descripción"
    descripcion = models.TextField(verbose_name="Descripción de la incidencia")
    solucion = models.TextField(blank=True, null=True, verbose_name="Solución Aplicada")
    resuelta = models.BooleanField(default=False, verbose_name="incidencia Resuelta")
    
    
    def __str__(self):
        return f"incidencia {self.pk} - {'Resuelta' if self.resuelta else 'Pendiente'}"


class IncidenciaLote(BaseModel):
    """
    Modelo intermedio para relacionar incidencias con Lotes de Inventario
    con campos adicionales de control
    """
    class Meta:
        verbose_name = "Lote en incidencia"
        verbose_name_plural = "Lotes en incidencias"
    
    incidencia = models.ForeignKey(
        incidencia, 
        on_delete=models.CASCADE, 
        related_name="lotes_incidencia", 
        verbose_name="incidencia"
    )
    lote = models.ForeignKey(
        'inventario.LoteInventario', 
        on_delete=models.CASCADE, 
        related_name="incidencias_lote", 
        verbose_name="Lote de Inventario"
    )
    cantidad = models.DecimalField(
        max_digits=20, 
        decimal_places=3, 
        default=0, 
        verbose_name="Cantidad Afectada"
    )
    atendida = models.BooleanField(default=False, verbose_name="Atendida")
    fecha_atencion = models.DateTimeField(blank=True, null=True, verbose_name="Fecha de Atención")
    nota = models.TextField(blank=True, null=True, verbose_name="Nota")
    
    def __str__(self):
        return f"incidencia {self.incidencia.pk} - Lote {self.lote.pk} ({'Atendida' if self.atendida else 'Pendiente'})"
