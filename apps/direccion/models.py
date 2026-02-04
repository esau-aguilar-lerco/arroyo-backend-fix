from django.db import models

# Modelo para los Estados
class Estado(models.Model):
    nombre = models.CharField(max_length=100,db_index=True)
    clave = models.CharField(max_length=5,db_index=True)
    
    class Meta:
        verbose_name_plural = "Estados"
        permissions = [
            ("can_view", "VER estado"),
            ("can_update", "ACTUALIZAR estado"),
        ]

    def __str__(self):
        return self.nombre

# Modelo para los Municipios
class Municipio(models.Model):
    nombre = models.CharField(max_length=100,db_index=True)
    estado = models.ForeignKey(Estado, on_delete=models.CASCADE)

    class Meta:
        indexes = [
            models.Index(fields=['id']),
        ]
        unique_together = ("id",)

    def __str__(self):
        return self.nombre

# Modelo para los Códigos Postales
class CodigoPostal(models.Model):
    codigo_postal = models.CharField(max_length=10, unique=True,db_index=True)
    zona = models.CharField(max_length=50)

    class Meta:
        indexes = [
            models.Index(fields=["codigo_postal", "id"]),
        ]

    def __str__(self):
        return self.codigo_postal

# Modelo para las Colonias
class Colonia(models.Model):
    d_asenta = models.CharField(max_length=100,db_index=True)
    tipo_asentamiento = models.CharField(max_length=50)
    municipio = models.ForeignKey(Municipio, on_delete=models.CASCADE)
    codigo_postal = models.ForeignKey(CodigoPostal, on_delete=models.CASCADE)

    class Meta:
        indexes = [
            models.Index(fields=[ "id"]),
        ]
       # unique_together = ( "municipio", "codigo_postal")

    def __str__(self):
        return self.d_asenta
