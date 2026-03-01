"""
Payment activation service for onboarding flow.

Handles activation of store after payment success (Stripe, Tap, or manual admin approval).
"""

from django.db import transaction
from django.utils import timezone
from apps.stores.models import Store
from apps.subscriptions.models_billing import Subscription
from apps.payments.models import WebhookEvent


@transaction.atomic
def activate_store_after_payment(store: Store, webhook_event_id: str = None) -> bool:
    """
    Activate a store after successful payment.
    
    Idempotent: Safe to call multiple times for the same event.
    
    Args:
        store: Store to activate
        webhook_event_id: Provider event ID for idempotency (optional)
    
    Returns:
        bool: True if newly activated, False if already activated
    
    Side Effects:
        - Sets store.status = ACTIVE
        - Activates StoreDomain
        - Calls publish_default_storefront()
        - Marks webhook event as processed
    """
    
    # Idempotency: check if already activated
    if webhook_event_id:
        if WebhookEvent.objects.filter(provider_event_id=webhook_event_id).exists():
            return False  # Already processed
    
    # Already active - no-op
    if store.status == Store.STATUS_ACTIVE:
        return False
    
    # Activate store
    store.status = Store.STATUS_ACTIVE
    store.save(update_fields=['status', 'updated_at'])
    
    # Activate StoreDomain
    from apps.tenants.models import StoreDomain
    StoreDomain.objects.filter(store=store).update(status='active')
    
    # Publish storefront
    from apps.storefront.services import publish_default_storefront
    publish_default_storefront(store)
    
    # Log webhook event if provided
    if webhook_event_id:
        WebhookEvent.objects.filter(provider_event_id=webhook_event_id).update(
            is_verified=True
        )
    
    return True


def approve_manual_payment(manual_payment, approved_by) -> bool:
    """
    Admin approves a manual payment submission.
    
    Args:
        manual_payment: ManualPayment instance
        approved_by: User who approved
    
    Returns:
        bool: True if approval triggered activation, False if already processed
    """
    
    # Approve the payment record
    manual_payment.approve(approved_by)
    
    # Activate the associated store
    return activate_store_after_payment(manual_payment.store)
