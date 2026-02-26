from __future__ import annotations

from decimal import Decimal

from apps.tenants.application.interfaces.wallet_repository_port import WalletRepositoryPort
from apps.wallet.models import Wallet


class DjangoWalletRepository(WalletRepositoryPort):
    def wallet_balance(self, store_id: int) -> Decimal:
        wallet = Wallet.objects.filter(store_id=store_id, is_active=True).only("balance").first()
        if not wallet:
            return Decimal("0.00")
        return wallet.balance or Decimal("0.00")
