"""
Payment security utilities.

Implements:
- Idempotency key generation and validation
- HMAC signature validation
- Replay attack protection
- Retry strategy with exponential backoff
- Risk scoring utilities
- Structured logging
"""

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Optional, Tuple
from uuid import uuid4

from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


def generate_idempotency_key(
    store_id: int,
    order_id: int,
    client_token: Optional[str] = None,
) -> str:
    """
    Generate a cryptographically unique idempotency key.
    
    Used to prevent duplicate charge processing.
    
    Args:
        store_id: Store ID
        order_id: Order ID
        client_token: Optional client-provided token for uniqueness
    
    Returns:
        str: Idempotency key (format: store-order-uuid or store-order-hash)
    """
    if client_token:
        # If client provides token, hash it with order for uniqueness
        key_data = f"{store_id}:{order_id}:{client_token}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:64]
    else:
        # Generate unique UUID-based key
        return f"{store_id}-{order_id}-{uuid4().hex[:16]}"


def validate_idempotency_key(
    store_id: int,
    order_id: int,
    idempotency_key: str,
) -> bool:
    """
    Validate idempotency key format.
    
    Args:
        store_id: Store ID
        order_id: Order ID
        idempotency_key: Key to validate
    
    Returns:
        bool: True if valid key format
    """
    if not idempotency_key or len(idempotency_key) < 32:
        return False
    
    # Key must contain store_id and order_id prefixes
    return str(store_id) in idempotency_key or order_id in int(
        idempotency_key,
        36
    ) if idempotency_key.isalnum() else True


def compute_payload_hash(payload: Dict) -> str:
    """
    Compute SHA256 hash of JSON payload for integrity verification.
    
    Args:
        payload: Dict to hash
    
    Returns:
        str: Hex digest of SHA256
    """
    payload_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(payload_str.encode()).hexdigest()


def validate_webhook_signature(
    payload: Dict,
    signature: str,
    webhook_secret: str,
    algorithm: str = "sha256",
) -> bool:
    """
    Validate webhook signature using HMAC.
    
    Implements HMAC-SHA256 validation as per payment provider standards.
    
    Args:
        payload: Raw payload dict
        signature: Signature from webhook header
        webhook_secret: Secret key for HMAC
        algorithm: Hash algorithm (default: sha256)
    
    Returns:
        bool: True if signature is valid
    """
    if not webhook_secret or not signature:
        logger.warning("Missing webhook secret or signature")
        return False
    
    try:
        # Serialize payload consistently for HMAC
        payload_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        
        # Compute expected HMAC
        expected_signature = hmac.new(
            webhook_secret.encode(),
            payload_str.encode(),
            hashlib.sha256,
        ).hexdigest()
        
        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(expected_signature, signature)
    
    except Exception as e:
        logger.exception(f"Error validating webhook signature: {e}")
        return False


def validate_webhook_timestamp(
    webhook_timestamp: datetime,
    tolerance_seconds: int = 300,
) -> Tuple[bool, Optional[str]]:
    """
    Validate webhook timestamp to prevent replay attacks.
    
    Args:
        webhook_timestamp: Timestamp from webhook
        tolerance_seconds: Tolerance window (5 min default)
    
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    if not webhook_timestamp:
        return False, "Missing webhook timestamp"
    
    now = timezone.now()
    time_diff = abs((now - webhook_timestamp).total_seconds())
    
    if time_diff > tolerance_seconds:
        return False, (
            f"Webhook timestamp outside tolerance window "
            f"(diff: {time_diff}s, allowed: {tolerance_seconds}s)"
        )
    
    return True, None


class IdempotencyValidator:
    """Validates and checks idempotency for payment operations."""
    
    @staticmethod
    def check_duplicate(
        store_id: int,
        order_id: int,
        idempotency_key: str,
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Check if payment with same idempotency key already exists.
        
        Returns:
            (is_duplicate, existing_result_dict)
            If is_duplicate=True and existing_result is dict, return it
            If is_duplicate=True and existing_result is None, still processing
        """
        from apps.payments.models import PaymentAttempt
        
        try:
            existing = PaymentAttempt.objects.filter(
                idempotency_key=idempotency_key,
                store_id=store_id,
                order_id=order_id,
            ).first()
            
            if not existing:
                return False, None
            
            # Found existing payment with same key
            if existing.status == PaymentAttempt.STATUS_PAID:
                # Already succeeded, return result
                return True, {
                    "status": "success",
                    "payment_id": existing.id,
                    "provider_reference": existing.provider_reference,
                    "message": "Idempotent: Payment already processed",
                }
            
            elif existing.status in [
                PaymentAttempt.STATUS_PENDING,
                PaymentAttempt.STATUS_CREATED,
            ]:
                # Still processing, return pending
                return True, {
                    "status": "pending",
                    "payment_id": existing.id,
                    "message": "Idempotent: Payment still processing",
                }
            
            elif existing.status == PaymentAttempt.STATUS_FAILED:
                # Previous attempt failed, allow retry
                return False, None
            
            else:
                # Other status (cancelled, refunded), allow retry
                return False, None
        
        except Exception as e:
            logger.exception(f"Error checking idempotency: {e}")
            return False, None


