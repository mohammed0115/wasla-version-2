"""
Celery tasks for orders app

Tasks:
- auto_release_expired_stock_reservations: Cleanup expired stock reservations
- process_order_payments: Process pending order payments
- send_order_notifications: Send email notifications for order status changes
"""

from celery import shared_task
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta
import logging

from wasla.apps.orders.models import StockReservation, Order, RMA
from wasla.apps.orders.services.stock_reservation_service import StockReservationService
from wasla.config.celery import app

logger = logging.getLogger(__name__)


@shared_task
def auto_release_expired_stock_reservations():
    """
    Release expired stock reservations.
    
    Called periodically (every 5 minutes) to clean up reservations that have exceeded
    their TTL and prevent inventory from being locked indefinitely.
    
    Flow:
    1. Find all reserved/confirmed reservations with expires_at < now
    2. For each expired reservation:
       - Release the reservation (decrement inventory.reserved_quantity)
       - Mark status as 'expired'
       - Log the release
    3. Return count of released reservations
    
    Returns:
        dict: {
            'released_count': int,
            'failed_count': int,
            'timestamp': str,
        }
    """
    service = StockReservationService()
    
    try:
        result = service.auto_release_expired()
        logger.info(f"Released {result['released_count']} expired stock reservations")
        return result
    except Exception as e:
        logger.error(f"Error auto-releasing stock reservations: {str(e)}", exc_info=True)
        return {
            'released_count': 0,
            'failed_count': 0,
            'error': str(e),
        }


@shared_task
def send_order_notification(order_id, event_type, **kwargs):
    """
    Send notification email for order events.
    
    Events:
    - order_created: New order notification
    - order_paid: Payment confirmation
    - order_confirmed: Order processing started
    - order_shipped: Shipment notification with tracking
    - order_delivered: Delivery confirmation
    - order_cancelled: Cancellation notice
    - invoice_issued: Invoice available
    - rma_approved: Return RMA approved
    - rma_completed: Return completed with refund
    - refund_processed: Refund issued
    
    Args:
        order_id: Order ID
        event_type: Type of notification event
        **kwargs: Additional context (tracking_number, invoice_id, rma_id, etc.)
    
    Returns:
        dict: {'sent': bool, 'to': str, 'event': str}
    """
    try:
        order = Order.objects.get(id=order_id)
        
        # Import here to avoid circular imports
        from wasla.apps.orders.services.notification_service import OrderNotificationService
        
        notification_service = OrderNotificationService()
        notification_service.send_notification(order, event_type, **kwargs)
        
        logger.info(f"Sent {event_type} notification for order {order_id}")
        return {
            'sent': True,
            'to': order.customer_email,
            'event': event_type,
        }
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for notification")
        return {'sent': False, 'error': 'Order not found'}
    except Exception as e:
        logger.error(f"Error sending {event_type} notification for order {order_id}: {str(e)}", exc_info=True)
        return {'sent': False, 'error': str(e)}


@shared_task
def generate_invoice_pdf(invoice_id):
    """
    Generate PDF for issued invoice.
    
    Called asynchronously when invoice is issued to generate PDF and store locally.
    
    Args:
        invoice_id: Invoice ID
    
    Returns:
        dict: {'generated': bool, 'file_path': str, 'size_bytes': int}
    """
    try:
        from wasla.apps.orders.models import Invoice
        from wasla.apps.orders.services.invoice_service import InvoiceService
        
        invoice = Invoice.objects.get(id=invoice_id)
        service = InvoiceService()
        
        # Generate PDF
        pdf_bytes = service.generate_pdf(invoice)
        
        # Save to invoice.pdf_file
        from django.core.files.base import ContentFile
        filename = f"invoice_{invoice.invoice_number}.pdf"
        invoice.pdf_file.save(filename, ContentFile(pdf_bytes), save=True)
        
        logger.info(f"Generated PDF for invoice {invoice.invoice_number}")
        return {
            'generated': True,
            'file_path': invoice.pdf_file.name,
            'size_bytes': len(pdf_bytes),
        }
    except Exception as e:
        logger.error(f"Error generating PDF for invoice {invoice_id}: {str(e)}", exc_info=True)
        return {'generated': False, 'error': str(e)}


