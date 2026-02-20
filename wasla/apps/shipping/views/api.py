from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from  apps.orders.models import Order
from ..services.shipping_service import ShippingService
from ..serializers import ShipmentSerializer
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
