from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.purchases.views import PurchaseOrderViewSet, SupplierViewSet


router = DefaultRouter()
router.register(r"suppliers", SupplierViewSet, basename="supplier")
router.register(r"purchase-orders", PurchaseOrderViewSet, basename="purchaseorder")


urlpatterns = [
    path("stores/<int:store_id>/", include(router.urls)),
]
