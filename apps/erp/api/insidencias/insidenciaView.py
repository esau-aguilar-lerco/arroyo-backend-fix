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
from apps.erp.models import Insidencia, InsidenciaLote
from apps.erp.serializers.insidencias.insidenciaSerializer import (
    InsidenciaMiniSerializer,
    InsidenciaDetailSerializer,
    AtenderInsidenciaLoteSerializer,
)


class InsidenciaListRetrieveAPIView(APIView):
    """
    Vista para listar y obtener detalle de insidencias
    """
    
    @extend_schema(
        summary="Listar insidencias",
        description="Obtiene el listado de insidencias con paginación y filtros",
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
            200: InsidenciaMiniSerializer(many=True),
        },
        tags=['Insidencias']
    )
    def get(self, request, pk=None):
        """
        Lista todas las insidencias o detalle si se proporciona pk
        """
        if pk:
            return self.retrieve(request, pk)
        
        queryset = Insidencia.objects.filter(
            status_model=BaseModel.STATUS_MODEL_ACTIVE
        ).prefetch_related('lotes_insidencia').order_by('-created_at')
        
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
            serializer = InsidenciaMiniSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = InsidenciaMiniSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @extend_schema(
        summary="Obtener detalle de insidencia",
        description="Obtiene el detalle completo de una insidencia con sus lotes y productos",
        responses={
            200: InsidenciaDetailSerializer,
            404: "Insidencia no encontrada"
        },
        tags=['Insidencias']
    )
    def retrieve(self, request, pk):
        """
        Obtiene el detalle completo de una insidencia
        """
        try:
            insidencia = Insidencia.objects.select_related(
                'created_by'
            ).prefetch_related(
                Prefetch(
                    'lotes_insidencia',
                    queryset=InsidenciaLote.objects.select_related(
                        'lote__producto',
                        'lote__almacen'
                    )
                )
            ).get(pk=pk, status_model=BaseModel.STATUS_MODEL_ACTIVE)
            
            serializer = InsidenciaDetailSerializer(insidencia)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Insidencia.DoesNotExist:
            return Response(
                {'detail': 'Insidencia no encontrada.'},
                status=status.HTTP_404_NOT_FOUND
            )


@extend_schema(
    summary="Atender lotes de insidencia",
    description="Marca múltiples lotes de una insidencia como atendidos",
    request=AtenderInsidenciaLoteSerializer,
    responses={
        200: inline_serializer(
            name='AtenderInsidenciaLoteResponse',
            fields={
                'success': serializers.BooleanField(),
                'message': serializers.CharField(),
                'lotes_atendidos': serializers.IntegerField(),
                'insidencias_resueltas': serializers.ListField(child=serializers.IntegerField()),
            }
        ),
        400: "Error en los datos proporcionados",
        404: "Lote de insidencia no encontrado"
    },
    tags=['Insidencias']
)
@api_view(['POST'])
def atender_insidencia_lote(request):
    """
    Atiende múltiples lotes de insidencias
    """
    serializer = AtenderInsidenciaLoteSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {'detail': 'Datos inválidos', 'errors': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            lotes_data = serializer.validated_data['lotes']
            lotes_atendidos = []
            insidencias_a_verificar = set()
            
            for item in lotes_data:
                insidencia_lote_id = item['insidencia_lote_id']
                nota = item.get('nota', '')
                
                try:
                    insidencia_lote = InsidenciaLote.objects.select_related(
                        'insidencia'
                    ).get(pk=insidencia_lote_id, status_model=BaseModel.STATUS_MODEL_ACTIVE)
                except InsidenciaLote.DoesNotExist:
                    return Response(
                        {'detail': f'Lote de insidencia con ID {insidencia_lote_id} no encontrado.'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                if insidencia_lote.atendida:
                    continue  # Saltar lotes ya atendidos
                
                # Marcar como atendido
                insidencia_lote.atendida = True
                insidencia_lote.fecha_atencion = timezone.now()
                if nota:
                    insidencia_lote.nota = nota
                insidencia_lote.save()
                
                lotes_atendidos.append(insidencia_lote.id)
                insidencias_a_verificar.add(insidencia_lote.insidencia_id)
            
            # Verificar si las insidencias están completamente resueltas
            insidencias_resueltas = []
            for insidencia_id in insidencias_a_verificar:
                insidencia = Insidencia.objects.get(pk=insidencia_id)
                lotes_pendientes = insidencia.lotes_insidencia.filter(atendida=False).exists()
                
                if not lotes_pendientes and not insidencia.resuelta:
                    insidencia.resuelta = True
                    insidencia.save()
                    insidencias_resueltas.append(insidencia_id)
            
            return Response({
                'success': True,
                'message': f'{len(lotes_atendidos)} lote(s) atendido(s) correctamente',
                'lotes_atendidos': len(lotes_atendidos),
                'lotes_ids': lotes_atendidos,
                'insidencias_resueltas': insidencias_resueltas,
            }, status=status.HTTP_200_OK)
            
    except Exception as e:
        return Response(
            {'detail': f'Error al atender lotes: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
