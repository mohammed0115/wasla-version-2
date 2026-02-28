"""
Django view functions for rendering production commerce templates.
Connects templates with backend models and services.
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import FileResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.middleware.csrf import get_token
from django.db.models import Q, Sum, Count
from datetime import timedelta
from django.utils import timezone

from .models import Order, Invoice, RMA, RefundTransaction, StockReservation
from .services import InvoiceService, ReturnsService


# ============================================================================
# INVOICE VIEWS
# ============================================================================

@login_required
def invoices_list_view(request):
    """
    Display paginated list of invoices with search and filtering.
    
    URL: /orders/invoices/
    Template: invoices_list.html
    """
    invoices = Invoice.objects.all().select_related('order')
    
    # Search by invoice number
    search = request.GET.get('search', '').strip()
    if search:
        invoices = invoices.filter(invoice_number__icontains=search)
    
    # Filter by status
    status = request.GET.get('status', '').strip()
    if status and status in dict(Invoice.STATUS_CHOICES):
        invoices = invoices.filter(status=status)
    
    # Order by created date (newest first)
    invoices = invoices.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(invoices, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'invoices': page_obj.object_list,
        'page_obj': page_obj,
        'is_paginated': paginator.num_pages > 1,
        'search': search,
        'selected_status': status,
    }
    
    return render(request, 'dashboard/orders/invoices_list.html', context)


@login_required
def invoice_detail_view(request, id):
    """
    Display detailed invoice view with line items and ZATCA info.
    
    URL: /orders/invoices/<id>/
    Template: invoice_detail.html
    """
    invoice = get_object_or_404(Invoice, id=id)
    line_items = invoice.line_items.all()
    
    context = {
        'invoice': invoice,
        'line_items': line_items,
    }
    
    return render(request, 'dashboard/orders/invoice_detail.html', context)


@login_required
def invoice_pdf_view(request, id):
    """
    Download invoice as PDF.
    
    URL: /orders/invoices/<id>/pdf/
    """
    invoice = get_object_or_404(Invoice, id=id)
    
    # Generate PDF using InvoiceService
    service = InvoiceService()
    pdf_bytes = service.generate_pdf(invoice)
    
    response = FileResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
    
    return response


# ============================================================================
# RMA (RETURN) VIEWS
# ============================================================================

@login_required
def rma_list_view(request):
    """
    Display paginated list of RMAs with search and filtering.
    
    URL: /orders/rmas/
    Template: rma_list.html
    """
    rmas = RMA.objects.all().select_related('order')
    
    # Search by RMA number or order number
    search = request.GET.get('search', '').strip()
    if search:
        rmas = rmas.filter(
            Q(rma_number__icontains=search) |
            Q(order__id__icontains=search)
        )
    
    # Filter by status
    status = request.GET.get('status', '').strip()
    if status and status in dict(RMA.STATUS_CHOICES):
        rmas = rmas.filter(status=status)
    
    # Order by created date (newest first)
    rmas = rmas.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(rmas, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'rmas': page_obj.object_list,
        'page_obj': page_obj,
        'is_paginated': paginator.num_pages > 1,
        'search': search,
        'selected_status': status,
    }
    
    return render(request, 'dashboard/orders/rma_list.html', context)


@login_required
def rma_detail_view(request, id):
    """
    Display detailed RMA view with items, tracking, and refunds.
    
    URL: /orders/rmas/<id>/
    Template: rma_detail.html
    """
    rma = get_object_or_404(RMA, id=id)
    items = rma.return_items.all()
    refunds = RefundTransaction.objects.filter(rma=rma)
    
    context = {
        'rma': rma,
        'items': items,
        'refunds': refunds,
    }
    
    return render(request, 'dashboard/orders/rma_detail.html', context)


# ============================================================================
# REFUND VIEWS
# ============================================================================

@login_required
def refunds_list_view(request):
    """
    Display paginated list of refunds with search and filtering.
    
    URL: /orders/refunds/
    Template: refunds_list.html
    """
    refunds = RefundTransaction.objects.all().select_related('order', 'rma')
    
    # Search by refund ID or order number
    search = request.GET.get('search', '').strip()
    if search:
        refunds = refunds.filter(
            Q(refund_id__icontains=search) |
            Q(order__id__icontains=search)
        )
    
    # Filter by status
    status = request.GET.get('status', '').strip()
    if status and status in dict(RefundTransaction.STATUS_CHOICES):
        refunds = refunds.filter(status=status)
    
    # Order by created date (newest first)
    refunds = refunds.order_by('-created_at')
    
    # Statistics
    total_refunds_count = refunds.count()
    total_refunds_amount = refunds.aggregate(Sum('amount'))['amount__sum'] or 0
    completed_refunds_count = refunds.filter(status='completed').count()
    processing_refunds_count = refunds.filter(status='processing').count()
    
    # Pagination
    paginator = Paginator(refunds, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'refunds': page_obj.object_list,
        'page_obj': page_obj,
        'is_paginated': paginator.num_pages > 1,
        'search': search,
        'selected_status': status,
        'total_refunds_count': total_refunds_count,
        'total_refunds_amount': total_refunds_amount,
        'completed_refunds_count': completed_refunds_count,
        'processing_refunds_count': processing_refunds_count,
    }
    
    return render(request, 'dashboard/orders/refunds_list.html', context)


@login_required
def refund_detail_view(request, id):
    """
    Display detailed refund view with timeline and gateway info.
    
    URL: /orders/refunds/<id>/
    Template: refund_detail.html
    """
    refund = get_object_or_404(RefundTransaction, id=id)
    
    context = {
        'refund': refund,
    }
    
    return render(request, 'dashboard/orders/refund_detail.html', context)


# ============================================================================
# STOCK RESERVATION VIEWS
# ============================================================================

@login_required
def stock_reservations_view(request):
    """
    Display paginated list of stock reservations with TTL management.
    
    URL: /orders/stock-reservations/
    Template: stock_reservations.html
    """
    reservations = StockReservation.objects.all().select_related('order', 'product')
    
    # Search by product SKU or order number
    search = request.GET.get('search', '').strip()
    if search:
        reservations = reservations.filter(
            Q(product__sku__icontains=search) |
            Q(order__id__icontains=search)
        )
    
    # Filter by status
    status = request.GET.get('status', '').strip()
    if status == 'expiring':
        # Expiring soon: within 5 minutes
        expiring_threshold = timezone.now() + timedelta(minutes=5)
        reservations = reservations.filter(
            status='active',
            expires_at__lte=expiring_threshold
        )
    elif status and status in dict(StockReservation.STATUS_CHOICES):
        reservations = reservations.filter(status=status)
    
    # Order by expires date (soonest first)
    reservations = reservations.order_by('expires_at')
    
    # Statistics
    active_reservations_count = StockReservation.objects.filter(status='active').count()
    expiring_threshold = timezone.now() + timedelta(minutes=5)
    expiring_soon_count = StockReservation.objects.filter(
        status='active',
        expires_at__lte=expiring_threshold
    ).count()
    expired_count = StockReservation.objects.exclude(status='active').count()
    total_reserved_qty = StockReservation.objects.filter(
        status='active'
    ).aggregate(Sum('quantity'))['quantity__sum'] or 0
    
    # Pagination
    paginator = Paginator(reservations, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'reservations': page_obj.object_list,
        'page_obj': page_obj,
        'is_paginated': paginator.num_pages > 1,
        'search': search,
        'selected_status': status,
        'active_reservations_count': active_reservations_count,
        'expiring_soon_count': expiring_soon_count,
        'expired_count': expired_count,
        'total_reserved_qty': total_reserved_qty,
    }
    
    return render(request, 'dashboard/orders/stock_reservations.html', context)


# ============================================================================
# AJAX API ENDPOINTS FOR STOCK RESERVATIONS
# ============================================================================

@login_required
@require_http_methods(["POST"])
def extend_reservation_api(request, id):
    """
    API endpoint to extend stock reservation TTL by 15 minutes.
    
    URL: /api/reservations/<id>/extend/
    Method: POST
    Returns: JSON
    """
    from .services import StockReservationService
    
    try:
        reservation = get_object_or_404(StockReservation, id=id)
        service = StockReservationService()
        service.extend_ttl(reservation, minutes=15)
        
        return JsonResponse({
            'success': True,
            'message': 'Reservation extended successfully',
            'expires_at': reservation.expires_at.isoformat()
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@require_http_methods(["POST"])
def release_reservation_api(request, id):
    """
    API endpoint to immediately release stock reservation.
    
    URL: /api/reservations/<id>/release/
    Method: POST
    Returns: JSON
    """
    from .services import StockReservationService
    
    try:
        reservation = get_object_or_404(StockReservation, id=id)
        service = StockReservationService()
        service.release(reservation)
        
        return JsonResponse({
            'success': True,
            'message': 'Reservation released successfully'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@require_http_methods(["POST"])
def retry_refund_api(request, id):
    """
    API endpoint to retry a failed refund.
    
    URL: /api/refunds/<id>/retry/
    Method: POST
    Returns: JSON
    """
    from .services import RefundsService
    
    try:
        refund = get_object_or_404(RefundTransaction, id=id)
        
        if refund.status != 'failed':
            return JsonResponse({
                'success': False,
                'error': 'Refund must be in failed status to retry'
            }, status=400)
        
        service = RefundsService()
        service.process_refund(refund)
        
        return JsonResponse({
            'success': True,
            'message': 'Refund retry submitted',
            'status': refund.status
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
