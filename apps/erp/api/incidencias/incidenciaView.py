from rest_framework import status, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.pagination import LimitOffsetPagination
from django.db import transaction
from django.db.models import Q, Prefetch
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP

from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from apps.base.models import BaseModel
from apps.erp.models import incidencia as IncidenciaModel, IncidenciaLote, Almacen
from apps.inventario.models import MovimientoInventario, ProductosMovimiento, LoteInventario
from apps.erp.serializers.incidencias.incidenciaSerializer import (
    IncidenciaMiniSerializer,
    IncidenciaDetailSerializer,
    AtenderIncidenciaLoteSerializer,
)

QTY_3 = Decimal("0.001")


def _q3(value):
    if value is None:
        return Decimal("0.000")
    if isinstance(value, Decimal):
        return value.quantize(QTY_3, rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(QTY_3, rounding=ROUND_HALF_UP)


def _resolver_almacen_destino(incidencia_lote, accion, almacen_destino_id, user):
    lote = incidencia_lote.lote

    if accion not in {"REASIGNACION", "RETORNO_ALMACEN"}:
        return None

    if almacen_destino_id:
        destino = Almacen.objects.filter(
            id=almacen_destino_id,
            status_model=BaseModel.STATUS_MODEL_ACTIVE
        ).first()
        if not destino:
            raise ValueError(f"El almacén destino {almacen_destino_id} no existe o está inactivo.")
        return destino

    if accion == "RETORNO_ALMACEN":
        concentrado = Almacen.objects.filter(
            nombre__iexact="CONCENTRADO DE RUTAS",
            status_model=BaseModel.STATUS_MODEL_ACTIVE
        ).first()
        if concentrado:
            return concentrado
        raise ValueError("No existe almacén 'CONCENTRADO DE RUTAS' para RETORNO_ALMACEN.")

    # REASIGNACION sin destino explícito: usar almacén del usuario operativo.
    almacen_usuario = getattr(user, 'almacen', None)
    if almacen_usuario and almacen_usuario.id != lote.almacen_id:
        return almacen_usuario

    raise ValueError(
        "Para acción REASIGNACION debes enviar almacen_destino_id o usar un usuario con almacén asignado."
    )


def _mover_lote_por_resolucion(incidencia_lote, almacen_destino, user, accion):
    lote_origen = incidencia_lote.lote
    lote_origen.refresh_from_db()

    if not lote_origen.almacen:
        raise ValueError(f"El lote {lote_origen.id} no tiene almacén origen.")

    if lote_origen.almacen_id == almacen_destino.id:
        return None

    cantidad = _q3(incidencia_lote.cantidad)
    if cantidad <= 0:
        raise ValueError(f"La cantidad de incidencia para lote {lote_origen.id} debe ser mayor a 0.")

    if _q3(lote_origen.cantidad) < cantidad:
        raise ValueError(
            f"No hay suficiente inventario en lote {lote_origen.id} para mover {cantidad}. "
            f"Disponible: {_q3(lote_origen.cantidad)}."
        )

    referencia = f"INC-{accion}-L{lote_origen.id}-I{incidencia_lote.id}"
    nota = f"Movimiento por atención de incidencia #{incidencia_lote.incidencia_id} ({accion})"

    mov_salida = MovimientoInventario.objects.create(
        almacen=lote_origen.almacen,
        almacen_destino=almacen_destino,
        tipo=MovimientoInventario.TIPO_SALIDA,
        movimiento=MovimientoInventario.SALIDA_TRASPASO,
        cantidad=cantidad,
        referencia=f"{referencia}-SAL",
        nota=nota,
        detalle_nota=f"SALIDA {lote_origen.almacen.nombre} -> {almacen_destino.nombre}",
        fase=MovimientoInventario.FASE_TERMINADA,
        created_by=user,
        updated_by=user,
    )

    ProductosMovimiento.objects.create(
        movimiento=mov_salida,
        producto=lote_origen.producto,
        lote=lote_origen,
        cantidad=cantidad,
        costo_unitario=lote_origen.costo_unitario,
        created_by=user,
        updated_by=user,
    )

    lote_destino = LoteInventario.objects.create(
        lote_herencia=lote_origen,
        producto=lote_origen.producto,
        almacen=almacen_destino,
        cantidad=Decimal("0.000"),
        costo_unitario=lote_origen.costo_unitario,
        fecha_ingreso=timezone.now(),
        fecha_vencimiento=lote_origen.fecha_vencimiento,
        created_by=user,
        updated_by=user,
    )

    mov_entrada = MovimientoInventario.objects.create(
        almacen=almacen_destino,
        almacen_destino=almacen_destino,
        tipo=MovimientoInventario.TIPO_ENTRADA,
        movimiento=MovimientoInventario.ENTRADA_TRASPASO,
        cantidad=cantidad,
        referencia=f"{referencia}-ENT",
        nota=nota,
        detalle_nota=f"ENTRADA {almacen_destino.nombre}",
        fase=MovimientoInventario.FASE_TERMINADA,
        created_by=user,
        updated_by=user,
    )

    ProductosMovimiento.objects.create(
        movimiento=mov_entrada,
        producto=lote_destino.producto,
        lote=lote_destino,
        cantidad=cantidad,
        costo_unitario=lote_destino.costo_unitario,
        created_by=user,
        updated_by=user,
    )

    return {
        'incidencia_lote_id': incidencia_lote.id,
        'accion': accion,
        'almacen_origen_id': lote_origen.almacen_id,
        'almacen_destino_id': almacen_destino.id,
        'movimiento_salida_id': mov_salida.id,
        'movimiento_entrada_id': mov_entrada.id,
    }


class IncidenciaListRetrieveAPIView(APIView):
    """
    Vista para listar y obtener detalle de incidencias
    """
    
    @extend_schema(
        summary="Listar incidencias",
        description="Obtiene el listado de incidencias con paginación y filtros",
        parameters=[
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Buscar por descripción',
                required=False
            ),
            OpenApiParameter(
                name='resuelta',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='Filtrar por estado resuelta (true/false)',
                required=False
            ),
        ],
        responses={
            200: IncidenciaMiniSerializer(many=True),
        },
        tags=['incidencias']
    )
    def get(self, request, pk=None):
        """
        Lista todas las incidencias o detalle si se proporciona pk
        """
        if pk:
            return self.retrieve(request, pk)
        
        queryset = IncidenciaModel.objects.filter(
            status_model=BaseModel.STATUS_MODEL_ACTIVE
        ).prefetch_related('lotes_incidencia').order_by('-created_at')
        
        # Filtro por búsqueda
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(descripcion__icontains=search)
            )
        
        # Filtro por resuelta
        resuelta = request.query_params.get('resuelta')
        if resuelta is not None:
            resuelta_bool = resuelta.lower() == 'true'
            queryset = queryset.filter(resuelta=resuelta_bool)
        
        # Paginación
        paginator = LimitOffsetPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = IncidenciaMiniSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = IncidenciaMiniSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @extend_schema(
        summary="Obtener detalle de incidencia",
        description="Obtiene el detalle completo de una incidencia con sus lotes y productos",
        responses={
            200: IncidenciaDetailSerializer,
            404: "incidencia no encontrada"
        },
        tags=['incidencias']
    )
    def retrieve(self, request, pk):
        """
        Obtiene el detalle completo de una incidencia
        """
        try:
            incidencia = IncidenciaModel.objects.select_related(
                'created_by'
            ).prefetch_related(
                Prefetch(
                    'lotes_incidencia',
                    queryset=IncidenciaLote.objects.select_related(
                        'lote__producto',
                        'lote__almacen'
                    )
                )
            ).get(pk=pk, status_model=BaseModel.STATUS_MODEL_ACTIVE)
            
            serializer = IncidenciaDetailSerializer(incidencia)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except IncidenciaModel.DoesNotExist:
            return Response(
                {'detail': 'incidencia no encontrada.'},
                status=status.HTTP_404_NOT_FOUND
            )


