"""
Billing service layer for recurring SaaS billing.

Handles:
- Subscription lifecycle management
- Billing cycle creation and charging
- Proration for upgrades/downgrades
- Dunning (payment retry) flow
- Webhook synchronization
"""

from decimal import Decimal
from datetime import datetime, timedelta, date
from typing import Optional, Dict, Any, Tuple
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
import logging

from .models_billing import (
    Subscription, SubscriptionItem, BillingCycle, Invoice,
    DunningAttempt, PaymentEvent, PaymentMethod, BillingPlan
)

logger = logging.getLogger(__name__)


class SubscriptionService:
    """Manages subscription lifecycle and state transitions."""
    
    @staticmethod
    def create_subscription(
        tenant,
        plan: BillingPlan,
        payment_method: PaymentMethod,
        billing_cycle_anchor: int = 1,
        currency: str = 'SAR',
        idempotency_key: str = None
    ) -> Subscription:
        """
        Create a new subscription for a tenant.
        
        Args:
            tenant: Tenant instance
            plan: BillingPlan to subscribe to
            payment_method: PaymentMethod for billing
            billing_cycle_anchor: Day of month for renewal (1-28)
            currency: Currency code (e.g., 'SAR')
            idempotency_key: For idempotent creation
        
        Returns:
            Created Subscription instance
        """
        # Ensure idempotency
        if idempotency_key:
            try:
                return Subscription.objects.filter(
                    tenant=tenant,
                    plan=plan
                ).latest('created_at')
            except Subscription.DoesNotExist:
                pass
        
        # Calculate next billing date
        today = date.today()
        next_billing = date(today.year, today.month, billing_cycle_anchor)
        if next_billing <= today:
            # Move to next month if anchor date has passed
            if today.month == 12:
                next_billing = date(today.year + 1, 1, billing_cycle_anchor)
            else:
                next_billing = date(today.year, today.month + 1, billing_cycle_anchor)
        
        with transaction.atomic():
            # Create subscription
            subscription = Subscription.objects.create(
                tenant=tenant,
                plan=plan,
                currency=currency,
                billing_cycle_anchor=billing_cycle_anchor,
                next_billing_date=next_billing,
                state='active'
            )
            
            # Assign payment method
            payment_method.subscription = subscription
            payment_method.save(update_fields=['subscription'])
            
            logger.info(
                f"Created subscription {subscription.id} for tenant {tenant.id} "
                f"on plan {plan.name}"
            )
        
        return subscription
    
    @staticmethod
    def change_plan(
        subscription: Subscription,
        new_plan: BillingPlan,
        idempotency_key: str = None
    ) -> Subscription:
        """
        Upgrade or downgrade subscription plan with proration.
        
        Args:
            subscription: Current subscription
            new_plan: New plan to switch to
            idempotency_key: For idempotent operations
        
        Returns:
            Updated subscription
        """
        old_plan = subscription.plan
        
        with transaction.atomic():
            # Calculate proration
            proration_amount = BillingService.calculate_proration(
                subscription=subscription,
                old_plan=old_plan,
                new_plan=new_plan
            )
            
            # Update subscription
            subscription.plan = new_plan
            subscription.save(update_fields=['plan', 'updated_at'])
            
            # Create proration credit or charge
            if proration_amount != 0:
                billing_cycle = BillingService.get_current_billing_cycle(subscription)
                if billing_cycle:
                    billing_cycle.proration_total = proration_amount
                    billing_cycle.proration_reason = f"Plan change: {old_plan.name} → {new_plan.name}"
                    billing_cycle.save()
                    logger.info(
                        f"Proration of {proration_amount} for subscription {subscription.id} "
                        f"on plan change"
                    )
            
            logger.info(
                f"Changed subscription {subscription.id} from {old_plan.name} "
                f"to {new_plan.name}"
            )
        
        return subscription
    
    @staticmethod
    def cancel_subscription(
        subscription: Subscription,
        reason: str = None,
        immediately: bool = False
    ) -> Subscription:
        """
        Cancel a subscription immediately or at end of billing period.
        
        Args:
            subscription: Subscription to cancel
            reason: Cancellation reason
            immediately: If True, cancel now; else cancel at period end
        
        Returns:
            Updated subscription
        """
        with transaction.atomic():
            subscription.state = 'cancelled'
            subscription.cancelled_at = timezone.now()
            subscription.cancellation_reason = reason or 'Merchant cancelled'
            subscription.save()
            
            # If immediate cancellation, also suspend store
            if immediately:
                tenant = subscription.tenant
                tenant.is_active = False
                tenant.save(update_fields=['is_active'])
                logger.warning(
                    f"Immediately cancelled subscription {subscription.id} "
                    f"for tenant {tenant.id}"
                )
            else:
                logger.info(
                    f"Cancelled subscription {subscription.id} "
                    f"at end of billing period"
                )
        
        return subscription
    
    @staticmethod
    def suspend_subscription(
        subscription: Subscription,
        reason: str = None
    ) -> Subscription:
        """
        Suspend a subscription (e.g., due to non-payment).
        
        Args:
            subscription: Subscription to suspend
            reason: Suspension reason
        
        Returns:
            Updated subscription
        """
        with transaction.atomic():
            subscription.state = 'suspended'
            subscription.suspended_at = timezone.now()
            subscription.suspension_reason = reason or 'Non-payment'
            subscription.save()
            
            # Suspend the store
            tenant = subscription.tenant
            tenant.is_active = False
            tenant.save(update_fields=['is_active'])
            
            logger.warning(
                f"Suspended subscription {subscription.id} and store {tenant.id}: {reason}"
            )
        
        return subscription
    
    @staticmethod
    def reactivate_subscription(subscription: Subscription) -> Subscription:
        """
        Reactivate a suspended subscription after payment received.
        
        Args:
            subscription: Suspended subscription
        
        Returns:
            Updated subscription
        """
        with transaction.atomic():
            subscription.state = 'active'
            subscription.suspended_at = None
            subscription.suspension_reason = ''
            subscription.save()
            
            # Reactivate the store
            tenant = subscription.tenant
            tenant.is_active = True
            tenant.save(update_fields=['is_active'])
            
            logger.info(
                f"Reactivated subscription {subscription.id} and store {tenant.id}"
            )
        
        return subscription


