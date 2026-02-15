from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from settlements.domain.dtos import SettlementDetail, SettlementSummary
from settlements.domain.errors import SettlementNotFoundError
from settlements.models import Settlement, SettlementItem


@dataclass(frozen=True)
class GetSettlementDetailCommand:
    settlement_id: int
    store_id: int


class GetSettlementDetailUseCase:
    @staticmethod
    def execute(cmd: GetSettlementDetailCommand) -> SettlementDetail:
        settlement = Settlement.objects.filter(id=cmd.settlement_id, store_id=cmd.store_id).first()
        if not settlement:
            raise SettlementNotFoundError("Settlement not found.")
        items = (
            SettlementItem.objects.select_related("order")
            .filter(settlement_id=settlement.id)
            .order_by("id")
        )
        summary = SettlementSummary(
            id=settlement.id,
            period_start=settlement.period_start,
            period_end=settlement.period_end,
            gross_amount=Decimal(settlement.gross_amount),
            fees_amount=Decimal(settlement.fees_amount),
            net_amount=Decimal(settlement.net_amount),
            status=settlement.status,
            created_at=settlement.created_at,
            approved_at=settlement.approved_at,
            paid_at=settlement.paid_at,
        )
        return SettlementDetail(
            settlement=summary,
            items=[
                {
                    "order_id": item.order_id,
                    "order_amount": Decimal(item.order_amount),
                    "fee_amount": Decimal(item.fee_amount),
                    "net_amount": Decimal(item.net_amount),
                }
                for item in items
            ],
        )