@shared_task
def process_refund(refund_id):
    """
    Process refund via payment gateway.
    
    Called after refund is created to submit to payment gateway.
    Updates RefundTransaction status and stores gateway response.
    
    Args:
        refund_id: RefundTransaction ID
    
    Returns:
        dict: {'processed': bool, 'status': str, 'gateway_ref': str}
    """
    try:
        from wasla.apps.orders.models import RefundTransaction
        from wasla.apps.orders.services.returns_service import RefundsService
        from wasla.apps.payments.gateway import PaymentGatewayClient
        
        refund = RefundTransaction.objects.get(id=refund_id)
        refunds_service = RefundsService()
        
        # Get payment gateway client (this depends on your implementation)
        gateway = PaymentGatewayClient(tenant_id=refund.tenant_id)
        
        # Process refund through gateway
        result = refunds_service.process_refund(refund, gateway)
        
        logger.info(f"Processed refund {refund.refund_id} with status {refund.status}")
        return {
            'processed': True,
            'status': refund.status,
            'gateway_ref': refund.gateway_response.get('refund_id', ''),
        }
    except Exception as e:
        logger.error(f"Error processing refund {refund_id}: {str(e)}", exc_info=True)
        return {'processed': False, 'error': str(e)}


@shared_task
def process_rma_return_received(rma_id):
    """
    Process return shipment received event.
    
    Called when return shipment is marked as received in warehouse.
    Triggers inspection workflow.
    
    Args:
        rma_id: RMA ID
    
    Returns:
        dict: {'processed': bool, 'rma_number': str}
    """
    try:
        from wasla.apps.orders.models import RMA
        from wasla.apps.orders.services.returns_service import ReturnsService
        
        rma = RMA.objects.get(id=rma_id)
        returns_service = ReturnsService()
        
        # Mark as received
        rma = returns_service.receive_return(rma)
        
        # Send notification
        send_order_notification.delay(rma.order_id, 'rma_received', rma_id=rma_id)
        
        logger.info(f"Processed return received for RMA {rma.rma_number}")
        return {
            'processed': True,
            'rma_number': rma.rma_number,
        }
    except RMA.DoesNotExist:
        logger.error(f"RMA {rma_id} not found")
        return {'processed': False, 'error': 'RMA not found'}
    except Exception as e:
        logger.error(f"Error processing RMA return received {rma_id}: {str(e)}", exc_info=True)
        return {'processed': False, 'error': str(e)}


@shared_task
def cleanup_abandoned_reservations():
    """
    Clean up abandoned stock reservations older than 24 hours.
    
    Releases very old expired reservations that haven't been cleaned up
    by the regular auto_release task.
    
    Returns:
        dict: {'cleaned_count': int}
    """
    try:
        cutoff_time = timezone.now() - timedelta(hours=24)
        abandoned = StockReservation.objects.filter(
            status__in=['reserved', 'confirmed'],
            expires_at__lt=cutoff_time,
        )
        
        count = abandoned.count()
        service = StockReservationService()
        
        for reservation in abandoned:
            service.release_reservation(reservation, reason='abandoned_auto_cleanup')
        
        logger.info(f"Cleaned up {count} abandoned stock reservations")
        return {'cleaned_count': count}
    except Exception as e:
        logger.error(f"Error cleaning up abandoned reservations: {str(e)}", exc_info=True)
        return {'cleaned_count': 0, 'error': str(e)}


@shared_task
def resync_rma_tracking(rma_id):
    """
    Resync RMA tracking status from carrier.
    
    Called periodically to poll carrier API for return shipment updates.
    
    Args:
        rma_id: RMA ID
    
    Returns:
        dict: {'synced': bool, 'status': str}
    """
    try:
        from wasla.apps.orders.models import RMA
        from wasla.apps.shipping.tracking_service import ShippingTrackingService
        
        rma = RMA.objects.get(id=rma_id)
        
        if not rma.return_tracking_number:
            return {'synced': False, 'error': 'No tracking number'}
        
        tracking_service = ShippingTrackingService()
        tracking_info = tracking_service.get_tracking_status(
            carrier=rma.return_carrier,
            tracking_number=rma.return_tracking_number,
        )
        
        # Update RMA status if tracking indicates delivery
        if tracking_info.get('status') == 'delivered':
            rma = ReturnsService().receive_return(rma)
        
        logger.info(f"Synced tracking for RMA {rma.rma_number}: {tracking_info.get('status')}")
        return {
            'synced': True,
            'status': tracking_info.get('status'),
        }
    except RMA.DoesNotExist:
        logger.error(f"RMA {rma_id} not found")
        return {'synced': False, 'error': 'RMA not found'}
    except Exception as e:
        logger.error(f"Error resyncing RMA tracking {rma_id}: {str(e)}", exc_info=True)
        return {'synced': False, 'error': str(e)}


# Celery Beat Schedule for periodic tasks
# Add to config/celery.py:
"""
from celery.schedules import crontab

app.conf.beat_schedule = {
    'auto-release-expired-reservations': {
        'task': 'wasla.apps.orders.tasks.auto_release_expired_stock_reservations',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'cleanup-abandoned-reservations': {
        'task': 'wasla.apps.orders.tasks.cleanup_abandoned_reservations',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
    },
}
"""