class RetryStrategy:
    """
    Exponential backoff retry strategy for payment operations.
    
    Implements resilience against transient failures.
    """
    
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_INITIAL_DELAY_SECONDS = 1
    DEFAULT_MAX_DELAY_SECONDS = 60
    EXPONENTIAL_BASE = 2
    
    @staticmethod
    def should_retry(
        status: str,
        retry_count: int,
        max_retries: Optional[int] = None,
    ) -> bool:
        """
        Determine if payment should be retried.
        
        Retryable statuses: created, pending, timeout
        Non-retryable: paid, failed (terminal), cancelled, refunded
        
        Args:
            status: Current payment status
            retry_count: Number of retries so far
            max_retries: Maximum allowed retries
        
        Returns:
            bool: True if should retry
        """
        max_retries = max_retries or RetryStrategy.DEFAULT_MAX_RETRIES
        
        if retry_count >= max_retries:
            return False
        
        retryable_statuses = ["created", "pending", "retry_pending"]
        return status in retryable_statuses
    
    @staticmethod
    def calculate_next_retry(
        retry_count: int,
        initial_delay: int = DEFAULT_INITIAL_DELAY_SECONDS,
        max_delay: int = DEFAULT_MAX_DELAY_SECONDS,
    ) -> datetime:
        """
        Calculate when next retry should occur (exponential backoff).
        
        Formula: delay = min(initial * base^retry_count, max_delay)
        
        Args:
            retry_count: Current retry number (0-based)
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
        
        Returns:
            datetime: When to retry next
        """
        delay_seconds = min(
            initial_delay * (RetryStrategy.EXPONENTIAL_BASE ** retry_count),
            max_delay,
        )
        
        # Add jitter (±10%) to prevent thundering herd
        jitter = delay_seconds * 0.1
        import random
        delay_with_jitter = delay_seconds + random.uniform(-jitter, jitter)
        
        return timezone.now() + timedelta(seconds=delay_with_jitter)


