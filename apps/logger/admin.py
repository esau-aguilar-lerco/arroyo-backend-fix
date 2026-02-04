# apps/logging/admin.py
from django.contrib import admin
from .models import RequestLog

from django.contrib import admin
from .models import RequestLog

@admin.register(RequestLog)
class RequestLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "method", "path", "remote_addr", "status_code", "response_time_ms", "user")
    list_filter = ("method", "status_code", "user", "remote_addr")
    search_fields = ("path", "body", "headers", "remote_addr")
    readonly_fields = [f.name for f in RequestLog._meta.fields]

    # 🔹 Mostrar solo 20 registros por página
    list_per_page = 20

    # 🔹 No permitir “Mostrar todos” (Show all)
    list_max_show_all = 20

    # 🔹 Evitar conteo total (para más velocidad)
    show_full_result_count = False
