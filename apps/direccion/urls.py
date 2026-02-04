from django.urls import path
from .api.views import DesgloseDireccionAPIView, EstadoListAPIView

urlpatterns = [
    path('desglose-cp/', DesgloseDireccionAPIView.as_view(), name='desglose-cp'),
    path('estados/', EstadoListAPIView.as_view(), name='estado-list'),

]