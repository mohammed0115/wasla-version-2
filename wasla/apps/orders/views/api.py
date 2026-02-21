from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from apps.customers.models import Customer
from apps.catalog.models import Product
from ..services.order_service import OrderService
from ..serializers import OrderCreateInputSerializer, OrderSerializer
from ..models import OrderItem, Order
from django.db.models import Sum, F, Count
from django.utils import timezone
from apps.analytics.application.telemetry import TelemetryService, actor_from_request
from apps.analytics.domain.types import ObjectRef
from apps.tenants.domain.tenant_context import TenantContext
from apps.tenants.guards import require_store, require_tenant


class OrderCreateAPI(APIView):
    def post(self, request, customer_id):
        store = require_store(request)
        tenant = require_tenant(request)
        customer = get_object_or_404(Customer, id=customer_id, store_id=store.id)
        input_serializer = OrderCreateInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        items = []
        for item in input_serializer.validated_data["items"]:
            product = get_object_or_404(
                Product,
                id=item["product_id"],
                store_id=customer.store_id,
                is_active=True,
            )
            items.append(
                {
                    "product": product,
                    "quantity": item["quantity"],
                    "price": item.get("price") or product.price,
                }
            )

        try:
            order = OrderService.create_order(
                customer,
                items,
                store_id=customer.store_id,
                tenant=tenant,
                tenant_id=tenant.id,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        tenant_ctx = TenantContext(
            tenant_id=tenant.id,
            store_id=customer.store_id,
            currency=getattr(order, "currency", "SAR") or "SAR",
            user_id=request.user.id if getattr(request, "user", None) and request.user.is_authenticated else None,
            session_key=getattr(getattr(request, "session", None), "session_key", None),
        )
        actor_type = "MERCHANT" if getattr(request, "user", None) and request.user.is_authenticated else "ANON"
        TelemetryService.track(
            event_name="order.placed",
            tenant_ctx=tenant_ctx,
            actor_ctx=actor_from_request(request=request, actor_type=actor_type),
            object_ref=ObjectRef(object_type="ORDER", object_id=order.id),
            properties={"total_amount": str(order.total_amount), "currency": order.currency},
        )

        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class SalesReportAPI(APIView):
    """Basic sales reporting for merchant dashboard (Phase 3).

    Query params:
      - days: integer (default 30)
    """

    def get(self, request):
        store = require_store(request)
        tenant = require_tenant(request)

        try:
            days = int(request.query_params.get("days", 30))
        except ValueError:
            days = 30
        days = max(1, min(days, 365))

        since = timezone.now() - timezone.timedelta(days=days)

        orders_qs = Order.objects.filter(
            store_id=store.id,
            tenant_id=tenant.id,
            status="paid",
            created_at__gte=since,
        )

        agg = orders_qs.aggregate(
            orders_count=Count("id"),
            revenue=Sum("total_amount"),
        )
        orders_count = int(agg.get("orders_count") or 0)
        revenue = agg.get("revenue") or 0
        avg_order_value = (revenue / orders_count) if orders_count else 0

        top_products = (
            OrderItem.objects.filter(order__in=orders_qs)
            .values("product_id", "product__name")
            .annotate(
                qty=Sum("quantity"),
                revenue=Sum(F("quantity") * F("price")),
            )
            .order_by("-revenue")[:10]
        )

        return Response(
            {
                "store_id": store.id,
                "tenant_id": tenant.id,
                "period_days": days,
                "orders_count": orders_count,
                "revenue": str(revenue),
                "avg_order_value": str(avg_order_value),
                "top_products": list(top_products),
            }
        )