class BillingService:
    """Handles billing cycles, invoices, and charging logic."""
    
    @staticmethod
    def get_current_billing_cycle(subscription: Subscription) -> Optional[BillingCycle]:
        """Get the current open billing cycle."""
        return BillingCycle.objects.filter(
            subscription=subscription,
            status__in=['pending', 'billed']
        ).first()
    
    @staticmethod
    def create_billing_cycle(
        subscription: Subscription,
        period_start: date,
        period_end: date,
        idempotency_key: str = None
    ) -> BillingCycle:
        """
        Create a new billing cycle.
        
        Args:
            subscription: Subscription for this cycle
            period_start: Start date of cycle
            period_end: End date of cycle
            idempotency_key: For idempotency
        
        Returns:
            Created BillingCycle
        """
        # Check for existing cycle (idempotency)
        existing = BillingCycle.objects.filter(
            subscription=subscription,
            period_end=period_end
        ).first()
        
        if existing:
            logger.info(
                f"Billing cycle already exists for subscription {subscription.id} "
                f"ending {period_end}"
            )
            return existing
        
        with transaction.atomic():
            # Create billing cycle
            billing_cycle = BillingCycle.objects.create(
                subscription=subscription,
                period_start=period_start,
                period_end=period_end,
                invoice_date=timezone.now().date(),
                due_date=period_end + timedelta(days=14)  # 14-day payment term
            )
            
            # Calculate amounts
            subtotal = subscription.plan.price
            discount = Decimal('0')
            tax = subtotal * Decimal('0.15')  # 15% VAT for Saudi Arabia
            total = subtotal - discount + tax
            
            billing_cycle.subtotal = subtotal
            billing_cycle.discount = discount
            billing_cycle.tax = tax
            billing_cycle.total = total
            billing_cycle.save()
            
            logger.info(
                f"Created billing cycle {billing_cycle.id} for subscription {subscription.id}"
            )
        
        return billing_cycle
    
    @staticmethod
    def calculate_proration(
        subscription: Subscription,
        old_plan: BillingPlan,
        new_plan: BillingPlan
    ) -> Decimal:
        """
        Calculate proration amount for plan change.
        
        Formula:
            daily_rate_new = new_plan.price / days_in_cycle
            daily_rate_old = old_plan.price / days_in_cycle
            remaining_days = days_until_next_billing
            proration = (daily_rate_new - daily_rate_old) * remaining_days
        
        Args:
            subscription: Subscription
            old_plan: Current plan
            new_plan: New plan
        
        Returns:
            Proration amount (positive = merchant owes, negative = credit)
        """
        today = date.today()
        next_billing = subscription.next_billing_date
        
        # Days remaining in current cycle
        if next_billing > today:
            days_remaining = (next_billing - today).days
        else:
            return Decimal('0')
        
        # Assuming 30-day billing cycles
        days_in_cycle = 30
        
        daily_old = old_plan.price / Decimal(days_in_cycle)
        daily_new = new_plan.price / Decimal(days_in_cycle)
        
        # Proration = (new_daily - old_daily) * remaining_days
        proration = (daily_new - daily_old) * Decimal(days_remaining)
        
        return proration.quantize(Decimal('0.01'))
    
    @staticmethod
    def create_invoice(
        billing_cycle: BillingCycle,
        idempotency_key: str = None
    ) -> Invoice:
        """
        Create an invoice for a billing cycle.
        
        Args:
            billing_cycle: BillingCycle to invoice
            idempotency_key: For idempotency
        
        Returns:
            Created Invoice
        """
        # Check for existing invoice (idempotency)
        if billing_cycle.invoice:
            logger.info(
                f"Invoice already exists for billing cycle {billing_cycle.id}"
            )
            return billing_cycle.invoice
        
        with transaction.atomic():
            # Generate invoice number
            invoice_number = BillingService._generate_invoice_number(
                billing_cycle.subscription.tenant_id
            )
            
            # Create invoice
            invoice = Invoice.objects.create(
                number=invoice_number,
                billing_cycle=billing_cycle,
                subscription=billing_cycle.subscription,
                subtotal=billing_cycle.subtotal,
                tax=billing_cycle.tax,
                discount=billing_cycle.discount,
                total=billing_cycle.total,
                amount_due=billing_cycle.total,
                due_date=billing_cycle.due_date,
                idempotency_key=idempotency_key or f"invoice_{invoice_number}"
            )
            
            billing_cycle.status = 'billed'
            billing_cycle.save(update_fields=['status'])
            
            logger.info(
                f"Created invoice {invoice.number} for subscription {billing_cycle.subscription.id}"
            )
        
        return invoice
    
    @staticmethod
    def _generate_invoice_number(tenant_id: int) -> str:
        """Generate unique invoice number."""
        from django.db.models import Max
        from datetime import datetime
        
        year_month = datetime.now().strftime('%Y%m')
        
        # Get next sequence for this month
        latest = Invoice.objects.filter(
            number__startswith=year_month
        ).aggregate(max_num=Max('number'))
        
        sequence = 1
        if latest['max_num']:
            try:
                last_seq = int(latest['max_num'][-4:])
                sequence = last_seq + 1
            except ValueError:
                sequence = 1
        
        return f"INV-{year_month}-{sequence:04d}"
    
    @staticmethod
    def record_payment(
        invoice: Invoice,
        amount: Decimal,
        provider_payment_id: str
    ) -> Invoice:
        """
        Record a payment against an invoice.
        
        Args:
            invoice: Invoice being paid
            amount: Amount paid
            provider_payment_id: Payment ID from provider
        
        Returns:
            Updated invoice
        """
        with transaction.atomic():
            invoice.amount_paid += amount
            invoice.amount_due = invoice.total - invoice.amount_paid
            
            if invoice.amount_due <= 0:
                invoice.status = 'paid'
                invoice.paid_date = timezone.now().date()
                
                # Update subscription state to active
                subscription = invoice.subscription
                if subscription.state in ['past_due', 'grace']:
                    subscription.state = 'active'
                    subscription.grace_until = None
                    subscription.save()
            elif invoice.amount_paid > 0:
                invoice.status = 'partial'
            
            invoice.save()
            
            logger.info(
                f"Recorded payment of {amount} for invoice {invoice.number}"
            )
        
        return invoice


