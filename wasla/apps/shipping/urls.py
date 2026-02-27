
from django.urls import path
from .views.api import ShipmentCreateAPI, ShipmentDetailAPI, ShipmentListAPI, ShipmentStatusUpdateAPI

urlpatterns = [
    path("shipping/orders/<int:order_id>/ship/", ShipmentCreateAPI.as_view()),
    path("shipping/shipments/", ShipmentListAPI.as_view()),
    path("shipping/shipments/<int:shipment_id>/", ShipmentDetailAPI.as_view()),
    path("shipping/shipments/<int:shipment_id>/status/", ShipmentStatusUpdateAPI.as_view()),
]
