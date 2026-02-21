from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import models

from apps.catalog.models import Inventory, StockMovement
from apps.tenants.guards import require_store


class LowStockAPI(APIView):
    """Return low stock products for a store (Phase 3)."""

    def get(self, request):
        store = require_store(request)

        qs = (
            Inventory.objects.select_related("product")
            .filter(product__store_id=store.id)
            .filter(quantity__lte=models.F("low_stock_threshold"))
            .order_by("quantity")
        )

        data = [
            {
                "product_id": inv.product_id,
                "product_name": inv.product.name,
                "quantity": inv.quantity,
                "low_stock_threshold": inv.low_stock_threshold,
            }
            for inv in qs
        ]
        return Response({"store_id": store.id, "items": data})


class StockMovementsAPI(APIView):
    """List stock movements for a store (Phase 3)."""

    def get(self, request):
        store = require_store(request)
        product_id = request.query_params.get("product_id")

        qs = StockMovement.objects.filter(store_id=store.id).select_related("product").order_by("-created_at")
        if product_id:
            qs = qs.filter(product_id=product_id)

        data = [
            {
                "id": m.id,
                "product_id": m.product_id,
                "product_name": m.product.name,
                "movement_type": m.movement_type,
                "quantity": m.quantity,
                "reason": m.reason,
                "order_id": m.order_id,
                "purchase_order_id": m.purchase_order_id,
                "created_at": m.created_at,
            }
            for m in qs[:200]
        ]

        return Response({"store_id": store.id, "items": data})
