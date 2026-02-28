"""
Notification service for billing events.

Handles sending emails and SMS for:
- Invoice issued/overdue
- Payment received/failed
- Grace period expiring
- Subscription suspended
- Payment reminders
"""

import logging
from datetime import timezone as tz
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class BillingNotificationService:
    """Service for sending billing-related notifications."""
    
    SENDER_EMAIL = getattr(settings, 'DEFAULT_FROM_EMAIL', 'billing@wasla.sa')
    SUPPORT_EMAIL = getattr(settings, 'SUPPORT_EMAIL', 'support@wasla.sa')
    SUPPORT_PHONE = getattr(settings, 'SUPPORT_PHONE', '+966-50-XXX-XXXX')
    
    @classmethod
    def send_invoice_issued(cls, invoice):
        """Send invoice issued notification."""
        try:
            subscription = invoice.subscription
            billing_cycle = invoice.billing_cycle
            
            context = {
                'merchant_name': subscription.tenant.name,
                'invoice_number': invoice.number,
                'invoice_date': invoice.issued_date,
                'due_date': invoice.due_date,
                'invoice_status': invoice.get_status_display(),
                'period_start': billing_cycle.period_start,
                'period_end': billing_cycle.period_end,
                'currency': subscription.currency,
                'subtotal': F"{billing_cycle.subtotal:.2f}",
                'tax': f"{billing_cycle.tax:.2f}",
                'discount': f"{billing_cycle.discount:.2f}",
                'total': f"{invoice.total:.2f}",
                'plan_name': subscription.plan.name,
                'billing_day': subscription.billing_cycle_anchor,
                'dashboard_url': settings.DASHBOARD_URL,
                'invoice_id': invoice.id,
            }
            
            # Get invoice items if needed
            items = []
            for item in subscription.items.all():
                items.append({
                    'name': item.name,
                    'amount': f"{item.price:.2f}"
                })
            if items:
                context['items'] = items
            
            subject = f"Invoice #{invoice.number} - Wasla"
            body = render_to_string('subscriptions/emails/invoice_issued.txt', context)
            
            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=cls.SENDER_EMAIL,
                to=[subscription.tenant.contact_email],
            )
            email.send(fail_silently=False)
            
            logger.info(f"Invoice issued email sent: {invoice.number} to {subscription.tenant.contact_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send invoice issued email for {invoice.number}: {str(e)}")
            return False
    
    @classmethod
    def send_payment_received(cls, invoice, payment_date, payment_method, reference_id):
        """Send payment received notification."""
        try:
            subscription = invoice.subscription
            
            context = {
                'merchant_name': subscription.tenant.name,
                'invoice_number': invoice.number,
                'payment_date': payment_date,
                'amount_paid': f"{invoice.amount_paid:.2f}",
                'payment_method': payment_method,
                'reference_id': reference_id,
                'currency': subscription.currency,
                'plan_name': subscription.plan.name,
                'next_billing_date': subscription.next_billing_date,
                'dashboard_url': settings.DASHBOARD_URL,
            }
            
            subject = f"Payment Received - Invoice #{invoice.number}"
            body = render_to_string('subscriptions/emails/payment_received.txt', context)
            
            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=cls.SENDER_EMAIL,
                to=[subscription.tenant.contact_email],
            )
            email.send(fail_silently=False)
            
            logger.info(f"Payment received email sent: {invoice.number} to {subscription.tenant.contact_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send payment received email for {invoice.number}: {str(e)}")
            return False
    
    @classmethod
    def send_grace_period_expiring(cls, subscription, days_remaining):
        """Send grace period expiring notification."""
        try:
            # Get the invoice that triggered grace period
            from .models_billing import Invoice
            invoice = Invoice.objects.filter(
                subscription=subscription,
                status__in=['overdue', 'partial']
            ).order_by('-issued_date').first()
            
            if not invoice:
                logger.warning(f"No overdue invoice found for grace period notification: {subscription.id}")
                return False
            
            context = {
                'merchant_name': subscription.tenant.name,
                'invoice_number': invoice.number,
                'amount_due': f"{invoice.amount_due:.2f}",
                'grace_until_date': subscription.grace_until.date(),
                'days_remaining': days_remaining,
                'currency': subscription.currency,
                'payment_url': f"{settings.DASHBOARD_URL}/invoices/{invoice.id}/pay/",
                'dashboard_url': settings.DASHBOARD_URL,
                'invoice_id': invoice.id,
            }
            
            subject = f"⚠️  Action Required: Payment Due - Invoice #{invoice.number}"
            body = render_to_string('subscriptions/emails/grace_period_expiring.txt', context)
            
            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=cls.SENDER_EMAIL,
                to=[subscription.tenant.contact_email],
            )
            email.send(fail_silently=False)
            
            logger.info(f"Grace period expiring email sent: {subscription.id} to {subscription.tenant.contact_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send grace period expiring email for {subscription.id}: {str(e)}")
            return False
    
    @classmethod
    def send_store_suspended(cls, subscription):
        """Send store suspension notification."""
        try:
            # Get the invoice that caused suspension
            from .models_billing import Invoice
            invoice = Invoice.objects.filter(
                subscription=subscription,
                status__in=['overdue', 'partial']
            ).order_by('-issued_date').first()
            
            if not invoice:
                logger.warning(f"No overdue invoice found for suspension notification: {subscription.id}")
                return False
            
            suspension_duration = timezone.now() - subscription.suspended_at
            days_suspended = suspension_duration.days
            days_overdue = (timezone.now().date() - invoice.due_date).days
            
            context = {
                'merchant_name': subscription.tenant.name,
                'suspension_date': subscription.suspended_at.date(),
                'days_suspended': days_suspended,
                'invoice_number': invoice.number,
                'amount_due': f"{invoice.amount_due:.2f}",
                'currency': subscription.currency,
                'original_due_date': invoice.due_date,
                'days_overdue': max(0, days_overdue),
                'payment_url': f"{settings.DASHBOARD_URL}/invoices/{invoice.id}/pay/",
                'dashboard_url': settings.DASHBOARD_URL,
            }
            
            subject = f"🚨 URGENT: Your Store Has Been Suspended - Immediate Action Required"
            body = render_to_string('subscriptions/emails/store_suspended.txt', context)
            
            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=cls.SENDER_EMAIL,
                to=[subscription.tenant.contact_email],
            )
            email.send(fail_silently=False)
            
            logger.info(f"Store suspended email sent: {subscription.id} to {subscription.tenant.contact_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send store suspended email for {subscription.id}: {str(e)}")
            return False
    
    @classmethod
    def send_payment_failed(cls, invoice, error_message):
        """Send payment failed notification."""
        try:
            subscription = invoice.subscription
            
            context = {
                'merchant_name': subscription.tenant.name,
                'invoice_number': invoice.number,
                'amount_due': f"{invoice.amount_due:.2f}",
                'currency': subscription.currency,
                'error_reason': error_message,
                'due_date': invoice.due_date,
                'days_until_due': (invoice.due_date - timezone.now().date()).days,
                'dashboard_url': settings.DASHBOARD_URL,
                'payment_url': f"{settings.DASHBOARD_URL}/invoices/{invoice.id}/pay/",
                'support_email': cls.SUPPORT_EMAIL,
                'support_phone': cls.SUPPORT_PHONE,
            }
            
            subject = f"Payment Failed - Invoice #{invoice.number} - Action Needed"
            body = f"""Dear {context['merchant_name']},

We attempted to charge your payment method for invoice #{context['invoice_number']}, but the payment failed.

FAILURE REASON
==============
{context['error_reason']}

INVOICE DETAILS
===============
Invoice Number: {context['invoice_number']}
Amount Due: {context['currency']} {context['amount_due']}
Due Date: {context['due_date']}
Days Until Due: {context['days_until_due']}

NEXT STEPS
==========
1. Update your payment method:
   {context['dashboard_url']}/payment-methods/

2. Pay the invoice:
   {context['payment_url']}

3. We will automatically retry payment in 3 days.

NEED HELP?
==========
Email: {cls.SUPPORT_EMAIL}
Phone: {cls.SUPPORT_PHONE}

Best regards,
Wasla Billing Team"""
            
            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=cls.SENDER_EMAIL,
                to=[subscription.tenant.contact_email],
            )
            email.send(fail_silently=False)
            
            logger.info(f"Payment failed email sent: {invoice.number} to {subscription.tenant.contact_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send payment failed email for {invoice.number}: {str(e)}")
            return False
    
    @classmethod
    def send_dunning_attempt_notification(cls, subscription, attempt_number, next_retry=None):
        """Send dunning attempt notification."""
        try:
            from .models_billing import Invoice
            invoice = Invoice.objects.filter(
                subscription=subscription,
                status__in=['overdue', 'partial']
            ).order_by('-issued_date').first()
            
            if not invoice:
                return False
            
            if attempt_number == 1:
                message = f"Your payment method failed. We'll retry automatically in 3 days."
            elif attempt_number == 2:
                message = f"Payment retry failed again. Next attempt in 5 days."
            elif attempt_number == 3:
                message = f"Multiple payment attempts unsuccessful. Final attempt in 7 days."
            else:
                message = f"Final payment attempt. If this fails, we'll suspend your store."
            
            context = {
                'merchant_name': subscription.tenant.name,
                'invoice_number': invoice.number,
                'amount_due': f"{invoice.amount_due:.2f}",
                'currency': subscription.currency,
                'attempt_number': attempt_number,
                'message': message,
                'next_retry': next_retry,
                'dashboard_url': settings.DASHBOARD_URL,
                'payment_url': f"{settings.DASHBOARD_URL}/invoices/{invoice.id}/pay/",
            }
            
            subject = f"Payment Attempt #{attempt_number} - Invoice #{invoice.number}"
            body = f"""Dear {context['merchant_name']},

Your automatic payment attempt #{context['attempt_number']} for invoice #{context['invoice_number']} failed.

{context['message']}

INVOICE DETAILS
===============
Invoice Number: {context['invoice_number']}
Amount Due: {context['currency']} {context['amount_due']}

ACTION REQUIRED
===============
Please update your payment method or pay manually to avoid service suspension:
{context['payment_url']}

Best regards,
Wasla Billing Team"""
            
            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=cls.SENDER_EMAIL,
                to=[subscription.tenant.contact_email],
            )
            email.send(fail_silently=False)
            
            logger.info(f"Dunning notification sent: {subscription.id} attempt #{attempt_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send dunning notification for {subscription.id}: {str(e)}")
            return False
