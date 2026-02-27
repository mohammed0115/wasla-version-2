from __future__ import annotations

from decimal import Decimal
from typing import Protocol


class WalletRepositoryPort(Protocol):
    def wallet_balance(self, store_id: int) -> Decimal:
        ...
