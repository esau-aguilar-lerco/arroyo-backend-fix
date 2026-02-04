
from django.contrib import admin
from .models import Estado

@admin.register(Estado)
class EstadoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "clave")
    search_fields = ("nombre", "clave")
    ordering = ("nombre",)



# Register your models here.
