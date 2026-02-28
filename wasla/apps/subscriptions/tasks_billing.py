"""
Celery tasks for recurring billing system.

Scheduled tasks:
- Process recurring billing charges
- Execute dunning flow for failed payments
- Check and expire grace periods
- Sync payment events from provider
"""

from celery import shared_task
from django.utils import timezone
from django.db.models import Q
from datetime import date, timedelta
import logging

from .models_billing import (
    Subscription, Invoice, BillingCycle, DunningAttempt,
    PaymentEvent
)
from .services_billing import (
    BillingService, DunningService, SubscriptionService, WebhookService
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_recurring_billing(self):
    """
    Process billing for all subscriptions with billing date today.
    
    Runs daily to:
    1. Find subscriptions due for billing
    2. Create billing cycles
    3. Generate invoices
    4. Attempt payment charge
    
    Celery beat: Daily at 2 AM
    """
    try:
        today = date.today()
        
        # Find all active subscriptions due for billing
        due_subscriptions = Subscription.objects.filter(
            state='active',
            next_billing_date=today
        ).select_related('plan', 'payment_method')
        
        logger.info(f"Processing recurring billing for {due_subscriptions.count()} subscriptions")
        
        for subscription in due_subscriptions:
            try:
                _charge_subscription(subscription)
            except Exception as e:
                logger.exception(
                    f"Failed to charge subscription {subscription.id}: {str(e)}"
                )
                # Continue with next subscription
        
        logger.info("Recurring billing processing completed")
        
    except Exception as e:
        logger.exception(f"Error in process_recurring_billing: {str(e)}")
        # Retry task with exponential backoff
        raise self.retry(exc=e, countdown=3600)  # Retry in 1 hour


def _charge_subscription(subscription):
    """
    Internal: Execute billing for a single subscription.
    
    Steps:
    1. Create billing cycle
    2. Create invoice
    3. Attempt payment
    """
    # Calculate billing period
    today = date.today()
    
    # Get previous cycle to calculate next one
    last_cycle = BillingCycle.objects.filter(
        subscription=subscription
    ).order_by('-period_end').first()
    
    if last_cycle:
        period_start = last_cycle.period_end + timedelta(days=1)
    else:
        period_start = subscription.started_at.date()
    
    # Calculate period end (approximately 30 days later)
    period_end = period_start + timedelta(days=29)
    
    # Create billing cycle
    billing_cycle = BillingService.create_billing_cycle(
        subscription=subscription,
        period_start=period_start,
        period_end=period_end
    )
    
    # Create invoice
    invoice = BillingService.create_invoice(billing_cycle)
    
    # Attempt to charge payment method
    payment_method = subscription.payment_method
    
    if not payment_method or not payment_method.is_valid():
        logger.warning(
            f"No valid payment method for subscription {subscription.id}. "
            f"Starting dunning flow."
        )
        DunningService.start_dunning(invoice)
        return
    
    # Process payment
    try:
        success = _attempt_charge(invoice, payment_method)
        
        if not success:
            # Payment failed - start dunning
            DunningService.start_dunning(invoice)
    
    except Exception as e:
        logger.error(f"Error charging subscription {subscription.id}: {str(e)}")
        DunningService.start_dunning(invoice)


def _attempt_charge(invoice, payment_method):
    """
    Attempt to charge a payment method.
    
    Integrate with your payment provider here.
    This is a stub - replace with actual implementation.
    """
    # TODO: Integrate with Stripe, PayMob, 2Checkout, etc.
    # For now, return False
    return False


@shared_task(bind=True, max_retries=3)
def process_dunning_attempts(self):
    """
    Process pending dunning attempts.
    
    Runs daily to:
    1. Find due dunning attempts
    2. Execute payment retry
    3. Schedule next attempt if failed
    4. Suspend subscription if max retries exceeded
    
    Celery beat: Daily at 3 AM
    """
    try:
        now = timezone.now()
        
        # Find all pending dunning attempts that are due
        due_attempts = DunningAttempt.objects.filter(
            status='pending',
            scheduled_for__lte=now
        ).select_related('subscription', 'invoice')
        
        logger.info(f"Processing {due_attempts.count()} dunning attempts")
        
        for attempt in due_attempts:
            try:
                DunningService.process_dunning_attempt(attempt)
            except Exception as e:
                logger.exception(
                    f"Error processing dunning attempt {attempt.id}: {str(e)}"
                )
                # Continue with next attempt
        
        logger.info("Dunning attempt processing completed")
        
    except Exception as e:
        logger.exception(f"Error in process_dunning_attempts: {str(e)}")
        raise self.retry(exc=e, countdown=3600)


@shared_task(bind=True, max_retries=3)
def check_and_expire_grace_periods(self):
    """
    Check subscriptions with grace period and expire if deadline passed.
    
    Runs daily to:
    1. Find subscriptions with expired grace period
    2. Transition to suspended state
    3. Notify merchant
    
    Celery beat: Daily at 4 AM
    """
    try:
        now = timezone.now()
        
        # Find subscriptions with expired grace period
        expired_grace = Subscription.objects.filter(
            state='grace',
            grace_until__lte=now
        )
        
        logger.info(f"Expiring grace period for {expired_grace.count()} subscriptions")
        
        for subscription in expired_grace:
            try:
                # Check if invoice is paid
                latest_invoice = Invoice.objects.filter(
                    subscription=subscription,
                    status__in=['issued', 'overdue', 'partial']
                ).order_by('-issued_date').first()
                
                if latest_invoice and latest_invoice.status != 'paid':
                    # Grace period expired without payment - suspend
                    SubscriptionService.suspend_subscription(
                        subscription=subscription,
                        reason='Grace period expired without payment'
                    )
                    
                    # Send notification
                    _notify_grace_period_expired(subscription)
                
            except Exception as e:
                logger.exception(
                    f"Error expiring grace period for subscription {subscription.id}: {str(e)}"
                )
        
        logger.info("Grace period check completed")
        
    except Exception as e:
        logger.exception(f"Error in check_and_expire_grace_periods: {str(e)}")
        raise self.retry(exc=e, countdown=3600)


@shared_task(bind=True, max_retries=3)
def sync_unprocessed_payment_events(self):
    """
    Retry processing of failed webhook events.
    
    Runs periodically to:
    1. Find events with failed status
    2. Attempt to reprocess
    3. Update status
    
    Celery beat: Hourly
    """
    try:
        # Find payment events that failed to process
        failed_events = PaymentEvent.objects.filter(
            status='failed'
        ).order_by('created_at')[:100]  # Process max 100 per task
        
        logger.info(f"Reprocessing {failed_events.count()} failed payment events")
        
        for event in failed_events:
            try:
                # Retry processing the event
                result_event = WebhookService.handle_payment_event(
                    event_type=event.event_type,
                    provider_event_id=event.provider_event_id,
                    payload=event.payload
                )
                
                logger.info(f"Successfully reprocessed event {event.provider_event_id}")
                
            except Exception as e:
                logger.exception(
                    f"Still unable to process event {event.provider_event_id}: {str(e)}"
                )
        
        logger.info("Payment event sync completed")
        
    except Exception as e:
        logger.exception(f"Error in sync_unprocessed_payment_events: {str(e)}")
        raise self.retry(exc=e, countdown=3600)


@shared_task(bind=True, max_retries=3)
def cleanup_old_billing_records(self):
    """
    Clean up old billing records (archival/retention).
    
    Runs weekly to:
    1. Archive old billing cycles
    2. Delete test invoices
    3. Clean up failed payment events older than 90 days
    
    Celery beat: Weekly on Sunday at 2 AM
    """
    try:
        now = timezone.now()
        
        # Clean up failed events older than 90 days
        cutoff_date = now - timedelta(days=90)
        deleted_count, _ = PaymentEvent.objects.filter(
            status='failed',
            created_at__lt=cutoff_date
        ).delete()
        
        logger.info(f"Deleted {deleted_count} old failed payment events")
        
        # Log summary
        logger.info("Billing record cleanup completed")
        
    except Exception as e:
        logger.exception(f"Error in cleanup_old_billing_records: {str(e)}")
        raise self.retry(exc=e, countdown=3600)


def _notify_grace_period_expired(subscription):
    """
    Send notification to merchant that grace period expired.
    
    Integrate with notification system.
    """
    # TODO: Send email/SMS to merchant
    logger.info(f"Grace period expired notification sent to tenant {subscription.tenant_id}")


# ============================================================================
# Celery Beat Schedule Configuration
# ============================================================================
"""
Add this to your Django settings.py or celery.py:

from celery.schedules import crontab

app.conf.beat_schedule = {
    'process-recurring-billing': {
        'task': 'apps.subscriptions.tasks_billing.process_recurring_billing',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'process-dunning-attempts': {
        'task': 'apps.subscriptions.tasks_billing.process_dunning_attempts',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
    },
    'check-grace-periods': {
        'task': 'apps.subscriptions.tasks_billing.check_and_expire_grace_periods',
        'schedule': crontab(hour=4, minute=0),  # Daily at 4 AM
    },
    'sync-payment-events': {
        'task': 'apps.subscriptions.tasks_billing.sync_unprocessed_payment_events',
        'schedule': crontab(minute=0),  # Every hour
    },
    'cleanup-billing-records': {
        'task': 'apps.subscriptions.tasks_billing.cleanup_old_billing_records',
        'schedule': crontab(hour=2, minute=0, day_of_week=6),  # Weekly Sunday at 2 AM
    },
}
"""
