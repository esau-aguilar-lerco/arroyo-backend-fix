from django.http import JsonResponse
from django.shortcuts import render

def root_view(request):
    return render(request, "index.html", {
        "api_base": "/api/",
        "endpoints": [
            {"name": "Dirección", "url": "/api/direccion/"},
            {"name": "Usuarios", "url": "/api/usuarios/"},
            {"name": "Crédito", "url": "/api/credito/"},
            {"name": "ERP", "url": "/api/erp/"},
            {"name": "Inventario", "url": "/api/inventario/"},
            {"name": "Contabilidad", "url": "/api/contabilidad/"},
        ],
        "docs": {
            "swagger": "/api/docs/",
            "redoc": "/api/redoc/",
            "schema": "/api/schema/",
        }
    })
