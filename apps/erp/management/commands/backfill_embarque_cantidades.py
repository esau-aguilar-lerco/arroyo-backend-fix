from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.base.models import BaseModel
from apps.erp.models import VentaDetalle
from apps.inventario.models import ProductoEmbarque


class Command(BaseCommand):
    help = (
        "Backfill ProductoEmbarque.cantidad when it is 0 using lotes or venta detalle. "
        "Use --apply to persist changes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Aplica los cambios en BD (por defecto es dry-run).",
        )
        parser.add_argument(
            "--embarque-id",
            type=int,
            default=None,
            help="Filtra por ID de embarque (opcional).",
        )
        parser.add_argument(
            "--tipo",
            choices=[ProductoEmbarque.PEDIDO, ProductoEmbarque.TARA],
            default=None,
            help="Filtra por tipo de producto (PEDIDO o TARA).",
        )

    def handle(self, *args, **options):
        apply = options["apply"]
        embarque_id = options["embarque_id"]
        tipo = options["tipo"]

        qs = ProductoEmbarque.objects.filter(
            status_model=BaseModel.STATUS_MODEL_ACTIVE
        ).filter(Q(cantidad__isnull=True) | Q(cantidad__lte=0))

        if embarque_id:
            qs = qs.filter(embarque_id=embarque_id)
        if tipo:
            qs = qs.filter(tipo=tipo)

        qs = qs.select_related("preventa", "producto").prefetch_related("lotes")

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS("No se encontraron registros para actualizar."))
            return

        updated = 0
        skipped = 0
        sample_updates = []

        for pe in qs:
            new_qty = None

            lotes_sum = sum((l.cantidad for l in pe.lotes.all()), Decimal("0"))
            if lotes_sum > 0:
                new_qty = lotes_sum
            elif pe.tipo == ProductoEmbarque.PEDIDO and pe.preventa_id and pe.producto_id:
                detalle = VentaDetalle.objects.filter(
                    venta_id=pe.preventa_id,
                    producto_id=pe.producto_id,
                ).first()
                if detalle:
                    if detalle.cantidad_logistica and detalle.cantidad_logistica > 0:
                        new_qty = detalle.cantidad_logistica
                    elif detalle.cantidad and detalle.cantidad > 0:
                        new_qty = detalle.cantidad

            if new_qty and new_qty > 0:
                if apply:
                    update_fields = ["cantidad"]
                    pe.cantidad = new_qty
                    if pe.tipo == ProductoEmbarque.PEDIDO and (pe.cantidad_solicitada is None or pe.cantidad_solicitada <= 0):
                        pe.cantidad_solicitada = new_qty
                        update_fields.append("cantidad_solicitada")
                    pe.save(update_fields=update_fields)
                updated += 1
                if len(sample_updates) < 5:
                    sample_updates.append((pe.id, str(new_qty), pe.tipo))
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f"Total candidatos: {total} | Actualizados: {updated} | Sin datos: {skipped}"
        ))

        if sample_updates:
            self.stdout.write("Ejemplos de actualización (id, cantidad, tipo):")
            for item in sample_updates:
                self.stdout.write(f"- {item[0]} | {item[1]} | {item[2]}")

        if not apply:
            self.stdout.write(self.style.WARNING("Dry-run. Ejecuta con --apply para aplicar cambios."))
