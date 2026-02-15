from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from customers.models import Customer
from catalog.models import Product
from ..services.order_service import OrderService
from ..serializers import OrderCreateInputSerializer, OrderSerializer
from analytics.application.telemetry import TelemetryService, actor_from_request
from analytics.domain.types import ObjectRef
from tenants.domain.tenant_context import TenantContext


class OrderCreateAPI(APIView):
    def post(self, request, customer_id):
        tenant = getattr(request, "tenant", None)
        tenant_id = getattr(tenant, "id", None) if tenant is not None else None
        if isinstance(tenant_id, int):
            customer = get_object_or_404(Customer, id=customer_id, store_id=tenant_id)
        else:
            customer = get_object_or_404(Customer, id=customer_id)
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
            order = OrderService.create_order(customer, items, store_id=customer.store_id)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        tenant_ctx = TenantContext(
            tenant_id=customer.store_id,
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
