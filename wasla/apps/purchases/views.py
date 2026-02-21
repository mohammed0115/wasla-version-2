from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.purchases.models import PurchaseOrder, Supplier
from apps.purchases.serializers import (
    GoodsReceiptNoteSerializer,
    PurchaseOrderSerializer,
    SupplierSerializer,
)
from apps.purchases.services import PurchaseReceivingService


class SupplierViewSet(viewsets.ModelViewSet):
    serializer_class = SupplierSerializer

    def get_queryset(self):
        store_id = int(self.kwargs.get("store_id"))
        return Supplier.objects.filter(store_id=store_id).order_by("name")

    def perform_create(self, serializer):
        serializer.save(store_id=int(self.kwargs.get("store_id")))


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    serializer_class = PurchaseOrderSerializer

    def get_queryset(self):
        store_id = int(self.kwargs.get("store_id"))
        return PurchaseOrder.objects.filter(store_id=store_id).select_related("supplier").prefetch_related("items")

    def perform_create(self, serializer):
        serializer.save(store_id=int(self.kwargs.get("store_id")))

    @action(detail=True, methods=["post"], url_path="receive")
    def receive(self, request, store_id: str = None, pk: str = None):
        po = get_object_or_404(PurchaseOrder, pk=pk, store_id=int(store_id))
        note = request.data.get("note", "")
        try:
            grn = PurchaseReceivingService.receive_purchase_order(po, note=note)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(GoodsReceiptNoteSerializer(grn).data, status=status.HTTP_201_CREATED)
