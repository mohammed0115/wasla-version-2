from __future__ import annotations

from tenants.application.dto.merchant_dashboard_metrics import LowStockRowDTO
from tenants.application.interfaces.inventory_repository_port import InventoryRepositoryPort


class DjangoLowStockRepository(InventoryRepositoryPort):
    _PRODUCT_STOCK_FIELDS = ["stock_quantity", "quantity", "on_hand", "stock"]

    def low_stock_products(self, store_id: int, threshold: int = 5, limit: int = 10) -> list[LowStockRowDTO]:
        if store_id <= 0 or limit <= 0:
            return []

        inventory_results = self._low_stock_from_inventory(store_id=store_id, threshold=threshold, limit=limit)
        if inventory_results is not None:
            return inventory_results

        return self._low_stock_from_product(store_id=store_id, threshold=threshold, limit=limit)

    def _low_stock_from_inventory(
        self, *, store_id: int, threshold: int, limit: int
    ) -> list[LowStockRowDTO] | None:
        try:
            from catalog.models import Inventory  # type: ignore
        except Exception:
            return None

        try:
            rows = list(
                Inventory.objects.select_related("product")
                .filter(product__store_id=store_id, product__is_active=True, quantity__lte=threshold)
                .only("quantity", "product__id", "product__name", "product__sku")
                .order_by("quantity", "product_id")[:limit]
            )
        except Exception:
            return []

        results: list[LowStockRowDTO] = []
        for row in rows:
            product = getattr(row, "product", None)
            if not product:
                continue
            results.append(
                {
                    "product_id": int(getattr(product, "id", 0) or 0),
                    "name": str(getattr(product, "name", "") or ""),
                    "sku": str(getattr(product, "sku", "") or ""),
                    "quantity": int(getattr(row, "quantity", 0) or 0),
                }
            )
        return results

    def _low_stock_from_product(self, *, store_id: int, threshold: int, limit: int) -> list[LowStockRowDTO]:
        try:
            from catalog.models import Product  # type: ignore
        except Exception:
            return []

        try:
            field_names = {field.name for field in Product._meta.fields}
        except Exception:
            return []

        stock_field = next((name for name in self._PRODUCT_STOCK_FIELDS if name in field_names), None)
        if not stock_field:
            return []

        filters: dict[str, object] = {"store_id": store_id, f"{stock_field}__lte": threshold}
        if "is_active" in field_names:
            filters["is_active"] = True

        try:
            rows = list(
                Product.objects.filter(**filters)
                .only("id", "name", "sku", stock_field)
                .order_by(stock_field, "id")[:limit]
            )
        except Exception:
            return []

        results: list[LowStockRowDTO] = []
        for row in rows:
            results.append(
                {
                    "product_id": int(getattr(row, "id", 0) or 0),
                    "name": str(getattr(row, "name", "") or ""),
                    "sku": str(getattr(row, "sku", "") or ""),
                    "quantity": int(getattr(row, stock_field, 0) or 0),
                }
            )
        return results
