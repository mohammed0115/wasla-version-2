from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from orders.models import Order
from ..services.payment_service import PaymentService
from ..serializers import PaymentSerializer

class PaymentInitiateAPI(APIView):
    def post(self, request, order_id):
        tenant = getattr(request, "tenant", None)
        tenant_id = getattr(tenant, "id", None) if tenant is not None else None
        if isinstance(tenant_id, int):
            order = get_object_or_404(Order, id=order_id, store_id=tenant_id)
        else:
            order = get_object_or_404(Order, id=order_id)
        method = request.data.get("method") or "card"
        try:
            payment = PaymentService.initiate_payment(order, method)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)
