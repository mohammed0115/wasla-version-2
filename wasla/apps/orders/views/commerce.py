"""
API views for production commerce features

Endpoints:
- /invoices/: List and create invoices
- /invoices/{id}/: Retrieve invoice details
- /invoices/{id}/pdf/: Download invoice PDF
- /invoices/{id}/issue/: Issue invoice (generate and ZATCA sign)
- /rmas/: List and create RMA requests
- /rmas/{id}/: Retrieve RMA details
- /rmas/{id}/approve/: Approve RMA
- /rmas/{id}/reject/: Reject RMA
- /rmas/{id}/track/: Track return shipment
- /rmas/{id}/receive/: Mark return as received
- /rmas/{id}/inspect/: Inspect return and assess condition
- /rmas/{id}/complete/: Complete RMA and process refund
- /refunds/: List and create refunds
- /refunds/{id}/: Retrieve refund status
- /stock-reservations/: List current reservations
- /stock-reservations/{id}/: Retrieve reservation details
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError, NotFound
from django.http import FileResponse, HttpResponse
from django.utils import timezone
import logging

from wasla.apps.orders.models import (
    Invoice,
    InvoiceLineItem,
    RMA,
    ReturnItem,
    RefundTransaction,
    StockReservation,
    Order,
)
from wasla.apps.orders.serializers_commerce import (
    InvoiceSerializer,
    InvoiceCreateSerializer,
    InvoiceGeneratePDFSerializer,
    RMASerializer,
    RMACreateSerializer,
    RMAApproveSerializer,
    RMATrackingSerializer,
    RMAInspectionSerializer,
    RefundTransactionSerializer,
    RefundRequestSerializer,
    StockReservationSerializer,
    StockReservationCreateSerializer,
)
from wasla.apps.orders.services.invoice_service import InvoiceService
from wasla.apps.orders.services.returns_service import ReturnsService, RefundsService
from wasla.apps.orders.services.stock_reservation_service import StockReservationService
from apps.tenants.interfaces.api.authentication import TenantTokenAuth

logger = logging.getLogger(__name__)


class InvoiceViewSet(viewsets.ModelViewSet):
    """
    API endpoints for invoice management
    
    List:
        GET /invoices/
    
    Create:
        POST /invoices/ with {'order_id': int, 'tax_rate': decimal}
    
    Retrieve:
        GET /invoices/{id}/
    
    Issue Invoice (ZATCA sign):
        POST /invoices/{id}/issue/
    
    Generate PDF:
        POST /invoices/{id}/generate-pdf/
    
    Download PDF:
        GET /invoices/{id}/pdf/
    
    Mark as Paid:
        POST /invoices/{id}/mark-paid/
    """
    
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated, TenantTokenAuth]
    filterset_fields = ['status', 'store_id', 'issue_date']
    search_fields = ['invoice_number', 'buyer_email', 'buyer_name']
    ordering_fields = ['issue_date', 'total_amount', 'status']
    ordering = ['-issue_date']
    
    def get_queryset(self):
        """Filter invoices by tenant"""
        user = self.request.user
        token_auth = TenantTokenAuth()
        tenant_id = token_auth.get_tenant_id(self.request)
        return self.queryset.filter(tenant_id=tenant_id)
    
    @action(detail=False, methods=['post'])
    def create_from_order(self, request):
        """Create invoice from order"""
        serializer = InvoiceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            order = Order.objects.get(id=serializer.validated_data['order_id'])
            service = InvoiceService()
            invoice = service.create_invoice_from_order(order)
            
            return Response(
                InvoiceSerializer(invoice).data,
                status=status.HTTP_201_CREATED,
            )
        except Order.DoesNotExist:
            raise NotFound("Order not found")
        except Exception as e:
            logger.error(f"Error creating invoice: {str(e)}", exc_info=True)
            raise ValidationError({"error": str(e)})
    
    @action(detail=True, methods=['post'])
    def issue(self, request, pk=None):
        """Issue invoice and generate ZATCA QR code"""
        invoice = self.get_object()
        
        if invoice.status != 'draft':
            raise ValidationError({"error": "Only draft invoices can be issued"})
        
        try:
            service = InvoiceService()
            issued_invoice = service.issue_invoice(invoice, previous_hash=None)
            
            # Generate PDF asynchronously
            from wasla.apps.orders.tasks import generate_invoice_pdf
            generate_invoice_pdf.delay(issued_invoice.id)
            
            return Response(
                InvoiceSerializer(issued_invoice).data,
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Error issuing invoice {pk}: {str(e)}", exc_info=True)
            raise ValidationError({"error": str(e)})
    
    @action(detail=True, methods=['post'])
    def generate_pdf(self, request, pk=None):
        """Generate PDF for invoice"""
        invoice = self.get_object()
        
        if invoice.status == 'draft':
            raise ValidationError({"error": "Invoice must be issued before generating PDF"})
        
        try:
            service = InvoiceService()
            pdf_bytes = service.generate_pdf(invoice)
            
            from django.core.files.base import ContentFile
            filename = f"invoice_{invoice.invoice_number}.pdf"
            invoice.pdf_file.save(filename, ContentFile(pdf_bytes), save=True)
            
            return Response(
                {
                    "message": "PDF generated successfully",
                    "file_path": invoice.pdf_file.name,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Error generating PDF for invoice {pk}: {str(e)}", exc_info=True)
            raise ValidationError({"error": str(e)})
    
    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        """Download invoice PDF"""
        invoice = self.get_object()
        
        if not invoice.pdf_file:
            raise NotFound("Invoice PDF not found")
        
        try:
            response = FileResponse(invoice.pdf_file.open('rb'))
            response['Content-Type'] = 'application/pdf'
            response['Content-Disposition'] = f'attachment; filename="{invoice.invoice_number}.pdf"'
            return response
        except Exception as e:
            logger.error(f"Error downloading PDF for invoice {pk}: {str(e)}", exc_info=True)
            raise ValidationError({"error": "Could not download PDF"})
    
    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        """Mark invoice as paid"""
        invoice = self.get_object()
        
        try:
            invoice.status = 'paid'
            invoice.paid_at = timezone.now()
            invoice.save()
            
            # Send notification
            from wasla.apps.orders.tasks import send_order_notification
            send_order_notification.delay(invoice.order_id, 'invoice_paid', invoice_id=invoice.id)
            
            return Response(
                InvoiceSerializer(invoice).data,
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Error marking invoice {pk} as paid: {str(e)}", exc_info=True)
            raise ValidationError({"error": str(e)})
    
    @action(detail=True, methods=['post'])
    def mark_refunded(self, request, pk=None):
        """Mark invoice as refunded"""
        invoice = self.get_object()
        
        try:
            invoice.status = 'refunded'
            invoice.save()
            
            return Response(
                InvoiceSerializer(invoice).data,
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Error marking invoice {pk} as refunded: {str(e)}", exc_info=True)
            raise ValidationError({"error": str(e)})


class RMAViewSet(viewsets.ModelViewSet):
    """
    API endpoints for Return Merchandise Authorization (RMA)
    
    List:
        GET /rmas/
    
    Create:
        POST /rmas/ with {
            'order_id': int,
            'reason': str,
            'items': [{'order_item_id': int, 'quantity': int}],
            'is_exchange': bool,
        }
    
    Retrieve:
        GET /rmas/{id}/
    
    Approve:
        POST /rmas/{id}/approve/
    
    Reject:
        POST /rmas/{id}/reject/
    
    Track:
        POST /rmas/{id}/track/ with {'carrier': str, 'tracking_number': str}
    
    Receive:
        POST /rmas/{id}/receive/
    
    Inspect:
        POST /rmas/{id}/inspect/ with {
            'inspections': [{'return_item_id': int, 'condition': str, 'refund_amount': decimal}]
        }
    
    Complete:
        POST /rmas/{id}/complete/
    """
    
    queryset = RMA.objects.all()
    serializer_class = RMASerializer
    permission_classes = [IsAuthenticated, TenantTokenAuth]
    filterset_fields = ['status', 'reason', 'store_id', 'is_exchange']
    search_fields = ['rma_number', 'order__customer_email']
    ordering_fields = ['requested_at', 'status']
    ordering = ['-requested_at']
    
    def get_queryset(self):
        """Filter RMAs by tenant"""
        token_auth = TenantTokenAuth()
        tenant_id = token_auth.get_tenant_id(self.request)
        return self.queryset.filter(tenant_id=tenant_id)
    
    @action(detail=False, methods=['post'])
    def create_request(self, request):
        """Create new RMA request"""
        serializer = RMACreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            order = Order.objects.get(id=serializer.validated_data['order_id'])
            returns_service = ReturnsService()
            
            rma = returns_service.request_rma(
                order=order,
                items=serializer.validated_data['items'],
                reason=serializer.validated_data['reason'],
                description=serializer.validated_data.get('reason_description', ''),
                is_exchange=serializer.validated_data.get('is_exchange', False),
                exchange_product_id=serializer.validated_data.get('exchange_product_id'),
            )
            
            return Response(
                RMASerializer(rma).data,
                status=status.HTTP_201_CREATED,
            )
        except Order.DoesNotExist:
            raise NotFound("Order not found")
        except Exception as e:
            logger.error(f"Error creating RMA: {str(e)}", exc_info=True)
            raise ValidationError({"error": str(e)})
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve RMA request"""
        rma = self.get_object()
        serializer = RMAApproveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            returns_service = ReturnsService()
            approved_rma = returns_service.approve_rma(rma, comment=serializer.validated_data.get('comment', ''))
            
            return Response(
                RMASerializer(approved_rma).data,
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Error approving RMA {pk}: {str(e)}", exc_info=True)
            raise ValidationError({"error": str(e)})
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject RMA request"""
        rma = self.get_object()
        
        try:
            returns_service = ReturnsService()
            rejected_rma = returns_service.reject_rma(rma, reason=request.data.get('reason', ''))
            
            return Response(
                RMASerializer(rejected_rma).data,
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Error rejecting RMA {pk}: {str(e)}", exc_info=True)
            raise ValidationError({"error": str(e)})
    
    @action(detail=True, methods=['post'])
    def track(self, request, pk=None):
        """Track return shipment"""
        rma = self.get_object()
        serializer = RMATrackingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            returns_service = ReturnsService()
            tracked_rma = returns_service.track_return_shipment(
                rma,
                carrier=serializer.validated_data['carrier'],
                tracking_number=serializer.validated_data['tracking_number'],
            )
            
            return Response(
                RMASerializer(tracked_rma).data,
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Error tracking RMA {pk}: {str(e)}", exc_info=True)
            raise ValidationError({"error": str(e)})
    
    @action(detail=True, methods=['post'])
    def receive(self, request, pk=None):
        """Mark return as received"""
        rma = self.get_object()
        
        try:
            returns_service = ReturnsService()
            received_rma = returns_service.receive_return(rma)
            
            return Response(
                RMASerializer(received_rma).data,
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Error marking RMA {pk} as received: {str(e)}", exc_info=True)
            raise ValidationError({"error": str(e)})
    
    @action(detail=True, methods=['post'])
    def inspect(self, request, pk=None):
        """Inspect return items"""
        rma = self.get_object()
        serializer = RMAInspectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            returns_service = ReturnsService()
            inspected_rma = returns_service.inspect_return(
                rma,
                inspections=serializer.validated_data['inspections'],
            )
            
            return Response(
                RMASerializer(inspected_rma).data,
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Error inspecting RMA {pk}: {str(e)}", exc_info=True)
            raise ValidationError({"error": str(e)})
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete RMA and process refund"""
        rma = self.get_object()
        
        try:
            returns_service = ReturnsService()
            completed_rma = returns_service.complete_rma(
                rma,
                refund_method=request.data.get('refund_method', 'original'),
            )
            
            return Response(
                RMASerializer(completed_rma).data,
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Error completing RMA {pk}: {str(e)}", exc_info=True)
            raise ValidationError({"error": str(e)})


class RefundTransactionViewSet(viewsets.ModelViewSet):
    """
    API endpoints for refund management
    
    List:
        GET /refunds/
    
    Create:
        POST /refunds/ with {
            'order_id': int,
            'amount': decimal,
            'refund_reason': str,
            'rma_id': int (optional),
        }
    
    Retrieve:
        GET /refunds/{id}/
    
    Retry Processing:
        POST /refunds/{id}/retry/
    """
    
    queryset = RefundTransaction.objects.all()
    serializer_class = RefundTransactionSerializer
    permission_classes = [IsAuthenticated, TenantTokenAuth]
    filterset_fields = ['status', 'order_id', 'rma_id']
    search_fields = ['refund_id', 'order__customer_email']
    ordering_fields = ['created_at', 'amount']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter refunds by tenant"""
        token_auth = TenantTokenAuth()
        tenant_id = token_auth.get_tenant_id(self.request)
        return self.queryset.filter(tenant_id=tenant_id)
    
    @action(detail=False, methods=['post'])
    def request_refund(self, request):
        """Request new refund"""
        serializer = RefundRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            order = Order.objects.get(id=serializer.validated_data['order_id'])
            refunds_service = RefundsService()
            
            refund = refunds_service.request_refund(
                order=order,
                amount=serializer.validated_data['amount'],
                reason=serializer.validated_data.get('refund_reason', ''),
                rma_id=serializer.validated_data.get('rma_id'),
            )
            
            # Process refund asynchronously
            from wasla.apps.orders.tasks import process_refund
            process_refund.delay(refund.id)
            
            return Response(
                RefundTransactionSerializer(refund).data,
                status=status.HTTP_201_CREATED,
            )
        except Order.DoesNotExist:
            raise NotFound("Order not found")
        except Exception as e:
            logger.error(f"Error requesting refund: {str(e)}", exc_info=True)
            raise ValidationError({"error": str(e)})
    
    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """Retry processing failed refund"""
        refund = self.get_object()
        
        if refund.status not in ['failed', 'initiated']:
            raise ValidationError({"error": "Only failed or initiated refunds can be retried"})
        
        try:
            from wasla.apps.orders.tasks import process_refund
            process_refund.delay(refund.id)
            
            return Response(
                {
                    "message": "Refund processing queued",
                    "status": "processing",
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Error retrying refund {pk}: {str(e)}", exc_info=True)
            raise ValidationError({"error": str(e)})


class StockReservationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoints for viewing stock reservations (read-only)
    
    List:
        GET /stock-reservations/
    
    Retrieve:
        GET /stock-reservations/{id}/
    
    Release (admin only):
        POST /stock-reservations/{id}/release/
    """
    
    queryset = StockReservation.objects.all()
    serializer_class = StockReservationSerializer
    permission_classes = [IsAuthenticated, TenantTokenAuth]
    filterset_fields = ['status', 'store_id', 'expires_at']
    search_fields = ['inventory__product__name']
    ordering_fields = ['expires_at', 'created_at']
    ordering = ['expires_at']
    
    def get_queryset(self):
        """Filter reservations by tenant"""
        token_auth = TenantTokenAuth()
        tenant_id = token_auth.get_tenant_id(self.request)
        return self.queryset.filter(tenant_id=tenant_id)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def release(self, request, pk=None):
        """Manually release a reservation (admin only)"""
        reservation = self.get_object()
        
        # Check if user is admin/staff
        if not request.user.is_staff:
            raise ValidationError({"error": "Only admins can manually release reservations"})
        
        try:
            service = StockReservationService()
            released = service.release_reservation(
                reservation,
                reason=request.data.get('reason', 'manual_release'),
            )
            
            return Response(
                StockReservationSerializer(released).data,
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Error releasing reservation {pk}: {str(e)}", exc_info=True)
            raise ValidationError({"error": str(e)})
    
    @action(detail=False, methods=['get'])
    def expired(self, request):
        """List expired reservations"""
        expired_reservations = self.get_queryset().filter(
            expires_at__lt=timezone.now(),
            status__in=['reserved', 'confirmed'],
        )
        
        serializer = self.get_serializer(expired_reservations, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        """List reservations expiring within next 5 minutes"""
        cutoff = timezone.now() + timezone.timedelta(minutes=5)
        expiring = self.get_queryset().filter(
            expires_at__lt=cutoff,
            expires_at__gte=timezone.now(),
            status__in=['reserved', 'confirmed'],
        )
        
        serializer = self.get_serializer(expiring, many=True)
        return Response(serializer.data)


# URL registration pattern (add to urls.py):
"""
from rest_framework.routers import DefaultRouter
from wasla.apps.orders.views.commerce import (
    InvoiceViewSet,
    RMAViewSet,
    RefundTransactionViewSet,
    StockReservationViewSet,
)

router = DefaultRouter()
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'rmas', RMAViewSet, basename='rma')
router.register(r'refunds', RefundTransactionViewSet, basename='refund')
router.register(r'stock-reservations', StockReservationViewSet, basename='stock_reservation')

urlpatterns = [
    path('api/v1/', include(router.urls)),
]
"""
