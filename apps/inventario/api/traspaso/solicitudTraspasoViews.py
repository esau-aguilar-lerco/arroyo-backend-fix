from django.utils import timezone
from django.db import transaction

from rest_framework.exceptions import ValidationError
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter

from apps.inventario.models import SolicitudTraspaso, SolicitudTraspasoDetalle
from apps.inventario.serializers.traspaso.traspasoSolicitudSerializer import (
    SolicitudTraspasoListSerializer,
    SolicitudTraspasoDetailSerializer,
    SolicitudTraspasoCreateUpdateSerializer,
    AprobarRechazarSolicitudSerializer
)

from django.contrib.auth import get_user_model
from apps.inventario.models import MovimientoInventario, LoteInventario
from apps.inventario.helpers.movimientoSalida import movimento_inventario
from apps.erp.models import Almacen

User = get_user_model()

def get_superuser_almacen():
    superuser = User.objects.filter(
        is_superuser=True,
        almacen__isnull=False
    ).first()
    return superuser.almacen if superuser else None

class SolicitudTraspasoViewSet(viewsets.ModelViewSet):
    """
    ViewSet para el CRUD de solicitudes de traspaso entre almacenes.
    
    Endpoints:
    - GET /solicitudes-traspaso/ - Listar solicitudes
    - POST /solicitudes-traspaso/ - Crear solicitud
    - GET /solicitudes-traspaso/{id}/ - Ver detalle
    - PUT /solicitudes-traspaso/{id}/ - Actualizar solicitud (solo si está PENDIENTE)
    - PATCH /solicitudes-traspaso/{id}/ - Actualizar parcial
    - POST /solicitudes-traspaso/{id}/aprobar/ - Aprobar solicitud
    - POST /solicitudes-traspaso/{id}/rechazar/ - Rechazar solicitud
    """
    permission_classes = [IsAuthenticated]
    queryset = SolicitudTraspaso.objects.all()
    http_method_names = ['get', 'post', 'put', 'patch']  # Excluir DELETE
    
    def get_queryset(self):
        """Filtrar queryset con optimizaciones"""
        queryset = SolicitudTraspaso.objects.select_related(
            'almacen_solicitante',
            'almacen_surtidor',
            'created_by',
            'aprobado_por',
            'rechazado_por',
            'movimiento'
        ).prefetch_related(
            'detalles',
            'detalles__producto',
            'detalles__producto__unidad_sat'
        ).order_by('-created_at')
        
        # Filtros opcionales
        estado = self.request.query_params.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)
        
        almacen_solicitante = self.request.query_params.get('almacen_solicitante')
        if almacen_solicitante:
            queryset = queryset.filter(almacen_solicitante_id=almacen_solicitante)
        
        almacen_surtidor = self.request.query_params.get('almacen_surtidor')
        if almacen_surtidor:
            queryset = queryset.filter(almacen_surtidor_id=almacen_surtidor)
        
        return queryset
    
    def get_serializer_class(self):
        """Retornar serializer según la acción"""
        if self.action == 'list':
            return SolicitudTraspasoListSerializer
        elif self.action == 'retrieve':
            return SolicitudTraspasoDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return SolicitudTraspasoCreateUpdateSerializer
        elif self.action in ['aprobar', 'rechazar']:
            return AprobarRechazarSolicitudSerializer
        return SolicitudTraspasoDetailSerializer
    
    @extend_schema(
        summary="Listar solicitudes de traspaso",
        description="""
        Lista todas las solicitudes de traspaso con información resumida.
        
        **Filtros disponibles:**
        - `estado`: PENDIENTE, APROBADO, RECHAZADO
        - `almacen_solicitante`: ID del almacén solicitante
        - `almacen_surtidor`: ID del almacén surtidor
        
        **Ejemplos:**
        - `?estado=PENDIENTE` - Solo solicitudes pendientes
        - `?almacen_solicitante=5` - Solicitudes del almacén 5
        """,
        parameters=[
            OpenApiParameter(
                name='estado',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Filtrar por estado',
                required=False
            ),
            OpenApiParameter(
                name='almacen_solicitante',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Filtrar por almacén solicitante',
                required=False
            ),
            OpenApiParameter(
                name='almacen_surtidor',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Filtrar por almacén surtidor',
                required=False
            ),
        ],
        tags=['Solicitudes de Traspaso']
    )
    def list(self, request, *args, **kwargs):
        """Listar solicitudes"""
        return super().list(request, *args, **kwargs)
    
    @extend_schema(
        summary="Ver detalle de solicitud",
        description="Obtiene el detalle completo de una solicitud de traspaso incluyendo todos sus productos.",
        tags=['Solicitudes de Traspaso']
    )
    def retrieve(self, request, *args, **kwargs):
        """Ver detalle de una solicitud"""
        return super().retrieve(request, *args, **kwargs)
    
    @extend_schema(
        summary="Crear solicitud de traspaso",
        description="""
        Crea una nueva solicitud de traspaso con sus productos.
        
        **Validaciones:**
        - Almacén solicitante y surtidor deben ser diferentes
        - Debe incluir al menos un producto
        - No puede haber productos duplicados
        - Cantidades deben ser mayores a 0
        
        La solicitud se crea en estado PENDIENTE.
        """,
        tags=['Solicitudes de Traspaso']
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # 🔹 almacen_surtidor: SIEMPRE del frontend
        almacen_surtidor = serializer.validated_data.get('almacen_surtidor')

        if not almacen_surtidor:
            return Response(
                {
                    "success": False,
                    "message": "Debe enviar el almacén surtidor."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # 🔹 almacen_solicitante
        if request.user.is_superuser:
            # Superusuario → frontend
            almacen_solicitante = serializer.validated_data.get('almacen_solicitante')

            if not almacen_solicitante:
                return Response(
                    {
                        "success": False,
                        "message": "Debe enviar el almacén solicitante."
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # Usuario normal → SU almacén
            if not request.user.almacen:
                return Response(
                    {
                        "success": False,
                        "message": "El usuario no tiene un almacén asignado."
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            almacen_solicitante = request.user.almacen

        solicitud = serializer.save(
            created_by=request.user,
            almacen_solicitante=almacen_solicitante,
            almacen_surtidor=almacen_surtidor
        )

        return Response(
            {
                "success": True,
                "message": "Solicitud de traspaso creada exitosamente",
                "data": SolicitudTraspasoDetailSerializer(solicitud).data
            },
            status=status.HTTP_201_CREATED
    )

    
    @extend_schema(
        summary="Actualizar solicitud de traspaso",
        description="""
        Actualiza una solicitud de traspaso completa.
        
        **Importante:**
        - Solo se pueden actualizar solicitudes en estado PENDIENTE
        - Se reemplazan todos los productos por los nuevos proporcionados
        """,
        tags=['Solicitudes de Traspaso']
    )
    def update(self, request, *args, **kwargs):
        """Actualizar solicitud completa"""
        instance = self.get_object()
        
        if instance.estado != SolicitudTraspaso.PENDIENTE:
            return Response(
                {
                    "success": False,
                    "message": f"No se puede modificar una solicitud en estado {instance.estado}"
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(
            {
                "success": True,
                "message": "Solicitud actualizada exitosamente",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )
    
    @extend_schema(
        summary="Actualizar parcialmente solicitud",
        description="Actualiza uno o más campos de la solicitud. Solo disponible para solicitudes PENDIENTES.",
        tags=['Solicitudes de Traspaso']
    )
    def partial_update(self, request, *args, **kwargs):
        """Actualizar parcialmente"""
        instance = self.get_object()
        
        if instance.estado != SolicitudTraspaso.PENDIENTE:
            return Response(
                {
                    "success": False,
                    "message": f"No se puede modificar una solicitud en estado {instance.estado}"
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return super().partial_update(request, *args, **kwargs)
    
    @extend_schema(
        summary="Aprobar solicitud de traspaso",
        description="""
        Aprueba una solicitud de traspaso que está en estado PENDIENTE.
        
        **Proceso:**
        1. Valida que la solicitud esté PENDIENTE
        2. Cambia el estado a APROBADO
        3. Registra quién aprobó y cuándo
        4. El movimiento de inventario se creará posteriormente (por implementar)
        
        **Parámetros opcionales:**
        - `nota`: Justificación de la aprobación
        """,
        request=AprobarRechazarSolicitudSerializer,
        responses={
            200: OpenApiResponse(description='Solicitud aprobada exitosamente'),
            400: OpenApiResponse(description='No se puede aprobar (ya no está PENDIENTE)'),
            404: OpenApiResponse(description='Solicitud no encontrada'),
        },
        tags=['Solicitudes de Traspaso']
    )
    @action(detail=True, methods=['post'], url_path='aprobar')
    def aprobar(self, request, pk=None):
        """
        Aprobar una solicitud de traspaso
        """
        solicitud = self.get_object()
        
        # Validar que esté pendiente
        if solicitud.estado != SolicitudTraspaso.PENDIENTE:
            return Response(
                {
                    "success": False,
                    "message": f"No se puede aprobar una solicitud en estado {solicitud.estado}",
                    "estado_actual": solicitud.estado
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            # Actualizar solicitud
            solicitud.estado = SolicitudTraspaso.APROBADO
            solicitud.aprobado_el = timezone.now()
            solicitud.aprobado_por = request.user
            
            # Agregar nota si se proporcionó
            nota_aprobacion = serializer.validated_data.get('nota', '')
            if nota_aprobacion:
                if solicitud.nota:
                    solicitud.nota += f"\n\n[APROBACIÓN] {nota_aprobacion}"
                else:
                    solicitud.nota = f"[APROBACIÓN] {nota_aprobacion}"

            # ✅ Preparar detalle de lotes (FIFO) para movimiento de traspaso
            detalle_lotes = []

            # Validar que exista almacén virtual de traspaso
            almacen_traspaso = Almacen.objects.filter(
                tipo=Almacen.TIPO_TRASPASO,
                pertence=solicitud.almacen_surtidor
            ).first()
            if not almacen_traspaso:
                raise ValidationError({
                    "success": False,
                    "message": "No existe almacén virtual de traspaso para el almacén surtidor",
                    "errors": {"detail": f"Configure un almacén tipo TRASPASO que pertenezca a {solicitud.almacen_surtidor.nombre}"}
                })

            for det in solicitud.detalles.all():
                # 🔹 LOTE ORIGEN (surtidor)
                cantidad_restante = det.cantidad

                lotes = LoteInventario.objects.select_for_update().filter(
                    producto=det.producto,
                    almacen=solicitud.almacen_surtidor,
                    cantidad__gt=0,
                    status_model=LoteInventario.STATUS_MODEL_ACTIVE
                ).order_by('created_at')

                lotes_asignados = []

                for lote in lotes:
                    if cantidad_restante <= 0:
                        break
                    tomar = min(lote.cantidad, cantidad_restante)
                    lotes_asignados.append({
                        'lote': lote,
                        'cantidad': tomar
                    })
                    cantidad_restante -= tomar

                if cantidad_restante > 0:
                    raise ValidationError({
                        "success": False,
                        "message": "No hay suficiente inventario para surtir la solicitud",
                        "errors": {"detail": f"No hay suficiente inventario total del siguiente producto: {det.producto.nombre}"}
                    })

                detalle_lotes.append({
                    'producto': det.producto,
                    'cantidad': det.cantidad,
                    'lotes': lotes_asignados
                })

            # ✅ Crear movimiento de traspaso (salida + virtual)
            movimiento = movimento_inventario(
                detalle_lotes=detalle_lotes,
                almacen_salida=solicitud.almacen_surtidor,
                almacen_destino=solicitud.almacen_solicitante,
                movimiento=MovimientoInventario.TIPO_SALIDA,
                sub_movimiento=MovimientoInventario.SALIDA_TRASPASO,
                nota=f"TRASPASO SOLICITUD {solicitud.id}",
                user=request.user
            )
            # guardar relación
            solicitud.movimiento = movimiento
            solicitud.save()

            # movimiento = crear_movimiento_traspaso(solicitud)
            # solicitud.movimiento = movimiento
            # solicitud.save()
        
        return Response(
            {
                "success": True,
                "message": "Solicitud aprobada exitosamente",
                "data": SolicitudTraspasoDetailSerializer(solicitud).data
            },
            status=status.HTTP_200_OK
        )
    
    @extend_schema(
        summary="Rechazar solicitud de traspaso",
        description="""
        Rechaza una solicitud de traspaso que está en estado PENDIENTE.
        
        **Proceso:**
        1. Valida que la solicitud esté PENDIENTE
        2. Cambia el estado a RECHAZADO
        3. Registra quién rechazó y cuándo
        
        **Parámetros opcionales:**
        - `nota`: Justificación del rechazo
        """,
        request=AprobarRechazarSolicitudSerializer,
        responses={
            200: OpenApiResponse(description='Solicitud rechazada exitosamente'),
            400: OpenApiResponse(description='No se puede rechazar (ya no está PENDIENTE)'),
            404: OpenApiResponse(description='Solicitud no encontrada'),
        },
        tags=['Solicitudes de Traspaso']
    )
    @action(detail=True, methods=['post'], url_path='rechazar')
    def rechazar(self, request, pk=None):
        """
        Rechazar una solicitud de traspaso
        """
        solicitud = self.get_object()
        
        # Validar que esté pendiente
        if solicitud.estado != SolicitudTraspaso.PENDIENTE:
            return Response(
                {
                    "success": False,
                    "message": f"No se puede rechazar una solicitud en estado {solicitud.estado}",
                    "estado_actual": solicitud.estado
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            solicitud.estado = SolicitudTraspaso.RECHAZADO
            solicitud.rechazado_el = timezone.now()
            solicitud.rechazado_por = request.user

            nota_rechazo = serializer.validated_data.get('nota', '')
            if nota_rechazo:
                if solicitud.nota:
                    solicitud.nota += f"\n\n[RECHAZO] {nota_rechazo}"
                else:
                    solicitud.nota = f"[RECHAZO] {nota_rechazo}"

            solicitud.save()

        
        return Response(
            {
                "success": True,
                "message": "Solicitud rechazada exitosamente",
                "data": SolicitudTraspasoDetailSerializer(solicitud).data
            },
            status=status.HTTP_200_OK
        )
