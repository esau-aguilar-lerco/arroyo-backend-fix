from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

from apps.direccion.models import Estado, Municipio, CodigoPostal, Colonia

class Usuario(AbstractUser):
    
    class Meta:
        verbose_name = 'usuario'
        verbose_name_plural = 'usuarios'
        permissions = [
            ("can_view_user", "VER USUARIO"),
            ("can_update_user", "ACTUALIZAR USUARIO"),
            ("can_create_user", "CREAR USUARIO"),
            ("can_delete_user", "ELIMINAR USUARIO"),
            
        ]

    nombre = models.CharField(max_length=200, null=False, verbose_name='Nombres')
    apellido_paterno = models.CharField(max_length=200, null=True, verbose_name='Apellido Paterno')
    apellido_materno = models.CharField(max_length=200, null=True, verbose_name='Apellido Materno')
    access_to_app = models.BooleanField(default=True, blank=True, verbose_name='Puede acceder a la app', help_text='Si el usuario puede acceder a la aplicación, de lo contrario no podrá iniciar sesión.')
    telefono_1 = models.CharField(max_length=20, null=True, blank=True, verbose_name='Teléfono', help_text='')
    telefono_2 = models.CharField(max_length=20, null=True, blank=True, verbose_name='Teléfono 2', help_text='Teléfono 2')
    almacen = models.ForeignKey('erp.Almacen', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Almacén asignado', help_text='Almacén asignado al usuario')
    sucursal = models.ForeignKey('erp.Sucursal', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Sucursal asignada', help_text='Sucursal asignada al usuario')
    
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name='Fecha de creación')
    updated_at = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de actualización')
    created_by = models.ForeignKey(
        'self', 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL, 
        related_name='usuarios_creados',
        verbose_name='Creado por'
    )
    updated_by = models.ForeignKey(
        'self', 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL, 
        related_name='usuarios_actualizados',
        verbose_name='Actualizado por'
    )
    
    def full_name(self):
        return f"{self.nombre if self.nombre else ''} {self.apellido_paterno if self.apellido_paterno else ''} {self.apellido_materno if self.apellido_materno else ''}"

    def full_name_bread(self):
        return f"{self.nombre if self.nombre else ''} {self.apellido_paterno if self.apellido_paterno else ''} {self.apellido_materno if self.apellido_materno else ''} [{self.id}]"

    def __str__(self):
        return self.username
    

    @property
    def direccion_principal(self):
        return self.direccion_usuario.first()  # si hay varias direcciones
    
    @property
    def get_created_at(self):
        return (
            self.created_at.strftime("%d-%b-%Y %H:%M:%S")
            if self.created_at
            else "N/A"
        )

    @property
    def get_updated_at(self):
        return (
            self.updated_at.strftime("%d-%b-%Y %H:%M:%S")
            if self.updated_at and self.updated_by is not None
            else "N/A"
        )

    @property
    def get_created_by(self):
        return self.created_by.full_name() if self.created_by else "N/A"

    @property
    def get_updated_by(self):
        return self.updated_by.full_name() if self.updated_by else "N/A"
    
    
    def get_mi_caja(self):
        from apps.erp.models import CajaApertura
        return CajaApertura.objects.filter(
            usuario=self,
            is_abierta=True,
            status_model=CajaApertura.STATUS_MODEL_ACTIVE
        ).select_related('caja').first()
        
        
        
    
    
    
    def save(self, *args, **kwargs):
        # Asignar las fechas de creación y actualización
        if not self.created_at:
            self.created_at = timezone.now()
        else:
            self.updated_at = timezone.now()
        super().save(*args, **kwargs)
        

class DireccionUsuario(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='direccion_usuario', verbose_name='Usuario')
    estado = models.ForeignKey(Estado, on_delete=models.CASCADE, null=True, blank=True)
    municipio = models.ForeignKey(Municipio, on_delete=models.CASCADE, null=True, blank=True)
    codigo_postal = models.ForeignKey(CodigoPostal, on_delete=models.CASCADE, null=True, blank=True)
    colonia = models.ForeignKey(Colonia, on_delete=models.CASCADE, null=True, blank=True)
    calle = models.CharField(max_length=200, null=True, blank=True)
    numero_exterior = models.CharField(max_length=20, null=True, blank=True)
    numero_interior = models.CharField(max_length=20, null=True, blank=True)
    

    def save(self, *args, **kwargs):
        self.numero_exterior = self.numero_exterior.upper().strip() if self.numero_exterior else "N/A"
        self.numero_interior = self.numero_interior.upper().strip() if self.numero_interior else "N/A"
        self.calle = self.calle.upper().strip() if self.calle else "N/A"
        super().save(*args, **kwargs)