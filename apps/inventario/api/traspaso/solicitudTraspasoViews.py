from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone
from django.db import transaction

from rest_framework.exceptions import ValidationError
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter

from apps.inventario.models import (
    SolicitudTraspaso,
    ProductosSolicitud,
)
from apps.inventario.serializers.traspaso.traspasoSolicitudSerializer import (
    SolicitudTraspasoListSerializer,
    SolicitudTraspasoDetailSerializer,
    SolicitudTraspasoCreateUpdateSerializer,
    AprobarRechazarSolicitudSerializer
)

from django.contrib.auth import get_user_model
from apps.inventario.models import MovimientoInventario, LoteInventario, ProductosMovimiento

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

    @staticmethod
    def _q3(valor):
        return Decimal(str(valor)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)

    def _resolver_abastecidas(self, solicitud, detalles_payload):
        """
        Devuelve un dict {detalle_id: cantidad_abastecida} con fallback a cantidad solicitada.
        Soporta identificar por detalle_id o producto.
        """
        detalles_qs = solicitud.detalles.select_related('producto').all()
        detalles_ids_validos = {d.id for d in detalles_qs}
        productos_ids_validos = {d.producto_id for d in detalles_qs if d.producto_id}

        por_detalle = {}
        por_producto = {}
        for item in (detalles_payload or []):
            cantidad = self._q3(item.get('cantidad_abastecida', 0))
            if item.get('detalle_id') is not None:
                detalle_id = int(item['detalle_id'])
                if detalle_id not in detalles_ids_validos:
                    raise ValidationError({
                        "success": False,
                        "message": "Detalle de solicitud inválido para esta operación",
                        "errors": {
                            "detail": (
                                f"El detalle_id={detalle_id} no pertenece a la solicitud {solicitud.id}."
                            )
                        }
                    })
                por_detalle[detalle_id] = cantidad
            elif item.get('producto') is not None:
                producto_id = int(item['producto'])
                if producto_id not in productos_ids_validos:
                    raise ValidationError({
                        "success": False,
                        "message": "Producto inválido para esta solicitud",
                        "errors": {
                            "detail": (
                                f"El producto={producto_id} no pertenece a la solicitud {solicitud.id}."
                            )
                        }
                    })
                por_producto[producto_id] = cantidad

        resultado = {}
        for det in detalles_qs:
            if det.id in por_detalle:
                resultado[det.id] = por_detalle[det.id]
            elif det.producto_id in por_producto:
                resultado[det.id] = por_producto[det.producto_id]
            else:
                resultado[det.id] = self._q3(det.cantidad)
        return resultado

    def _crear_solicitudes_compra(self, solicitud, faltantes, user):
        """
        Genera solicitudes de compra (ProductosSolicitud) para cantidades faltantes.
        faltantes: list[{'producto': Producto, 'cantidad': Decimal}]
        """
        creadas = []
        creador = solicitud.created_by or user
        for item in faltantes:
            cantidad = self._q3(item['cantidad'])
            if cantidad <= 0:
                continue
            model = ProductosSolicitud.objects.create(
                almacen=solicitud.almacen_solicitante,
                producto=item['producto'],
                cantidad=cantidad,
                motivo=ProductosSolicitud.MOTIVO_BAJA,
                fase=ProductosSolicitud.SOLICITUD,
                created_by=creador,
                updated_by=user,
            )
            creadas.append(model)
        return creadas

    def _crear_movimientos_traspaso(self, solicitud, lotes_asignados, user):
        """
        Crea y aplica movimientos de salida (surtidor) y entrada (solicitante)
        afectando inventario en ambos almacenes.
        """
        total = Decimal('0.000')
        for item in lotes_asignados:
            total += self._q3(item['cantidad'])

        if total <= 0:
            return None, None

        movimiento_salida = MovimientoInventario.objects.create(
            almacen=solicitud.almacen_surtidor,
            almacen_destino=solicitud.almacen_solicitante,
            tipo=MovimientoInventario.TIPO_SALIDA,
            movimiento=MovimientoInventario.SALIDA_TRASPASO,
            cantidad=total,
            referencia=f"TRASP-SALIDA-SOL-{solicitud.id}",
            nota=f"Salida por aprobación de solicitud #{solicitud.id}",
            detalle_nota=(
                f"SALIDA DE {solicitud.almacen_surtidor.nombre} "
                f"A {solicitud.almacen_solicitante.nombre}"
            ),
            fase=MovimientoInventario.FASE_TERMINADA,
            created_by=user,
            updated_by=user,
        )
        movimiento_entrada = MovimientoInventario.objects.create(
            almacen=solicitud.almacen_solicitante,
            almacen_destino=solicitud.almacen_solicitante,
            tipo=MovimientoInventario.TIPO_ENTRADA,
            movimiento=MovimientoInventario.ENTRADA_TRASPASO,
            cantidad=total,
            referencia=f"TRASP-ENTRADA-SOL-{solicitud.id}",
            nota=f"Entrada por aprobación de solicitud #{solicitud.id}",
            detalle_nota=(
                f"ENTRADA EN {solicitud.almacen_solicitante.nombre} "
                f"DESDE {solicitud.almacen_surtidor.nombre}"
            ),
            fase=MovimientoInventario.FASE_TERMINADA,
            created_by=user,
            updated_by=user,
        )

        for item in lotes_asignados:
            producto = item['producto']
            lote_origen = item['lote']
            cantidad = self._q3(item['cantidad'])

            # salida: resta del surtidor
            ProductosMovimiento.objects.create(
                movimiento=movimiento_salida,
                producto=producto,
                lote=lote_origen,
                cantidad=cantidad,
                costo_unitario=lote_origen.costo_unitario,
                created_by=user,
                updated_by=user,
            )

            # entrada: suma al solicitante en un lote nuevo por trazabilidad
            lote_destino = LoteInventario.objects.create(
                referencia=f"TRASP-SOL-{solicitud.id}-ORIG-{lote_origen.id}",
                lote_herencia=lote_origen,
                producto=producto,
                almacen=solicitud.almacen_solicitante,
                cantidad=Decimal('0.000'),
                costo_unitario=lote_origen.costo_unitario,
                fecha_vencimiento=lote_origen.fecha_vencimiento,
                created_by=user,
                updated_by=user,
            )
            ProductosMovimiento.objects.create(
                movimiento=movimiento_entrada,
                producto=producto,
                lote=lote_destino,
                cantidad=cantidad,
                costo_unitario=lote_destino.costo_unitario,
                created_by=user,
                updated_by=user,
            )

        return movimiento_salida, movimiento_entrada
    
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
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            solicitud = (
                SolicitudTraspaso.objects
                .select_for_update()
                .get(pk=pk)
            )
            detalles_solicitud = list(
                solicitud.detalles.select_related('producto').all()
            )

            # Idempotencia por estado final
            if solicitud.estado == SolicitudTraspaso.APROBADO:
                response_data = SolicitudTraspasoDetailSerializer(solicitud).data
                response_data['idempotent_replay'] = True
                return Response(
                    {
                        "success": True,
                        "message": "Solicitud ya estaba aprobada",
                        "data": response_data
                    },
                    status=status.HTTP_200_OK
                )

            if solicitud.estado == SolicitudTraspaso.RECHAZADO:
                return Response(
                    {
                        "success": False,
                        "message": "No se puede aprobar una solicitud ya rechazada",
                        "estado_actual": solicitud.estado
                    },
                    status=status.HTTP_409_CONFLICT
                )

            cantidades_abastecidas = self._resolver_abastecidas(
                solicitud=solicitud,
                detalles_payload=serializer.validated_data.get('detalles', [])
            )

            faltantes = []
            lotes_asignados = []
            resumen_detalles = []
            for det in detalles_solicitud:
                cantidad_solicitada = self._q3(det.cantidad)
                cantidad_abastecida = self._q3(cantidades_abastecidas.get(det.id, cantidad_solicitada))

                if cantidad_abastecida > 0:
                    cantidad_restante = cantidad_abastecida
                    lotes = (
                        LoteInventario.objects
                        .select_for_update()
                        .filter(
                            producto=det.producto,
                            almacen=solicitud.almacen_surtidor,
                            cantidad__gt=0,
                            status_model=LoteInventario.STATUS_MODEL_ACTIVE
                        )
                        .order_by('created_at', 'id')
                    )

                    for lote in lotes:
                        if cantidad_restante <= 0:
                            break
                        tomar = min(self._q3(lote.cantidad), cantidad_restante)
                        if tomar <= 0:
                            continue

                        lotes_asignados.append({
                            'producto': det.producto,
                            'lote': lote,
                            'cantidad': tomar,
                        })
                        cantidad_restante = self._q3(cantidad_restante - tomar)

                    if cantidad_restante > 0:
                        raise ValidationError({
                            "success": False,
                            "message": "No hay suficiente inventario para surtir la solicitud",
                            "errors": {
                                "detail": (
                                    f"Producto {det.producto.codigo} sin stock suficiente. "
                                    f"Solicitado para abastecer: {cantidad_abastecida}, "
                                    f"faltante en surtidor: {cantidad_restante}"
                                )
                            }
                        })

                faltante = Decimal('0.000')
                if cantidad_abastecida < cantidad_solicitada:
                    faltante = self._q3(cantidad_solicitada - cantidad_abastecida)
                    faltantes.append({
                        'producto': det.producto,
                        'cantidad': faltante,
                    })

                resumen_detalles.append({
                    "detalle_id": det.id,
                    "producto_id": det.producto_id,
                    "producto_codigo": det.producto.codigo if det.producto else "",
                    "cantidad_solicitada": float(cantidad_solicitada),
                    "cantidad_abastecida": float(cantidad_abastecida),
                    "cantidad_faltante": float(faltante),
                })

            movimiento_salida, movimiento_entrada = self._crear_movimientos_traspaso(
                solicitud=solicitud,
                lotes_asignados=lotes_asignados,
                user=request.user,
            )

            solicitudes_compra = self._crear_solicitudes_compra(
                solicitud=solicitud,
                faltantes=faltantes,
                user=request.user,
            )

            # Actualizar solicitud
            solicitud.estado = SolicitudTraspaso.APROBADO
            solicitud.aprobado_el = timezone.now()
            solicitud.aprobado_por = request.user
            solicitud.movimiento = movimiento_salida
            
            # Agregar nota si se proporcionó
            nota_aprobacion = serializer.validated_data.get('nota', '')
            if nota_aprobacion:
                if solicitud.nota:
                    solicitud.nota += f"\n\n[APROBACIÓN] {nota_aprobacion}"
                else:
                    solicitud.nota = f"[APROBACIÓN] {nota_aprobacion}"

            solicitud.save()

        data = SolicitudTraspasoDetailSerializer(solicitud).data
        data['movimientos'] = {
            "salida_id": movimiento_salida.id if movimiento_salida else None,
            "entrada_id": movimiento_entrada.id if movimiento_entrada else None,
        }
        data['resumen_abastecimiento'] = resumen_detalles
        data['solicitudes_compra_generadas'] = [
            {
                "id": s.id,
                "producto_id": s.producto_id,
                "producto_codigo": s.producto.codigo if s.producto else "",
                "cantidad": float(s.cantidad),
            }
            for s in solicitudes_compra
        ]

        return Response(
            {
                "success": True,
                "message": "Solicitud aprobada exitosamente",
                "data": data
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
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            solicitud = (
                SolicitudTraspaso.objects
                .select_for_update()
                .get(pk=pk)
            )
            detalles_solicitud = list(
                solicitud.detalles.select_related('producto').all()
            )

            # Idempotencia por estado final
            if solicitud.estado == SolicitudTraspaso.RECHAZADO:
                response_data = SolicitudTraspasoDetailSerializer(solicitud).data
                response_data['idempotent_replay'] = True
                return Response(
                    {
                        "success": True,
                        "message": "Solicitud ya estaba rechazada",
                        "data": response_data
                    },
                    status=status.HTTP_200_OK
                )
            if solicitud.estado == SolicitudTraspaso.APROBADO:
                return Response(
                    {
                        "success": False,
                        "message": "No se puede rechazar una solicitud ya aprobada",
                        "estado_actual": solicitud.estado
                    },
                    status=status.HTTP_409_CONFLICT
                )

            solicitudes_compra = self._crear_solicitudes_compra(
                solicitud=solicitud,
                faltantes=[
                    {'producto': d.producto, 'cantidad': self._q3(d.cantidad)}
                    for d in detalles_solicitud
                ],
                user=request.user,
            )

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

        data = SolicitudTraspasoDetailSerializer(solicitud).data
        data['solicitudes_compra_generadas'] = [
            {
                "id": s.id,
                "producto_id": s.producto_id,
                "producto_codigo": s.producto.codigo if s.producto else "",
                "cantidad": float(s.cantidad),
            }
            for s in solicitudes_compra
        ]

        return Response(
            {
                "success": True,
                "message": "Solicitud rechazada exitosamente",
                "data": data
            },
            status=status.HTTP_200_OK
        )