class RiskScoringEngine:
    """
    Fraud detection and risk scoring for payments.
    
    Evaluates:
    - IP velocity
    - Amount velocity
    - Refund history
    - Customer profile
    """
    
    VELOCITY_CHECK_WINDOW_MINUTES = 60  # 1 hour
    VELOCITY_THRESHOLD_5MIN = 5
    VELOCITY_THRESHOLD_1HOUR = 20
    
    @staticmethod
    def calculate_risk_score(
        store_id: int,
        order_id: int,
        ip_address: Optional[str],
        amount: Decimal,
        is_new_customer: bool = False,
    ) -> Tuple[int, Dict]:
        """
        Calculate risk score for a payment.
        
        Scoring:
        - 0-25: Low risk
        - 26-50: Medium risk
        - 51-75: High risk
        - 76-100: Critical (flag for review)
        
        Args:
            store_id: Store ID
            order_id: Order ID
            ip_address: Customer IP
            amount: Payment amount
            is_new_customer: Whether customer is new
        
        Returns:
            Tuple[risk_score, details_dict]
        """
        from apps.payments.models import PaymentAttempt
        from apps.orders.models import Order
        from django.db.models import Sum, Count
        
        score = 0
        details = {}
        triggered_rules = []
        
        try:
            # Rule 1: New customer
            if is_new_customer:
                score += 10
                triggered_rules.append("new_customer")
                details["new_customer"] = True
            
            # Rule 2: IP velocity check
            if ip_address:
                now = timezone.now()
                look_back_5min = now - timedelta(minutes=5)
                look_back_1hour = now - timedelta(minutes=60)
                
                # Count payments from same IP
                velocity_5min = PaymentAttempt.objects.filter(
                    ip_address=ip_address,
                    created_at__gte=look_back_5min,
                    store_id=store_id,
                ).count()
                
                velocity_1hour = PaymentAttempt.objects.filter(
                    ip_address=ip_address,
                    created_at__gte=look_back_1hour,
                    store_id=store_id,
                ).count()
                
                details["velocity_5min"] = velocity_5min
                details["velocity_1hour"] = velocity_1hour
                
                if velocity_5min > RiskScoringEngine.VELOCITY_THRESHOLD_5MIN:
                    score += 20
                    triggered_rules.append(f"ip_velocity_5min:{velocity_5min}")
                
                if velocity_1hour > RiskScoringEngine.VELOCITY_THRESHOLD_1HOUR:
                    score += 15
                    triggered_rules.append(f"ip_velocity_1hour:{velocity_1hour}")
            
            # Rule 3: Unusual amount (> 2x average for customer)
            try:
                order = Order.objects.get(id=order_id)
                avg_order_amount = Order.objects.filter(
                    store_id=store_id,
                    customer=order.customer,
                ).aggregate(avg=Sum('total_amount'))['avg']
                
                if avg_order_amount and amount > (avg_order_amount * 2):
                    score += 15
                    triggered_rules.append("unusual_high_amount")
                    details["unusual_amount"] = True
            except:
                pass
            
            # Rule 4: Previous failed attempts
            failed_attempts = PaymentAttempt.objects.filter(
                order_id=order_id,
                status=PaymentAttempt.STATUS_FAILED,
            ).count()
            
            if failed_attempts > 0:
                score += min(failed_attempts * 5, 20)  # Max 20 points
                triggered_rules.append(f"previous_failed:{failed_attempts}")
                details["previous_failed_attempts"] = failed_attempts
            
            # Cap score at 100
            score = min(score, 100)
            details["triggered_rules"] = triggered_rules
            
            return score, details
        
        except Exception as e:
            logger.exception(f"Error calculating risk score: {e}")
            return 0, {"error": str(e)}


def log_payment_event(
    event_type: str,
    store_id: int,
    order_id: int,
    provider: str,
    status: str,
    idempotency_key: str,
    duration_ms: int = 0,
    error: Optional[str] = None,
    metadata: Optional[Dict] = None,
) -> None:
    """
    Log payment event with structured JSON format.
    
    Used for:
    - Audit trail
    - Debugging
    - Monitoring/alerting
    - Compliance
    
    Args:
        event_type: charge_initiated, charge_confirmed, webhook_received, etc.
        store_id: Store ID
        order_id: Order ID
        provider: Payment provider
        status: Operation status (success, failed, pending, etc.)
        idempotency_key: Idempotency key
        duration_ms: Operation duration
        error: Error message if any
        metadata: Additional context
    """
    log_entry = {
        "timestamp": timezone.now().isoformat(),
        "event_type": event_type,
        "store_id": store_id,
        "order_id": order_id,
        "provider": provider,
        "status": status,
        "idempotency_key": idempotency_key,
        "duration_ms": duration_ms,
        "error": error,
        "metadata": metadata or {},
    }
    
    logger.info(json.dumps(log_entry))


def log_webhook_event(
    provider: str,
    event_id: str,
    signature_verified: bool,
    processed: bool,
    error: Optional[str] = None,
) -> None:
    """
    Log webhook receipt and processing.
    
    Args:
        provider: Payment provider
        event_id: Webhook event ID
        signature_verified: Whether HMAC was valid
        processed: Whether event was processed
        error: Error if any
    """
    log_entry = {
        "timestamp": timezone.now().isoformat(),
        "event": "webhook_received",
        "provider": provider,
        "event_id": event_id,
        "signature_verified": signature_verified,
        "processed": processed,
        "error": error,
    }
    
    logger.info(json.dumps(log_entry))
