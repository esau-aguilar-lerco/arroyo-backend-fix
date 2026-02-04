from django.db import models
from django.utils import timezone

from apps.usuarios.models import Usuario
from apps.direccion.models import Estado, Municipio, CodigoPostal, Colonia
class BaseModel(models.Model):

    STATUS_MODEL_ACTIVE = "ACTIVE"
    STATUS_MODEL_INACTIVE = "INACTIVE"
    STATUS_MODEL_DELETE = "DELETE"
    STATUS_CHOICES = [
        (STATUS_MODEL_ACTIVE, "Activo"),
        (STATUS_MODEL_INACTIVE, "Inactivo")
        #,(STATUS_MODEL_DELETE, "Eliminado"),
    ]
    status_model = models.CharField(verbose_name="Estado", max_length=10, choices=STATUS_CHOICES, default=STATUS_MODEL_ACTIVE)

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name='Fecha de creación')
    updated_at = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de actualización')
    created_by = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_%(class)s_set",
    )
    updated_by = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_%(class)s_set",
    )

    class Meta:
        abstract = True
        # ordering = ['-created_at']

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
    
    

    def save(self, *args, **kwargs):
        
        current_time = timezone.now()
        if self._state.adding:
            pass
        else:
            self.updated_at = current_time
            #print("Updated at:", self.updated_at)
        #if self.created_by != None:
        #    self.updated_at = current_time

        super().save(*args, **kwargs)


class BaseDireccion(models.Model):
    estado = models.ForeignKey(Estado, on_delete=models.CASCADE, null=True, blank=True)
    municipio = models.ForeignKey(Municipio, on_delete=models.CASCADE, null=True, blank=True)
    codigo_postal = models.ForeignKey(CodigoPostal, on_delete=models.CASCADE, null=True, blank=True)
    colonia = models.ForeignKey(Colonia, on_delete=models.CASCADE, null=True, blank=True)
    calle = models.CharField(max_length=200, null=True, blank=True)
    numero_exterior = models.CharField(max_length=20, null=True, blank=True)
    numero_interior = models.CharField(max_length=20, null=True, blank=True)
    
    class Meta:
        abstract = True
        # ordering = ['-created_at']

    def save(self, *args, **kwargs):
        self.numero_exterior = self.numero_exterior.upper().strip() if self.numero_exterior else "N/A"
        self.numero_interior = self.numero_interior.upper().strip() if self.numero_interior else "N/A"
        self.calle = self.calle.upper().strip() if self.calle else "N/A"
        super().save(*args, **kwargs)