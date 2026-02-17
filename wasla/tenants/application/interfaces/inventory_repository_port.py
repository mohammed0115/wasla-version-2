from __future__ import annotations

from typing import Protocol

from tenants.application.dto.merchant_dashboard_metrics import LowStockRowDTO


class InventoryRepositoryPort(Protocol):
    def low_stock_products(self, store_id: int, threshold: int = 5, limit: int = 10) -> list[LowStockRowDTO]:
        ...
