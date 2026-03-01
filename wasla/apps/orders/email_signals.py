"""Order confirmation email signals."""
from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.mail import send_mail
from django.utils import timezone
from apps.orders.models import Order
from apps.orders.email_templates import (
    render_order_confirmation_email,
    render_order_shipped_email,
)
from apps.shipping.models import Shipment


@receiver(post_save, sender=Order)
def send_order_confirmation_email(sender, instance, created, **kwargs):
    """Send confirmation email after order is placed and paid."""
    if instance.status not in ['processing', 'confirmed', 'paid']:
        return
    if instance.payment_status != "paid":
        return
    if instance.confirmation_email_sent_at:
        return
    order_id = instance.id

    def _send():
        order = Order.objects.filter(
            id=order_id,
            confirmation_email_sent_at__isnull=True,
            payment_status="paid",
        ).first()
        if not order:
            return
        send_order_confirmation(order)
        Order.objects.filter(id=order_id, confirmation_email_sent_at__isnull=True).update(
            confirmation_email_sent_at=timezone.now()
        )

    transaction.on_commit(_send)


@receiver(post_save, sender=Shipment)
def send_shipment_notification_email(sender, instance, created, **kwargs):
    """Send shipping notification when shipment is created."""
    if instance.tracking_number and not instance.notification_sent_at:
        shipment_id = instance.id

        def _send():
            shipment = Shipment.objects.select_related("order").filter(
                id=shipment_id,
                notification_sent_at__isnull=True,
            ).first()
            if not shipment or not shipment.tracking_number:
                return
            send_shipment_email(shipment)
            Shipment.objects.filter(id=shipment_id, notification_sent_at__isnull=True).update(
                notification_sent_at=timezone.now()
            )

        transaction.on_commit(_send)


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
