from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims
        token['name'] = f'{user.full_name()}'
        token['email'] = user.email
        token['is_superuser'] = user.is_superuser
        token['caja_abierta'] = True if  user.get_mi_caja() is not None else False
        #token['permissions'] = list(user.get_all_permissions())
        return token