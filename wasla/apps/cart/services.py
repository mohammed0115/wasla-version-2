"""Abandoned cart tracking and recovery services."""
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.db.models import Q, F
from apps.cart.models import Cart
from apps.stores.models import Store


class AbandonedCartService:
    """Service for tracking and managing abandoned carts."""

    ABANDONED_THRESHOLD_HOURS = 24
    REMINDER_THRESHOLD_HOURS = 24

    @staticmethod
    def get_abandoned_carts(store=None, hours=ABANDONED_THRESHOLD_HOURS):
        """
        Get all abandoned carts.

        Args:
            store: Store instance (optional, if None returns all stores)
            hours: Hours since last activity to consider abandoned

        Returns:
            QuerySet of abandoned Cart instances
        """
        threshold = timezone.now() - timedelta(hours=hours)

        carts = Cart.objects.filter(
            updated_at__lt=threshold,
            abandoned_at__isnull=True,  # Not yet marked as abandoned
        ).exclude(items__isnull=True)  # Has items

        if store:
            carts = carts.filter(store_id=store.id)

        # Mark as abandoned
        carts.update(abandoned_at=timezone.now())

        return carts

    @staticmethod
    def get_abandoned_carts_for_reminder(store=None, hours=ABANDONED_THRESHOLD_HOURS):
        """
        Get abandoned carts that haven't had reminder sent yet.

        Args:
            store: Store instance (optional)
            hours: Hours since abandoned to send reminder

        Returns:
            QuerySet of Cart instances ready for reminder
        """
        reminder_threshold = timezone.now() - timedelta(hours=hours)

        carts = Cart.objects.filter(
            abandoned_at__isnull=False,
            abandoned_at__lt=reminder_threshold,
            reminder_sent=False,
        ).exclude(items__isnull=True)

        if store:
            carts = carts.filter(store_id=store.id)

        return carts

    @staticmethod
    def get_abandoned_cart_stats(store=None):
        """Get statistics about abandoned carts."""
        threshold = timezone.now() - timedelta(hours=AbandonedCartService.ABANDONED_THRESHOLD_HOURS)

        carts = Cart.objects.filter(
            updated_at__lt=threshold,
        ).exclude(items__isnull=True)

        if store:
            carts = carts.filter(store_id=store.id)

        total_carts = carts.count()
        total_value = sum(
            sum(
                item.unit_price_snapshot * item.quantity
                for item in cart.items.all()
            )
            for cart in carts
        )

        return {
            "total_abandoned_carts": total_carts,
            "total_abandoned_value": Decimal(str(total_value)),
            "average_cart_value": Decimal(str(total_value / total_carts)) if total_carts > 0 else 0,
            "threshold_hours": AbandonedCartService.ABANDONED_THRESHOLD_HOURS,
        }

    @staticmethod
    def mark_reminder_sent(cart):
        """Mark reminder as sent for a cart."""
        cart.reminder_sent = True
        cart.reminder_sent_at = timezone.now()
        cart.save(update_fields=["reminder_sent", "reminder_sent_at"])

    @staticmethod
    def recover_cart(cart):
        """Reset abandoned cart status for recovery."""
        cart.abandoned_at = None
        cart.reminder_sent = False
        cart.reminder_sent_at = None
        cart.updated_at = timezone.now()
        cart.save(update_fields=["abandoned_at", "reminder_sent", "reminder_sent_at", "updated_at"])


class AbandonedCartRecoveryEmailService:
    """Service to send abandoned cart recovery emails."""

    @staticmethod
    def render_recovery_email(cart):
        """Render abandoned cart recovery email."""
        items_html = ""
        total_value = Decimal("0.00")

        for item in cart.items.all():
            item_total = item.unit_price_snapshot * item.quantity
            total_value += item_total
            items_html += f"""
            <tr style="border-bottom: 1px solid #e0e0e0;">
                <td style="padding: 12px;">{item.product.name}</td>
                <td style="padding: 12px; text-align: center;">{item.quantity}</td>
                <td style="padding: 12px; text-align: right;">{item.unit_price_snapshot} SAR</td>
                <td style="padding: 12px; text-align: right;">{item_total} SAR</td>
            </tr>
            """

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; background-color: #f5f5f5; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: white; border-radius: 8px; overflow: hidden; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }}
                .content {{ padding: 30px; }}
                .total {{ font-size: 18px; font-weight: 600; color: #667eea; }}
                .cta-button {{ display: inline-block; background-color: #667eea; color: white; padding: 12px 30px; border-radius: 4px; text-decoration: none; margin: 20px 0; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th {{ background-color: #f5f5f5; padding: 12px; text-align: left; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>You left something behind! 🛒</h1>
                </div>
                <div class="content">
                    <p>We noticed you left some items in your cart. Don't miss out!</p>

                    <div style="background-color: #f9f9f9; padding: 15px; border-radius: 4px; margin: 20px 0;">
                        <table>
                            <thead>
                                <tr>
                                    <th>Product</th>
                                    <th>Qty</th>
                                    <th>Price</th>
                                    <th>Total</th>
                                </tr>
                            </thead>
                            <tbody>
                                {items_html}
                            </tbody>
                        </table>
                        <div style="padding-top: 15px; border-top: 1px solid #e0e0e0; text-align: right;">
                            <span class="total">Cart Total: {total_value} SAR</span>
                        </div>
                    </div>

                    <p style="text-align: center;">
                        <a href="#" class="cta-button">Complete Your Purchase</a>
                    </p>

                    <p style="font-size: 12px; color: #666;">
                        This cart will expire in 7 days. Secure your items before they're gone!
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        return html_content

    @staticmethod
    def send_recovery_email(cart):
        """Send recovery email for abandoned cart."""
        try:
            from apps.emails.domain.types import EmailMessage
            from apps.emails.tasks import enqueue_send_email
            from apps.emails.application.use_cases.send_email import SendEmailUseCase

            recipient_email = None
            if cart.user:
                recipient_email = cart.user.email
            elif cart.session_key:
                # For guest carts, you might have email stored elsewhere
                # This is a placeholder
                return False

            if not recipient_email:
                return False

            html_content = AbandonedCartRecoveryEmailService.render_recovery_email(cart)

            message = EmailMessage(
                sender="noreply@wasla.sa",
                recipient=recipient_email,
                subject="You left items in your cart! 🛒",
                text_content="Complete your purchase",
                html_content=html_content,
            )

            email_log = SendEmailUseCase.create_email_log(
                tenant_id=None,
                recipient=recipient_email,
                subject=message.subject,
                body=html_content,
            )

            enqueue_send_email(
                email_log_id=email_log.id,
                tenant_id=None,
                provider="smtp",
                message=message,
            )

            # Mark reminder as sent
            AbandonedCartService.mark_reminder_sent(cart)

            return True

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send abandoned cart email for cart {cart.id}: {str(e)}")
            return False
