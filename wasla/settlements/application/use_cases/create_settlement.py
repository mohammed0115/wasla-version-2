from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal

from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from orders.models import Order
from settlements.domain.errors import SettlementError
from settlements.domain.fees import allocate_fees, resolve_fee_policy
from settlements.domain.policies import ensure_positive_amount
from settlements.models import Settlement, SettlementItem
from analytics.application.telemetry import TelemetryService, actor_from_tenant_ctx
from analytics.domain.types import ObjectRef
from tenants.domain.tenant_context import TenantContext


@dataclass(frozen=True)
class CreateSettlementCommand:
    store_id: int
    period_start: date
    period_end: date


class CreateSettlementUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: CreateSettlementCommand) -> Settlement:
        if not cmd.period_start or not cmd.period_end:
            raise SettlementError("Settlement period is required.")
        if cmd.period_end <= cmd.period_start:
            raise SettlementError("Invalid settlement period.")

        start_dt = timezone.make_aware(datetime.combine(cmd.period_start, time.min))
        end_dt = timezone.make_aware(datetime.combine(cmd.period_end, time.min))

        settled_orders = SettlementItem.objects.filter(order_id=OuterRef("pk"))
        orders_qs = (
            Order.objects.filter(
                store_id=cmd.store_id,
                payment_status="paid",
                created_at__gte=start_dt,
                created_at__lt=end_dt,
            )
            .annotate(is_settled=Exists(settled_orders))
            .filter(is_settled=False)
        )

        order_rows = list(orders_qs.values("id", "total_amount"))
        if not order_rows:
            existing = (
                Settlement.objects.filter(
                    store_id=cmd.store_id,
                    period_start=cmd.period_start,
                    period_end=cmd.period_end,
                )
                .order_by("-created_at")
                .first()
            )
            if existing:
                return existing
            raise SettlementError("No eligible paid orders for this period.")

        amounts = [Decimal(str(row["total_amount"])) for row in order_rows]
        gross_amount = ensure_positive_amount(sum(amounts), field="gross_amount")

        fee_policy = resolve_fee_policy(cmd.store_id)
        fees = allocate_fees(amounts, policy=fee_policy)

        items_payload = []
        fees_total = Decimal("0")
        net_total = Decimal("0")
        for row, fee_amount in zip(order_rows, fees):
            order_amount = Decimal(str(row["total_amount"]))
            net_amount = order_amount - fee_amount
            fees_total += fee_amount
            net_total += net_amount
            items_payload.append(
                SettlementItem(
                    settlement_id=0,
                    order_id=row["id"],
                    order_amount=order_amount,
                    fee_amount=fee_amount,
                    net_amount=net_amount,
                )
            )

        settlement = Settlement.objects.create(
            store_id=cmd.store_id,
            period_start=cmd.period_start,
            period_end=cmd.period_end,
            gross_amount=gross_amount,
            fees_amount=fees_total,
            net_amount=net_total,
            status=Settlement.STATUS_CREATED,
        )

        for item in items_payload:
            item.settlement_id = settlement.id

        SettlementItem.objects.bulk_create(items_payload)
        tenant_ctx = TenantContext(
            tenant_id=cmd.store_id,
            currency="SAR",
            user_id=None,
            session_key="",
        )
        TelemetryService.track(
            event_name="settlement.created",
            tenant_ctx=tenant_ctx,
            actor_ctx=actor_from_tenant_ctx(tenant_ctx=tenant_ctx, actor_type="MERCHANT"),
            object_ref=ObjectRef(object_type="SETTLEMENT", object_id=settlement.id),
            properties={"gross": str(gross_amount), "net": str(net_total)},
        )
        return settlement
