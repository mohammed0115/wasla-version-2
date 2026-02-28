"""Order confirmation email signals."""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.mail import send_mail
from apps.orders.models import Order
from apps.orders.email_templates import (
    render_order_confirmation_email,
    render_order_shipped_email,
)
from apps.shipping.models import Shipment


@receiver(post_save, sender=Order)
def send_order_confirmation_email(sender, instance, created, **kwargs):
    """Send confirmation email after order is placed and paid."""
    # Only send when order status changes to 'processing' (after payment)
    if not created and instance.status in ['processing', 'confirmed']:
        # Check if email already sent (use a flag to avoid duplicates)
        if not getattr(instance, '_confirmation_email_sent', False):
            send_order_confirmation(instance)
            instance._confirmation_email_sent = True


@receiver(post_save, sender=Shipment)
def send_shipment_notification_email(sender, instance, created, **kwargs):
    """Send shipping notification when shipment is created."""
    if created and instance.tracking_number:
        send_shipment_email(instance)


def send_order_confirmation(order):
    """
    Send order confirmation email to customer.

    Args:
        order: Order instance
    """
    try:
        from apps.emails.domain.types import EmailMessage
        from apps.emails.tasks import enqueue_send_email
        from apps.emails.application.use_cases.send_email import SendEmailUseCase

        recipient_email = order.customer.email if hasattr(order, 'customer') and order.customer else order.email
        store = order.store if hasattr(order, 'store') else None

        html_content = render_order_confirmation_email(order)

        # Create email message
        message = EmailMessage(
            sender="noreply@wasla.sa",
            recipient=recipient_email,
            subject=f"Order Confirmation #{order.id}",
            text_content=f"Order #{order.id} has been confirmed",
            html_content=html_content,
            reply_to=store.email if store and hasattr(store, 'email') else None,
        )

        # Create email log and enqueue
        email_log = SendEmailUseCase.create_email_log(
            tenant_id=order.tenant_id if hasattr(order, 'tenant_id') else None,
            recipient=recipient_email,
            subject=message.subject,
            body=html_content,
        )

        # Enqueue for sending
        enqueue_send_email(
            email_log_id=email_log.id,
            tenant_id=order.tenant_id if hasattr(order, 'tenant_id') else None,
            provider="smtp",
            message=message,
        )

    except Exception as e:
        # Log error but don't crash the order process
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send order confirmation email for order {order.id}: {str(e)}")


def send_shipment_email(shipment):
    """
    Send shipment notification email.

    Args:
        shipment: Shipment instance
    """
    try:
        from apps.emails.domain.types import EmailMessage
        from apps.emails.tasks import enqueue_send_email
        from apps.emails.application.use_cases.send_email import SendEmailUseCase

        order = shipment.order
        recipient_email = order.customer.email if hasattr(order, 'customer') and order.customer else order.email

        html_content = render_order_shipped_email(order, shipment)

        message = EmailMessage(
            sender="noreply@wasla.sa",
            recipient=recipient_email,
            subject=f"Your Order #{order.id} Has Shipped - Tracking #{shipment.tracking_number}",
            text_content=f"Order #{order.id} has been shipped with tracking {shipment.tracking_number}",
            html_content=html_content,
        )

        # Create email log and enqueue
        email_log = SendEmailUseCase.create_email_log(
            tenant_id=order.tenant_id if hasattr(order, 'tenant_id') else None,
            recipient=recipient_email,
            subject=message.subject,
            body=html_content,
        )

        # Enqueue for sending
        enqueue_send_email(
            email_log_id=email_log.id,
            tenant_id=order.tenant_id if hasattr(order, 'tenant_id') else None,
            provider="smtp",
            message=message,
        )

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send shipment email for shipment {shipment.id}: {str(e)}")
