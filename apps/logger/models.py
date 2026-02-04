# apps/logging/models.py
from django.db import models
from django.conf import settings

# Para Django >= 3.1 use models.JSONField, si usas Postgres antiguo usa from django.contrib.postgres.fields import JSONField
try:
    JSONField = models.JSONField
except AttributeError:
    from django.contrib.postgres.fields import JSONField  # fallback

class RequestLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    method = models.CharField(max_length=10)
    path = models.TextField()               # full path (path + querystring si lo quieres)
    query_string = models.TextField(blank=True, null=True)
    remote_addr = models.CharField(max_length=100, blank=True, null=True)
    headers = JSONField(blank=True, null=True)
    body = models.TextField(blank=True, null=True)
    content_type = models.CharField(max_length=200, blank=True, null=True)
    status_code = models.PositiveIntegerField(blank=True, null=True)
    response_time_ms = models.IntegerField(blank=True, null=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.timestamp} {self.method} {self.path}"