class DunningService:
    """Manages payment retry (dunning) flow for failed invoices."""
    
    # Retry schedule: days before next attempt
    RETRY_SCHEDULE = {
        1: 3,      # First retry: 3 days
        2: 5,      # Second retry: 5 days  
        3: 7,      # Third retry: 7 days
        4: 14,     # Fourth retry: 14 days
    }
    
    @staticmethod
    def start_dunning(invoice: Invoice) -> DunningAttempt:
        """
        Initiate dunning flow for a failed invoice.
        
        Args:
            invoice: Invoice with failed payment
        
        Returns:
            First DunningAttempt
        """
        with transaction.atomic():
            # Mark invoice as overdue
            invoice.status = 'overdue'
            invoice.save(update_fields=['status'])
            
            # Update subscription state to past_due
            subscription = invoice.subscription
            original_state = subscription.state
            subscription.state = 'past_due'
            subscription.save(update_fields=['state', 'updated_at'])
            
            # Create first dunning attempt (immediate)
            attempt = DunningAttempt.objects.create(
                invoice=invoice,
                subscription=subscription,
                attempt_number=1,
                strategy='exponential',
                scheduled_for=timezone.now(),
                status='pending'
            )
            
            logger.warning(
                f"Started dunning flow for invoice {invoice.number} "
                f"(subscription {subscription.id})"
            )
        
        return attempt
    
    @staticmethod
    def process_dunning_attempt(attempt: DunningAttempt) -> bool:
        """
        Execute a dunning attempt (retry charge).
        
        Args:
            attempt: DunningAttempt to process
        
        Returns:
            True if payment succeeded, False if failed
        """
        with transaction.atomic():
            attempt.status = 'in_progress'
            attempt.attempted_at = timezone.now()
            attempt.save()
            
            invoice = attempt.invoice
            subscription = attempt.subscription
            
            try:
                # Attempt to charge payment method
                from apps.payments.services import PaymentService
                
                payment_method = subscription.payment_method
                if not payment_method or not payment_method.is_valid():
                    raise ValueError("Invalid or missing payment method")
                
                # Process charge (integrate with your payment provider)
                success = DunningService._process_payment(
                    invoice=invoice,
                    payment_method=payment_method
                )
                
                if success:
                    # Payment succeeded
                    attempt.status = 'success'
                    attempt.save()
                    
                    # Record payment on invoice
                    BillingService.record_payment(
                        invoice=invoice,
                        amount=invoice.amount_due,
                        provider_payment_id=f"dunning_{attempt.id}"
                    )
                    
                    # Reactivate subscription
                    SubscriptionService.reactivate_subscription(subscription)
                    
                    logger.info(
                        f"Dunning attempt {attempt.id} succeeded for invoice {invoice.number}"
                    )
                    return True
                else:
                    raise Exception("Payment processing failed")
            
            except Exception as e:
                attempt.status = 'failed'
                attempt.error_message = str(e)
                attempt.error_code = 'CHARGE_FAILED'
                
                # Schedule next retry
                next_attempt_number = attempt.attempt_number + 1
                if next_attempt_number in DunningService.RETRY_SCHEDULE:
                    days_until_next = DunningService.RETRY_SCHEDULE[next_attempt_number]
                    attempt.next_retry_at = timezone.now() + timedelta(days=days_until_next)
                    
                    # Create next attempt
                    DunningAttempt.objects.create(
                        invoice=invoice,
                        subscription=subscription,
                        attempt_number=next_attempt_number,
                        strategy='exponential',
                        scheduled_for=attempt.next_retry_at,
                        status='pending'
                    )
                    
                    logger.warning(
                        f"Dunning attempt {attempt.id} failed. Next retry scheduled for "
                        f"{days_until_next} days"
                    )
                else:
                    # Max retries exceeded - suspend subscription
                    logger.error(
                        f"Max dunning retries exceeded for invoice {invoice.number}. "
                        f"Suspending subscription {subscription.id}"
                    )
                    SubscriptionService.suspend_subscription(
                        subscription=subscription,
                        reason=f"Non-payment after {next_attempt_number - 1} dunning attempts"
                    )
                
                attempt.save()
                return False
    
    @staticmethod
    def _process_payment(invoice: Invoice, payment_method: PaymentMethod) -> bool:
        """
        Process actual payment charge.
        
        Integrate with your payment provider here.
        This is a stub - replace with actual implementation.
        """
        # TODO: Integrate with Stripe, PayMob, 2Checkout, etc.
        # For now, return False to simulate payment failure
        return False
    
    @staticmethod
    def add_grace_period(
        subscription: Subscription,
        days: int = 7
    ) -> Subscription:
        """
        Add grace period to subscription for payment.
        
        Args:
            subscription: Subscription to extend
            days: Number of grace period days
        
        Returns:
            Updated subscription
        """
        with transaction.atomic():
            subscription.state = 'grace'
            subscription.grace_until = timezone.now() + timedelta(days=days)
            subscription.save()
            
            logger.info(
                f"Added {days}-day grace period to subscription {subscription.id}"
            )
        
        return subscription


