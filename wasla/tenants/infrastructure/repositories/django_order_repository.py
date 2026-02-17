from __future__ import annotations

from datetime import datetime, time, timedelta, timezone as dt_timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from orders.models import Order
from tenants.application.dto.merchant_dashboard_metrics import ChartPointDTO, RecentOrderRowDTO
from tenants.application.interfaces.order_repository_port import OrderRepositoryPort


class DjangoOrderRepository(OrderRepositoryPort):
    @staticmethod
    def _tzinfo(tz: str) -> ZoneInfo:
        try:
            return ZoneInfo(tz)
        except Exception:
            return ZoneInfo("UTC")

    @classmethod
    def _today_utc_bounds(cls, tz: str) -> tuple[datetime, datetime]:
        tzinfo = cls._tzinfo(tz)
        local_now = timezone.localtime(timezone.now(), tzinfo)
        local_start = datetime.combine(local_now.date(), time.min, tzinfo=tzinfo)
        local_end = local_start + timedelta(days=1)
        return local_start.astimezone(dt_timezone.utc), local_end.astimezone(dt_timezone.utc)

    @classmethod
    def _last_7_days_utc_bounds(cls, tz: str) -> tuple[datetime, datetime]:
        tzinfo = cls._tzinfo(tz)
        local_now = timezone.localtime(timezone.now(), tzinfo)
        start_date = local_now.date() - timedelta(days=6)
        local_start = datetime.combine(start_date, time.min, tzinfo=tzinfo)
        local_end = datetime.combine(local_now.date() + timedelta(days=1), time.min, tzinfo=tzinfo)
        return local_start.astimezone(dt_timezone.utc), local_end.astimezone(dt_timezone.utc)

    def sum_sales_today(self, tenant_id: int, tz: str) -> Decimal:
        start_today, end_today = self._today_utc_bounds(tz)
        return (
            Order.objects.filter(store_id=tenant_id, created_at__gte=start_today, created_at__lt=end_today)
            .exclude(status__in=["canceled", "cancelled"])
            .aggregate(total=Sum("total_amount"))
            .get("total")
            or Decimal("0.00")
        )

    def count_orders_today(self, tenant_id: int, tz: str) -> int:
        start_today, end_today = self._today_utc_bounds(tz)
        return (
            Order.objects.filter(store_id=tenant_id, created_at__gte=start_today, created_at__lt=end_today)
            .exclude(status__in=["canceled", "cancelled"])
            .count()
        )

    def sum_revenue_last_7_days(self, tenant_id: int, tz: str) -> Decimal:
        start_7d, end_7d = self._last_7_days_utc_bounds(tz)
        return (
            Order.objects.filter(store_id=tenant_id, created_at__gte=start_7d, created_at__lt=end_7d)
            .exclude(status__in=["canceled", "cancelled"])
            .aggregate(total=Sum("total_amount"))
            .get("total")
            or Decimal("0.00")
        )

    def chart_revenue_orders_last_7_days(self, tenant_id: int, tz: str) -> list[ChartPointDTO]:
        start_7d, end_7d = self._last_7_days_utc_bounds(tz)
        tzinfo = self._tzinfo(tz)
        grouped_rows = (
            Order.objects.filter(store_id=tenant_id, created_at__gte=start_7d, created_at__lt=end_7d)
            .exclude(status__in=["canceled", "cancelled"])
            .annotate(local_date=TruncDate("created_at", tzinfo=tzinfo))
            .values("local_date")
            .annotate(revenue=Sum("total_amount"), orders=Count("id"))
            .order_by("local_date")
        )

        by_date: dict[str, tuple[Decimal, int]] = {
            row["local_date"].isoformat(): (
                row["revenue"] or Decimal("0.00"),
                int(row["orders"] or 0),
            )
            for row in grouped_rows
        }

        local_now = timezone.localtime(timezone.now(), tzinfo)
        day_keys = [
            (local_now.date() - timedelta(days=offset)).isoformat()
            for offset in range(6, -1, -1)
        ]

        return [
            {
                "date": day,
                "revenue": by_date.get(day, (Decimal("0.00"), 0))[0],
                "orders": by_date.get(day, (Decimal("0.00"), 0))[1],
                "revenue_level": 0,
            }
            for day in day_keys
        ]

    def recent_orders(self, tenant_id: int, limit: int = 10) -> list[RecentOrderRowDTO]:
        rows = list(
            Order.objects.filter(store_id=tenant_id)
            .select_related("customer")
            .only("id", "created_at", "total_amount", "status", "customer_name", "customer__full_name")
            .order_by("-created_at")[:limit]
        )
        return [
            {
                "id": row.id,
                "created_at": row.created_at,
                "total": row.total_amount,
                "status": row.status,
                "customer_name": row.customer_name or row.customer.full_name,
            }
            for row in rows
        ]