from rest_framework import status, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.pagination import LimitOffsetPagination
from django.db import transaction
from django.db.models import Q, Prefetch
from django.utils import timezone

from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from apps.base.models import BaseModel
from apps.erp.models import incidencia as IncidenciaModel, IncidenciaLote
from apps.erp.serializers.incidencias.incidenciaSerializer import (
    IncidenciaMiniSerializer,
    IncidenciaDetailSerializer,
    AtenderIncidenciaLoteSerializer,
)


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
            
            for item in lotes_data:
                incidencia_lote_id = item['incidencia_lote_id']
                tipificacion = item.get('tipificacion', '').strip()
                nota = item.get('nota', '')
                
                try:
                    incidencia_lote = IncidenciaLote.objects.select_related(
                        'incidencia'
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
                
                # Marcar como atendido
                incidencia_lote.atendida = True
                incidencia_lote.fecha_atencion = timezone.now()
                if nota:
                    incidencia_lote.nota = nota
                incidencia_lote.save()
                
                lotes_atendidos.append(incidencia_lote.id)
                incidencias_a_verificar.add(incidencia_lote.incidencia_id)
            
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
            }, status=status.HTTP_200_OK)
            
    except Exception as e:
        return Response(
            {'detail': f'Error al atender lotes: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
