from django.contrib import admin

from .models import UnidadSat, RegimenFiscal, MetodoPago

@admin.register(UnidadSat)
class UnidadSatAdmin(admin.ModelAdmin):
    list_display = ("clave", "nombre", "created_at", "updated_at", "status_model")
    search_fields = ("clave", "nombre")

@admin.register(MetodoPago)
class MetodoPagoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "activo",)
    search_fields = ("nombre", "tipo")
   
    ordering = ("nombre",)

@admin.register(RegimenFiscal)
class RegimenFiscalAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "created_at", "updated_at", "status_model")
    search_fields = ("codigo", "nombre")
    list_filter = ("status_model",)
    ordering = ("codigo",)
