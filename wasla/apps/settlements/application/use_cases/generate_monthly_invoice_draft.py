from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.settlements.models import Invoice, InvoiceLine, SettlementRecord
from apps.tenants.models import Tenant


@dataclass(frozen=True)
class InvoiceDraftResult:
    invoice: Invoice
    created: bool


def _month_bounds(year: int, month: int):
    if month < 1 or month > 12:
        raise ValueError("invalid_month")
    start = timezone.make_aware(datetime.combine(datetime(year, month, 1).date(), time.min))
    end_day = monthrange(year, month)[1]
    end = timezone.make_aware(datetime.combine(datetime(year, month, end_day).date(), time.max))
    return start, end


@transaction.atomic
def generate_monthly_invoice_draft(tenant_id: int, year: int, month: int) -> InvoiceDraftResult:
    start_at, end_at = _month_bounds(year=year, month=month)

    invoice = (
        Invoice.objects.select_for_update()
        .filter(tenant_id=tenant_id, year=year, month=month)
        .first()
    )
    if invoice:
        return InvoiceDraftResult(invoice=invoice, created=False)

    tenant = Tenant.objects.filter(id=tenant_id).first()
    if not tenant:
        raise ValueError("tenant_not_found")

    candidate_qs = (
        SettlementRecord.objects.select_for_update()
        .filter(
            store__tenant_id=tenant_id,
            created_at__gte=start_at,
            created_at__lte=end_at,
            status=SettlementRecord.STATUS_PENDING,
            invoice_line__isnull=True,
        )
        .order_by("id")
    )

    totals = candidate_qs.aggregate(
        total_operations=Coalesce(Count("id"), 0),
        total_wasla_fee=Coalesce(Sum("wasla_fee"), Decimal("0.00")),
    )
    total_operations = int(totals.get("total_operations") or 0)
    total_wasla_fee = Decimal(totals.get("total_wasla_fee") or Decimal("0.00"))

    try:
        invoice = Invoice.objects.create(
            tenant=tenant,
            year=year,
            month=month,
            total_operations=total_operations,
            total_wasla_fee=total_wasla_fee,
            status=Invoice.STATUS_DRAFT,
        )
    except IntegrityError:
        existing = Invoice.objects.get(tenant_id=tenant_id, year=year, month=month)
        return InvoiceDraftResult(invoice=existing, created=False)

    lines = [
        InvoiceLine(invoice=invoice, settlement=settlement)
        for settlement in candidate_qs
    ]
    if lines:
        InvoiceLine.objects.bulk_create(lines)

    return InvoiceDraftResult(invoice=invoice, created=True)
