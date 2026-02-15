from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from settlements.application.use_cases.record_audit_log import (
    RecordAuditLogCommand,
    RecordAuditLogUseCase,
)
from settlements.domain.errors import InvalidSettlementStateError, SettlementNotFoundError
from settlements.domain.policies import ensure_non_negative_amount
from settlements.infrastructure.repositories import get_or_create_ledger_account
from settlements.models import LedgerEntry, Settlement
from analytics.application.telemetry import TelemetryService
from analytics.domain.types import ActorContext, ObjectRef
from tenants.domain.tenant_context import TenantContext


@dataclass(frozen=True)
class MarkSettlementPaidCommand:
    settlement_id: int
    actor_id: int | None


class MarkSettlementPaidUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: MarkSettlementPaidCommand) -> Settlement:
        settlement = Settlement.objects.select_for_update().filter(id=cmd.settlement_id).first()
        if not settlement:
            raise SettlementNotFoundError("Settlement not found.")

        if settlement.status == Settlement.STATUS_PAID:
            return settlement
        if settlement.status != Settlement.STATUS_APPROVED:
            raise InvalidSettlementStateError("Settlement must be approved before payment.")

        account = get_or_create_ledger_account(store_id=settlement.store_id)
        if account.available_balance < settlement.net_amount:
            raise InvalidSettlementStateError("Insufficient available balance.")

        account.available_balance = Decimal(account.available_balance) - Decimal(settlement.net_amount)
        account.save(update_fields=["available_balance"])

        LedgerEntry.objects.create(
            store_id=settlement.store_id,
            settlement=settlement,
            entry_type=LedgerEntry.TYPE_DEBIT,
            amount=ensure_non_negative_amount(Decimal(settlement.net_amount), field="net_amount"),
            currency=account.currency,
            description="Settlement paid",
        )

        settlement.status = Settlement.STATUS_PAID
        settlement.paid_at = timezone.now()
        settlement.save(update_fields=["status", "paid_at"])

        RecordAuditLogUseCase.execute(
            RecordAuditLogCommand(
                actor_id=cmd.actor_id,
                store_id=settlement.store_id,
                action="settlement.paid",
                payload={"settlement_id": settlement.id},
            )
        )
        tenant_ctx = TenantContext(
            tenant_id=settlement.store_id,
            currency=account.currency,
            user_id=None,
            session_key="",
        )
        TelemetryService.track(
            event_name="settlement.paid",
            tenant_ctx=tenant_ctx,
            actor_ctx=ActorContext(actor_type="ADMIN", actor_id=cmd.actor_id),
            object_ref=ObjectRef(object_type="SETTLEMENT", object_id=settlement.id),
            properties={"net_amount": str(settlement.net_amount)},
        )
        return settlement
