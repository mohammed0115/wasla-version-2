from __future__ import annotations

from apps.catalog.models import Inventory
from apps.tenants.application.dto.merchant_dashboard_metrics import LowStockRowDTO
from apps.tenants.application.interfaces.inventory_repository_port import InventoryRepositoryPort


class DjangoInventoryRepository(InventoryRepositoryPort):
    def low_stock_products(self, store_id: int, threshold: int = 5, limit: int = 10) -> list[LowStockRowDTO]:
        rows = list(
            Inventory.objects.filter(product__store_id=store_id, quantity__lte=threshold)
            .select_related("product")
            .only("quantity", "product__id", "product__name", "product__sku")
            .order_by("quantity", "product__id")[:limit]
        )
        return [
            {
                "product_id": row.product.id,
                "name": row.product.name,
                "sku": row.product.sku,
                "quantity": row.quantity,
            }
            for row in rows
        ]