class WebhookService:
    """Handles webhook events from payment provider."""
    
    @staticmethod
    def handle_payment_event(
        event_type: str,
        provider_event_id: str,
        payload: Dict[str, Any]
    ) -> PaymentEvent:
        """
        Process webhook event from payment provider.
        Ensures idempotent processing using provider_event_id.
        
        Args:
            event_type: Type of event (e.g., 'payment.succeeded')
            provider_event_id: Unique ID from provider (idempotency key)
            payload: Full webhook payload
        
        Returns:
            ProcessedPaymentEvent
        """
        # Check if event already processed (idempotency)
        try:
            existing = PaymentEvent.objects.get(provider_event_id=provider_event_id)
            logger.info(
                f"Event {provider_event_id} already processed: {existing.status}"
            )
            return existing
        except PaymentEvent.DoesNotExist:
            pass
        
        with transaction.atomic():
            # Create payment event record
            event = PaymentEvent.objects.create(
                event_type=event_type,
                provider_event_id=provider_event_id,
                payload=payload,
                status='received'
            )
            
            try:
                # Route to appropriate handler
                if event_type == 'payment.succeeded':
                    WebhookService._handle_payment_succeeded(event, payload)
                
                elif event_type == 'payment.failed':
                    WebhookService._handle_payment_failed(event, payload)
                
                elif event_type == 'invoice.paid':
                    WebhookService._handle_invoice_paid(event, payload)
                
                elif event_type == 'invoice.payment_failed':
                    WebhookService._handle_invoice_payment_failed(event, payload)
                
                event.status = 'processed'
                event.processed_at = timezone.now()
                
            except Exception as e:
                event.status = 'failed'
                event.error_message = str(e)
                logger.exception(
                    f"Failed to process webhook {provider_event_id}: {str(e)}"
                )
            
            event.save()
        
        return event
    
    @staticmethod
    def _handle_payment_succeeded(event: PaymentEvent, payload: Dict):
        """Handle payment.succeeded webhook."""
        # Extract subscription and amount from payload
        # This depends on your payment provider's webhook format
        
        subscription_external_id = payload.get('customer_id')
        amount = Decimal(str(payload.get('amount', 0)))
        
        try:
            subscription = Subscription.objects.get(
                payment_method__provider_customer_id=subscription_external_id
            )
            event.subscription = subscription
            
            # Find related invoice and record payment
            invoice = Invoice.objects.filter(
                subscription=subscription,
                status__in=['issued', 'overdue', 'partial']
            ).latest('issued_date')
            
            event.invoice = invoice
            
            BillingService.record_payment(
                invoice=invoice,
                amount=amount,
                provider_payment_id=payload.get('payment_id')
            )
            
            logger.info(
                f"Payment succeeded webhook processed for subscription {subscription.id}"
            )
        except Exception as e:
            logger.error(f"Error handling payment.succeeded: {str(e)}")
            raise
    
    @staticmethod
    def _handle_payment_failed(event: PaymentEvent, payload: Dict):
        """Handle payment.failed webhook."""
        subscription_external_id = payload.get('customer_id')
        error_code = payload.get('error_code', 'UNKNOWN')
        
        try:
            subscription = Subscription.objects.get(
                payment_method__provider_customer_id=subscription_external_id
            )
            event.subscription = subscription
            
            # Find related invoice
            invoice = Invoice.objects.filter(
                subscription=subscription,
                status__in=['issued', 'overdue', 'partial']
            ).latest('issued_date')
            
            event.invoice = invoice
            
            # Start dunning if not already started
            if not invoice.dunning_attempts.exists():
                DunningService.start_dunning(invoice)
            
            logger.warning(
                f"Payment failed webhook for subscription {subscription.id}: {error_code}"
            )
        except Exception as e:
            logger.error(f"Error handling payment.failed: {str(e)}")
            raise
    
    @staticmethod
    def _handle_invoice_paid(event: PaymentEvent, payload: Dict):
        """Handle invoice.paid webhook."""
        invoice_external_id = payload.get('invoice_id')
        
        try:
            invoice = Invoice.objects.get(number=invoice_external_id)
            event.invoice = invoice
            event.subscription = invoice.subscription
            
            BillingService.record_payment(
                invoice=invoice,
                amount=invoice.amount_due,
                provider_payment_id=invoice_external_id
            )
            
            logger.info(f"Invoice {invoice.number} marked as paid via webhook")
        except Exception as e:
            logger.error(f"Error handling invoice.paid: {str(e)}")
            raise
    
    @staticmethod
    def _handle_invoice_payment_failed(event: PaymentEvent, payload: Dict):
        """Handle invoice.payment_failed webhook."""
        invoice_external_id = payload.get('invoice_id')
        
        try:
            invoice = Invoice.objects.get(number=invoice_external_id)
            event.invoice = invoice
            event.subscription = invoice.subscription
            
            # Start dunning
            if not invoice.dunning_attempts.exists():
                DunningService.start_dunning(invoice)
            
            logger.warning(
                f"Invoice {invoice.number} payment failed via webhook"
            )
        except Exception as e:
            logger.error(f"Error handling invoice.payment_failed: {str(e)}")
            raise
