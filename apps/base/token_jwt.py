from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from apps.erp.models import Rutas

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        ruta_asignada = (
            Rutas.objects
            .filter(asignado=user, status_model='ACTIVE')
            .order_by('-id')
            .first()
        )
        # Add custom claims
        token['name'] = f'{user.full_name()}'
        token['email'] = user.email
        token['is_superuser'] = user.is_superuser
        token['caja_abierta'] = True if  user.get_mi_caja() is not None else False
        token['ruta_asignada_id'] = ruta_asignada.id if ruta_asignada else None
        token['ruta_asignada_codigo'] = ruta_asignada.codigo if ruta_asignada else None
        token['ruta_asignada_nombre'] = ruta_asignada.nombre if ruta_asignada else None
        #token['permissions'] = list(user.get_all_permissions())
        return token