@extend_schema(
    summary="Atender lotes de incidencia",
    description="Marca múltiples lotes de una incidencia como atendidos",
    request=AtenderIncidenciaLoteSerializer,
    responses={
        200: inline_serializer(
            name='AtenderIncidenciaLoteResponse',
            fields={
                'success': serializers.BooleanField(),
                'message': serializers.CharField(),
                'lotes_atendidos': serializers.IntegerField(),
                'incidencias_resueltas': serializers.ListField(child=serializers.IntegerField()),
                'movimientos_generados': serializers.ListField(
                    child=serializers.DictField(),
                    required=False
                ),
            }
        ),
        400: "Error en los datos proporcionados",
        404: "Lote de incidencia no encontrado"
    },
    tags=['incidencias']
)
@api_view(['POST'])
def atender_incidencia_lote(request):
    """
    Atiende múltiples lotes de incidencias
    """
    serializer = AtenderIncidenciaLoteSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {'detail': 'Datos inválidos', 'errors': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            lotes_data = serializer.validated_data['lotes']
            lotes_atendidos = []
            incidencias_a_verificar = set()
            movimientos_generados = []
            
            for item in lotes_data:
                incidencia_lote_id = item['incidencia_lote_id']
                tipificacion = item.get('tipificacion', '').strip()
                nota = item.get('nota', '')
                accion = (item.get('accion') or '').strip().upper()
                almacen_destino_id = item.get('almacen_destino_id')
                
                try:
                    incidencia_lote = IncidenciaLote.objects.select_related(
                        'incidencia',
                        'lote__almacen',
                        'lote__producto',
                    ).get(pk=incidencia_lote_id, status_model=BaseModel.STATUS_MODEL_ACTIVE)
                except IncidenciaLote.DoesNotExist:
                    return Response(
                        {'detail': f'Lote de incidencia con ID {incidencia_lote_id} no encontrado.'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                if incidencia_lote.atendida:
                    continue  # Saltar lotes ya atendidos

                if not tipificacion:
                    return Response(
                        {'detail': f'Tipificacion requerida para atender el lote {incidencia_lote_id}.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                incidencia = incidencia_lote.incidencia
                if (
                    not incidencia.descripcion
                    or not incidencia.descripcion.strip()
                    or incidencia.descripcion.strip() == IncidenciaModel.DEFAULT_DESCRIPCION
                ):
                    incidencia.descripcion = tipificacion
                    incidencia.save(update_fields=['descripcion'])
                else:
                    # Cuando la incidencia tiene descripcion de negocio
                    # (ej. excedente/faltante de compra), no debe bloquearse
                    # la atencion del lote por una tipificacion distinta.
                    tipificacion_linea = f"Lote #{incidencia_lote.lote_id}: {tipificacion}"
                    solucion_actual = (incidencia.solucion or "").strip()
                    if tipificacion_linea not in solucion_actual:
                        incidencia.solucion = (
                            f"{solucion_actual}\n{tipificacion_linea}".strip()
                            if solucion_actual
                            else tipificacion_linea
                        )
                        incidencia.save(update_fields=['solucion'])
                
                movimiento = None
                if accion:
                    almacen_destino = _resolver_almacen_destino(
                        incidencia_lote=incidencia_lote,
                        accion=accion,
                        almacen_destino_id=almacen_destino_id,
                        user=request.user,
                    )
                    movimiento = _mover_lote_por_resolucion(
                        incidencia_lote=incidencia_lote,
                        almacen_destino=almacen_destino,
                        user=request.user,
                        accion=accion,
                    )

                    linea_estado = (
                        f"Lote #{incidencia_lote.lote_id}: {accion} -> "
                        f"{almacen_destino.nombre} (cant={incidencia_lote.cantidad})"
                    )
                    solucion_actual = (incidencia.solucion or "").strip()
                    if linea_estado not in solucion_actual:
                        incidencia.solucion = (
                            f"{solucion_actual}\n{linea_estado}".strip()
                            if solucion_actual
                            else linea_estado
                        )
                        incidencia.save(update_fields=['solucion'])

                # Marcar como atendido
                incidencia_lote.atendida = True
                incidencia_lote.fecha_atencion = timezone.now()
                if nota:
                    incidencia_lote.nota = nota
                elif accion:
                    incidencia_lote.nota = f"Acción aplicada: {accion}"
                incidencia_lote.save()
                
                lotes_atendidos.append(incidencia_lote.id)
                incidencias_a_verificar.add(incidencia_lote.incidencia_id)
                if movimiento:
                    movimientos_generados.append(movimiento)
            
            # Verificar si las incidencias están completamente resueltas
            incidencias_resueltas = []
            for incidencia_id in incidencias_a_verificar:
                incidencia_obj = IncidenciaModel.objects.get(pk=incidencia_id)
                lotes_pendientes = incidencia_obj.lotes_incidencia.filter(atendida=False).exists()
                
                if not lotes_pendientes and not incidencia_obj.resuelta:
                    incidencia_obj.resuelta = True
                    incidencia_obj.save()
                    incidencias_resueltas.append(incidencia_id)
            
            return Response({
                'success': True,
                'message': f'{len(lotes_atendidos)} lote(s) atendido(s) correctamente',
                'lotes_atendidos': len(lotes_atendidos),
                'lotes_ids': lotes_atendidos,
                'incidencias_resueltas': incidencias_resueltas,
                'movimientos_generados': movimientos_generados,
            }, status=status.HTTP_200_OK)
            
    except Exception as e:
        return Response(
            {'detail': f'Error al atender lotes: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
