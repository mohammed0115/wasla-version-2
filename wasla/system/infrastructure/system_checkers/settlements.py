from __future__ import annotations

from django.db.utils import OperationalError, ProgrammingError

from settlements.models import LedgerAccount, Settlement
from system.domain.go_live_checks.types import GoLiveCheckItem, LEVEL_P0, LEVEL_P1
from tenants.models import Tenant


class SettlementReadinessChecker:
    category_key = "settlements"
    category_label = "Settlement readiness"

    def run(self) -> list[GoLiveCheckItem]:
        items: list[GoLiveCheckItem] = []

        try:
            active_tenants = list(Tenant.objects.filter(is_active=True).values_list("id", flat=True))
            active_count = len(active_tenants)
            ledger_count = (
                LedgerAccount.objects.filter(store_id__in=active_tenants)
                .values("store_id")
                .distinct()
                .count()
            )
            ledger_ok = active_count == 0 or ledger_count >= active_count
            items.append(
                GoLiveCheckItem(
                    key="settlements.ledger_accounts",
                    label="Ledger accounts exist for active tenants",
                    ok=ledger_ok,
                    level=LEVEL_P0,
                    message=""
                    if ledger_ok
                    else "Create ledger accounts for active tenants (pending/available balances).",
                    category=self.category_key,
                )
            )
        except (OperationalError, ProgrammingError):
            items.append(
                GoLiveCheckItem(
                    key="settlements.ledger_accounts",
                    label="Ledger accounts exist for active tenants",
                    ok=False,
                    level=LEVEL_P0,
                    message="Ledger tables are not ready. Run migrations first.",
                    category=self.category_key,
                )
            )

        try:
            _ = Settlement.objects.none().count()
            items.append(
                GoLiveCheckItem(
                    key="settlements.table_ready",
                    label="Settlement tables ready",
                    ok=True,
                    level=LEVEL_P1,
                    message="",
                    category=self.category_key,
                )
            )
        except (OperationalError, ProgrammingError):
            items.append(
                GoLiveCheckItem(
                    key="settlements.table_ready",
                    label="Settlement tables ready",
                    ok=False,
                    level=LEVEL_P0,
                    message="Settlement tables are missing or not migrated.",
                    category=self.category_key,
                )
            )

        return items
