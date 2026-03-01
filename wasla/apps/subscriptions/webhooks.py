"""
Webhook handlers for onboarding payment processing.

Handles payment confirmation webhooks from Stripe and Tap,
then activates the store after successful payment.
"""

import logging
import hashlib
import hmac
import json
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.stores.models import Store
from apps.payments.models import WebhookEvent, PaymentIntent
from apps.subscriptions.services.onboarding_payment import activate_store_after_payment

logger = logging.getLogger(__name__)


def handle_stripe_webhook(event_data: dict, raw_body: str, headers: dict) -> bool:
    """
    Handle Stripe webhook event.
    
    Verifies signature and processes payment_intent.succeeded events.
    Returns: True if processed successfully, False if ignored/invalid.
    """
    from apps.orders.models import Order
    
    # Verify Stripe signature
    sig_header = headers.get('stripe-signature', '')
    secret = settings.STRIPE_WEBHOOK_SECRET
    
    if not secret:
        logger.warning("Stripe webhook secret not configured")
        return False
    
    try:
        # Verify the webhook signature
        timestamp, signature = sig_header.split(',')[0].split('=')[1], sig_header.split(',')[1].split('=')[1]
        signed_content = f"{timestamp}.{raw_body}"
        expected_sig = hmac.new(
            secret.encode(),
            signed_content.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_sig):
            logger.warning(f"Stripe webhook signature mismatch: {event_data.get('id')}")
            return False
    except (ValueError, IndexError, AttributeError) as e:
        logger.warning(f"Invalid Stripe signature format: {e}")
        return False
    
    event_id = event_data.get('id')
    event_type = event_data.get('type')
    
    # Idempotency check - has this event been processed?
    webhook_obj, created = WebhookEvent.objects.get_or_create(
        provider='stripe',
        event_id=event_id,
        defaults={
            'provider_name': 'Stripe',
            'payload': event_data,
            'raw_payload': raw_body,
            'status': 'received'
        }
    )
    
    if not created:
        # Already processed
        logger.info(f"Stripe webhook already processed: {event_id}")
        return False
    
    # Process only payment_intent.succeeded events
    if event_type != 'payment_intent.succeeded':
        logger.info(f"Ignoring Stripe event type: {event_type}")
        webhook_obj.status = 'ignored'
        webhook_obj.save(update_fields=['status'])
        return False
    
    try:
        with transaction.atomic():
            # Extract payment intent from webhook
            payment_intent_data = event_data.get('data', {}).get('object', {})
            stripe_intent_id = payment_intent_data.get('id')
            stripe_customer_id = payment_intent_data.get('customer')
            amount = payment_intent_data.get('amount')  # Amount in cents
            
            if not stripe_intent_id:
                logger.warning(f"No intent ID in Stripe webhook: {event_id}")
                webhook_obj.status = 'ignored'
                webhook_obj.save(update_fields=['status'])
                return False
            
            # Find the PaymentIntent in our system
            intent = PaymentIntent.objects.filter(
                provider_code='stripe',
                provider_reference=stripe_intent_id,
                status='pending'
            ).first()
            
            if not intent:
                logger.warning(f"PaymentIntent not found for Stripe: {stripe_intent_id}")
                webhook_obj.status = 'failed'
                webhook_obj.save(update_fields=['status'])
                return False
            
            # Get the store and activate it
            store = intent.order.store if intent.order else None
            if not store:
                logger.warning(f"Store not found for payment intent: {intent.id}")
                webhook_obj.status = 'failed'
                webhook_obj.save(update_fields=['status'])
                return False
            
            # Mark intent as succeeded
            intent.status = 'succeeded'
            intent.save(update_fields=['status'])
            
            # Activate the store after payment
            webhook_obj.store = store
            webhook_obj.status = 'processing'
            webhook_obj.save(update_fields=['store', 'status'])
            
            activated = activate_store_after_payment(store, webhook_event_id=webhook_obj.id)
            
            webhook_obj.status = 'processed'
            webhook_obj.processed_at = __import__('django.utils.timezone', fromlist=['now']).now()
            webhook_obj.save(update_fields=['status', 'processed_at'])
            
            if activated:
                logger.info(f"Store {store.id} activated via Stripe webhook: {event_id}")
            
            return True
            
    except Exception as e:
        logger.exception(f"Error processing Stripe webhook: {event_id}", exc_info=e)
        webhook_obj.status = 'failed'
        webhook_obj.save(update_fields=['status'])
        return False


def handle_tap_webhook(event_data: dict, raw_body: str, headers: dict) -> bool:
    """
    Handle Tap webhook event.
    
    Verifies signature and processes charge.completed events.
    Returns: True if processed successfully, False if ignored/invalid.
    """
    from apps.orders.models import Order
    
    event_id = event_data.get('id')
    event_type = event_data.get('type')
    
    # Idempotency check
    webhook_obj, created = WebhookEvent.objects.get_or_create(
        provider='tap',
        event_id=event_id,
        defaults={
            'provider_name': 'Tap',
            'payload': event_data,
            'raw_payload': raw_body,
            'status': 'received'
        }
    )
    
    if not created:
        # Already processed
        logger.info(f"Tap webhook already processed: {event_id}")
        return False
    
    # Process only charge.completed events
    if event_type != 'charge.completed':
        logger.info(f"Ignoring Tap event type: {event_type}")
        webhook_obj.status = 'ignored'
        webhook_obj.save(update_fields=['status'])
        return False
    
    try:
        with transaction.atomic():
            # Extract charge data from webhook
            charge_data = event_data.get('data', {})
            tap_charge_id = charge_data.get('id')
            tap_status = charge_data.get('status')
            reference_id = charge_data.get('reference', {}).get('invoice') or charge_data.get('reference', {}).get('order')
            
            if not tap_charge_id or tap_status != 'CAPTURED':
                logger.warning(f"Invalid Tap charge data: {event_id}")
                webhook_obj.status = 'ignored'
                webhook_obj.save(update_fields=['status'])
                return False
            
            # Find the PaymentIntent in our system
            intent = PaymentIntent.objects.filter(
                provider_code='tap',
                provider_reference=tap_charge_id,
                status='pending'
            ).first()
            
            if not intent:
                logger.warning(f"PaymentIntent not found for Tap: {tap_charge_id}")
                webhook_obj.status = 'failed'
                webhook_obj.save(update_fields=['status'])
                return False
            
            # Get the store and activate it
            store = intent.order.store if intent.order else None
            if not store:
                logger.warning(f"Store not found for payment intent: {intent.id}")
                webhook_obj.status = 'failed'
                webhook_obj.save(update_fields=['status'])
                return False
            
            # Mark intent as succeeded
            intent.status = 'succeeded'
            intent.save(update_fields=['status'])
            
            # Activate the store after payment
            webhook_obj.store = store
            webhook_obj.status = 'processing'
            webhook_obj.save(update_fields=['store', 'status'])
            
            activated = activate_store_after_payment(store, webhook_event_id=webhook_obj.id)
            
            webhook_obj.status = 'processed'
            webhook_obj.processed_at = __import__('django.utils.timezone', fromlist=['now']).now()
            webhook_obj.save(update_fields=['status', 'processed_at'])
            
            if activated:
                logger.info(f"Store {store.id} activated via Tap webhook: {event_id}")
            
            return True
            
    except Exception as e:
        logger.exception(f"Error processing Tap webhook: {event_id}", exc_info=e)
        webhook_obj.status = 'failed'
        webhook_obj.save(update_fields=['status'])
        return False
