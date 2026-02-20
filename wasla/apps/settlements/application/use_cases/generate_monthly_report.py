from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.settlements.models import SettlementRecord


@dataclass(frozen=True)
class MonthlyReportResult:
    tenant_id: int
    year: int
    month: int
    total_operations: int
    total_wasla_fee: Decimal
    settlement_ids: list[int]


def _month_bounds(year: int, month: int):
    if month < 1 or month > 12:
        raise ValueError("invalid_month")
    start = timezone.make_aware(datetime.combine(datetime(year, month, 1).date(), time.min))
    end_day = monthrange(year, month)[1]
    end = timezone.make_aware(datetime.combine(datetime(year, month, end_day).date(), time.max))
    return start, end


def generate_monthly_report(tenant_id: int, year: int, month: int) -> MonthlyReportResult:
    start_at, end_at = _month_bounds(year=year, month=month)

    settlements_qs = SettlementRecord.objects.filter(
        store__tenant_id=tenant_id,
        created_at__gte=start_at,
        created_at__lte=end_at,
        status__in=[SettlementRecord.STATUS_PENDING, SettlementRecord.STATUS_INVOICED],
    ).order_by("id")

    settlement_ids = list(settlements_qs.values_list("id", flat=True))
    aggregate = settlements_qs.aggregate(
        total_wasla_fee=Coalesce(Sum("wasla_fee"), Decimal("0.00")),
    )

    return MonthlyReportResult(
        tenant_id=tenant_id,
        year=year,
        month=month,
        total_operations=len(settlement_ids),
        total_wasla_fee=Decimal(aggregate["total_wasla_fee"]),
        settlement_ids=settlement_ids,
    )
