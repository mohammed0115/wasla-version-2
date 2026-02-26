from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from  apps.orders.models import Order
from apps.orders.services.order_lifecycle_service import OrderLifecycleService
from ..services.shipping_service import ShippingService
from ..models import Shipment
from ..serializers import ShipmentSerializer, ShipmentStatusUpdateSerializer
from apps.tenants.guards import require_store, require_tenant


class ShipmentCreateAPI(APIView):
    def post(self, request, order_id):
        store = require_store(request)
        tenant = require_tenant(request)
        order = get_object_or_404(Order.objects.for_tenant(store), id=order_id)
        carrier = request.data.get("carrier")
        try:
            shipment = ShippingService.create_shipment(order, carrier)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ShipmentSerializer(shipment).data, status=status.HTTP_201_CREATED)


class ShipmentListAPI(APIView):
    def get(self, request):
        store = require_store(request)
        require_tenant(request)
        order_id = request.query_params.get("order_id")

        queryset = Shipment.objects.select_related("order").filter(order__store_id=store.id).order_by("-created_at")
        if order_id:
            queryset = queryset.filter(order_id=order_id)

        return Response(ShipmentSerializer(queryset, many=True).data, status=status.HTTP_200_OK)


class ShipmentDetailAPI(APIView):
    def get(self, request, shipment_id):
        store = require_store(request)
        require_tenant(request)
        shipment = get_object_or_404(
            Shipment.objects.select_related("order").filter(order__store_id=store.id),
            id=shipment_id,
        )
        return Response(ShipmentSerializer(shipment).data, status=status.HTTP_200_OK)


class ShipmentStatusUpdateAPI(APIView):
    def patch(self, request, shipment_id):
        store = require_store(request)
        require_tenant(request)
        shipment = get_object_or_404(
            Shipment.objects.select_related("order").filter(order__store_id=store.id),
            id=shipment_id,
        )

        serializer = ShipmentStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["status"]

        shipment.status = new_status
        shipment.save(update_fields=["status"])

        order = shipment.order
        if new_status == "shipped" and order.status == "processing":
            OrderLifecycleService.transition(order=order, new_status="shipped")
        if new_status == "delivered" and order.status == "shipped":
            OrderLifecycleService.transition(order=order, new_status="delivered")
        if new_status == "cancelled" and order.status in {"pending", "paid"}:
            OrderLifecycleService.transition(order=order, new_status="cancelled")

        shipment.refresh_from_db()
        return Response(ShipmentSerializer(shipment).data, status=status.HTTP_200_OK)
