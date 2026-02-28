"""
URL routing for production commerce web views.
These URLs are for the merchant-facing dashboard templates.
"""

from django.urls import path
from . import web

# Invoice URLs
invoice_patterns = [
    path('', web.invoices_list_view, name='invoices-list'),
    path('<int:id>/', web.invoice_detail_view, name='invoice-detail'),
    path('<int:id>/pdf/', web.invoice_pdf_view, name='invoice-pdf'),
]

# RMA URLs
rma_patterns = [
    path('', web.rma_list_view, name='rma-list'),
    path('<int:id>/', web.rma_detail_view, name='rma-detail'),
]

# Refund URLs
refund_patterns = [
    path('', web.refunds_list_view, name='refunds-list'),
    path('<int:id>/', web.refund_detail_view, name='refund-detail'),
]

# Stock Reservation URLs
reservation_patterns = [
    path('', web.stock_reservations_view, name='stock-reservations'),
]

# API endpoints
api_patterns = [
    path('api/reservations/<int:id>/extend/', web.extend_reservation_api, name='reservation-extend-api'),
    path('api/reservations/<int:id>/release/', web.release_reservation_api, name='reservation-release-api'),
    path('api/refunds/<int:id>/retry/', web.retry_refund_api, name='refund-retry-api'),
]

# Main URL configuration
urlpatterns = [
    path('invoices/', web.invoices_list_view, name='invoices-list'),
    path('invoices/<int:id>/', web.invoice_detail_view, name='invoice-detail'),
    path('invoices/<int:id>/pdf/', web.invoice_pdf_view, name='invoice-pdf'),
    
    path('rmas/', web.rma_list_view, name='rma-list'),
    path('rmas/<int:id>/', web.rma_detail_view, name='rma-detail'),
    
    path('refunds/', web.refunds_list_view, name='refunds-list'),
    path('refunds/<int:id>/', web.refund_detail_view, name='refund-detail'),
    
    path('stock-reservations/', web.stock_reservations_view, name='stock-reservations'),
    
    # API endpoints for dashboard interactions
    path('api/reservations/<int:id>/extend/', web.extend_reservation_api, name='reservation-extend-api'),
    path('api/reservations/<int:id>/release/', web.release_reservation_api, name='reservation-release-api'),
    path('api/refunds/<int:id>/retry/', web.retry_refund_api, name='refund-retry-api'),
]
