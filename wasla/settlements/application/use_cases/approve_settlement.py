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
class ApproveSettlementCommand:
    settlement_id: int
    actor_id: int | None


class ApproveSettlementUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: ApproveSettlementCommand) -> Settlement:
        settlement = Settlement.objects.select_for_update().filter(id=cmd.settlement_id).first()
        if not settlement:
            raise SettlementNotFoundError("Settlement not found.")

        if settlement.status == Settlement.STATUS_APPROVED:
            return settlement
        if settlement.status != Settlement.STATUS_CREATED:
            raise InvalidSettlementStateError("Settlement is not in a creatable state.")

        account = get_or_create_ledger_account(store_id=settlement.store_id)
        if account.pending_balance < settlement.gross_amount:
            raise InvalidSettlementStateError("Insufficient pending balance.")

        account.pending_balance = Decimal(account.pending_balance) - Decimal(settlement.gross_amount)
        account.available_balance = Decimal(account.available_balance) + Decimal(settlement.net_amount)
        account.save(update_fields=["pending_balance", "available_balance"])

        LedgerEntry.objects.create(
            store_id=settlement.store_id,
            settlement=settlement,
            entry_type=LedgerEntry.TYPE_DEBIT,
            amount=ensure_non_negative_amount(Decimal(settlement.gross_amount), field="gross_amount"),
            currency=account.currency,
            description="Settlement approved (pending cleared)",
        )
        LedgerEntry.objects.create(
            store_id=settlement.store_id,
            settlement=settlement,
            entry_type=LedgerEntry.TYPE_CREDIT,
            amount=ensure_non_negative_amount(Decimal(settlement.net_amount), field="net_amount"),
            currency=account.currency,
            description="Settlement approved (available credited)",
        )

        settlement.status = Settlement.STATUS_APPROVED
        settlement.approved_at = timezone.now()
        settlement.save(update_fields=["status", "approved_at"])

        RecordAuditLogUseCase.execute(
            RecordAuditLogCommand(
                actor_id=cmd.actor_id,
                store_id=settlement.store_id,
                action="settlement.approved",
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
            event_name="settlement.approved",
            tenant_ctx=tenant_ctx,
            actor_ctx=ActorContext(actor_type="ADMIN", actor_id=cmd.actor_id),
            object_ref=ObjectRef(object_type="SETTLEMENT", object_id=settlement.id),
            properties={"net_amount": str(settlement.net_amount)},
        )
        return settlement
