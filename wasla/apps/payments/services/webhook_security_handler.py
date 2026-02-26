"""
Enhanced webhook handler with enterprise-grade security integration.

Integrates:
- HMAC signature validation
- Replay attack protection  
- Idempotency enforcement
- Risk scoring
- Structured logging
- Retry state management
"""

import hashlib
import hmac
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Tuple

from django.db import transaction 
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.payments.models import (
    PaymentAttempt,
    WebhookEvent, 
    PaymentRisk,
    PaymentProviderSettings,
)
from apps.payments.security import (
    validate_webhook_signature,
    validate_webhook_timestamp,
    IdempotencyValidator,
    RiskScoringEngine,
    log_webhook_event,
)

logger = logging.getLogger(__name__)


@dataclass
class WebhookContext:
    """Context for webhook processing."""
    provider_code: str
    headers: Dict[str, str]
    payload: Dict
    raw_body: str
    ip_address: str = ""
    user_agent: str = ""


@dataclass
class WebhookValidationResult:
    """Result of webhook validation."""
    is_valid: bool
    signature_verified: bool
    timestamp_valid: bool
    payload_hash: str
    timestamp: Optional[int]
    error_message: Optional[str] = None
    warning_messages: list = None
    
    def __post_init__(self):
        if self.warning_messages is None:
            self.warning_messages = []


class WebhookSecurityHandler:
    """
    Handles webhook security validation and routing.
    
    Execution flow:
    1. Extract and validate HMAC signature
    2. Validate webhook timestamp (replay protection)
    3. Check for event deduplication (idempotency)
    4. Calculate risk score
    5. Update payment state if needed
    6. Structured logging
    """
    
    @staticmethod
    @transaction.atomic
    def process_webhook(
        context: WebhookContext,
        order_id: Optional[int] = None,
        store_id: Optional[int] = None,
    ) -> Tuple[WebhookEvent, PaymentRisk]:
        """
        Process webhook with full security validation.
        
        Args:
            context: WebhookContext with headers, payload, raw_body
            order_id: Associated order ID (if known)
            store_id: Store ID for multi-tenant filtering
        
        Returns:
            Tuple of (WebhookEvent, PaymentRisk) - risk may be None if low risk
        
        Raises:
            ValidationError: On security violation or processing failure
        """
        
        # Step 1: Validate webhook security
        validation_result = WebhookSecurityHandler.validate_webhook_security(
            context
        )
        
        if not validation_result.is_valid:
            logger.error(
                f"Webhook validation failed for {context.provider_code}: "
                f"{validation_result.error_message}",
                extra={
                    "provider": context.provider_code,
                    "signature_verified": validation_result.signature_verified,
                    "timestamp_valid": validation_result.timestamp_valid,
                },
            )
            raise ValidationError(validation_result.error_message)
        
        # Log warnings if any
        for warning in validation_result.warning_messages:
            logger.warning(
                f"Webhook warning for {context.provider_code}: {warning}",
                extra={"provider": context.provider_code},
            )
        
        # Step 2: Get or create webhook event record
        event = WebhookSecurityHandler._get_or_create_webhook_event(
            context=context,
            validation_result=validation_result,
            store_id=store_id,
        )
        
        # Step 3: Check idempotency (prevent duplicate processing)
        is_duplicate, existing_result = IdempotencyValidator.check_duplicate(
            store_id=store_id or event.store_id or 0,
            order_id=order_id or 0,
            idempotency_key=event.idempotency_key,
        )
        
        if is_duplicate and existing_result.get("status") == "paid":
            logger.info(
                f"Webhook is idempotent duplicate (already processed): {event.idempotency_key}",
                extra={
                    "provider": context.provider_code,
                    "order_id": order_id,
                    "duplicate": True,
                },
            )
            event.retry_count = 0  # Reset on successful verification
            event.save(update_fields=["retry_count"])
            
            # Log idempotent success
            log_webhook_event(
                provider=context.provider_code,
                event_id=event.event_id,
                signature_verified=validation_result.signature_verified,
                processed=True,
                metadata={
                    "duplicate": True,
                    "previous_status": existing_result.get("status"),
                },
            )
            
            return event, None
        
        # Step 4: Calculate risk score based on webhook context
        risk_score, risk_details = RiskScoringEngine.calculate_risk_score(
            store_id=store_id or event.store_id or 0,
            order_id=order_id or 0,
            ip_address=context.ip_address,
            amount=event.payload_json.get("amount", 0),
            is_new_customer=event.payload_json.get("is_new_customer", False),
        )
        
        # Step 5: Create/update payment risk record
        payment_risk = WebhookSecurityHandler._record_webhook_risk(
            webhook_event=event,
            order_id=order_id,
            store_id=store_id or event.store_id,
            risk_score=risk_score,
            risk_details=risk_details,
            ip_address=context.ip_address,
        )
        
        # Step 6: Update webhook event with security verification
        event.signature_verified = validation_result.signature_verified
        event.timestamp_valid = validation_result.timestamp_valid
        event.payload_hash = validation_result.payload_hash
        event.webhook_timestamp = validation_result.timestamp
        event.idempotency_checked = True
        event.save(
            update_fields=[
                "signature_verified",
                "timestamp_valid",
                "payload_hash",
                "webhook_timestamp",
                "idempotency_checked",
            ]
        )
        
        # Step 7: Structured logging
        log_webhook_event(
            provider=context.provider_code,
            event_id=event.event_id,
            signature_verified=validation_result.signature_verified,
            processed=True,
            metadata={
                "order_id": order_id,
                "risk_score": risk_score,
                "risk_level": payment_risk.risk_level if payment_risk else None,
                "ip_address": context.ip_address,
                "warnings": validation_result.warning_messages,
            },
        )
        
        return event, payment_risk
    
    @staticmethod
    def validate_webhook_security(context: WebhookContext) -> WebhookValidationResult:
        """
        Validate webhook signature and timestamp.
        
        Args:
            context: WebhookContext with headers and payload
        
        Returns:
            WebhookValidationResult with validation status
        """
        payload_hash = hashlib.sha256(
            context.raw_body.encode("utf-8")
        ).hexdigest() if context.raw_body else ""
        
        # Extract signature and timestamp from headers
        signature = (
            context.headers.get("X-Webhook-Signature") 
            or context.headers.get("X-Signature")
            or ""
        )
        
        timestamp = (
            context.headers.get("X-Webhook-Timestamp")
            or context.headers.get("X-Timestamp") 
            or None
        )
        
        # Try to parse timestamp
        webhook_timestamp = None
        timestamp_valid = False
        if timestamp:
            try:
                webhook_timestamp = int(timestamp)
                timestamp_valid, _ = validate_webhook_timestamp(
                    webhook_timestamp=webhook_timestamp,
                    tolerance_seconds=300,  # 5 minutes
                )
            except (ValueError, TypeError):
                logger.warning(f"Invalid timestamp format: {timestamp}")
        
        # Get webhook secret from provider settings
        try:
            provider_settings = PaymentProviderSettings.objects.get(
                provider_code=context.provider_code
            )
            webhook_secret = provider_settings.webhook_secret
        except PaymentProviderSettings.DoesNotExist:
            logger.warning(
                f"No provider settings found for {context.provider_code}, "
                f"skipping signature verification"
            )
            webhook_secret = None
        
        # Validate signature if secret is configured
        signature_verified = False
        warning_messages = []
        
        if webhook_secret and signature and context.raw_body:
            signature_verified = validate_webhook_signature(
                payload=context.raw_body,
                signature=signature,
                webhook_secret=webhook_secret,
            )
            
            if not signature_verified:
                error_msg = f"Invalid webhook signature for {context.provider_code}"
                logger.error(error_msg)
                return WebhookValidationResult(
                    is_valid=False,
                    signature_verified=False,
                    timestamp_valid=timestamp_valid,
                    payload_hash=payload_hash,
                    timestamp=webhook_timestamp,
                    error_message=error_msg,
                )
        elif not webhook_secret:
            warning_messages.append(
                f"No webhook secret configured for {context.provider_code}, "
                f"signature verification skipped"
            )
        elif not signature:
            warning_messages.append("No signature header found")
        
        # Check timestamp validity if signature verified
        if signature_verified and not timestamp_valid and webhook_timestamp is not None:
            error_msg = "Webhook timestamp expired (possible replay attack)"
            logger.error(error_msg)
            return WebhookValidationResult(
                is_valid=False,
                signature_verified=signature_verified,
                timestamp_valid=False,
                payload_hash=payload_hash,
                timestamp=webhook_timestamp,
                error_message=error_msg,
            )
        
        return WebhookValidationResult(
            is_valid=True,
            signature_verified=signature_verified,
            timestamp_valid=timestamp_valid,
            payload_hash=payload_hash,
            timestamp=webhook_timestamp,
            warning_messages=warning_messages,
        )
    
    @staticmethod
    def _get_or_create_webhook_event(
        context: WebhookContext,
        validation_result: WebhookValidationResult,
        store_id: Optional[int] = None,
    ) -> WebhookEvent:
        """
        Get or create webhook event record with idempotency.
        
        Args:
            context: WebhookContext
            validation_result: WebhookValidationResult
            store_id: Store ID for multi-tenant context
        
        Returns:
            WebhookEvent instance
        """
        event_id = context.payload.get("event_id") or context.payload.get("id") or ""
        
        # Create idempotency key: provider:event_id:payload_hash
        idempotency_key = (
            f"{context.provider_code}:{event_id}:{validation_result.payload_hash}"
        )
        
        event, created = WebhookEvent.objects.get_or_create(
            provider=context.provider_code,
            event_id=str(event_id),
            defaults={
                "store_id": store_id,
                "payload_json": context.payload,
                "idempotency_key": idempotency_key,
                "payload_hash": validation_result.payload_hash,
                "status": "pending",
                "retry_count": 0,
            },
        )
        
        if not created and not event.payload_hash:
            # Update payload hash if missing
            event.payload_hash = validation_result.payload_hash
            event.idempotency_key = idempotency_key
            event.save(update_fields=["payload_hash", "idempotency_key"])
        
        return event
    
    @staticmethod
    def _record_webhook_risk(
        webhook_event: WebhookEvent,
        order_id: Optional[int],
        store_id: Optional[int],
        risk_score: int,
        risk_details: Dict,
        ip_address: str = "",
    ) -> Optional[PaymentRisk]:
        """
        Create or update PaymentRisk record based on webhook context.
        
        Args:
            webhook_event: WebhookEvent instance
            order_id: Associated order ID
            store_id: Store ID
            risk_score: Calculated risk score (0-100)
            risk_details: Risk details dict with triggered_rules
            ip_address: Customer IP address
        
        Returns:
            PaymentRisk instance or None if no risk to record
        """
        # Only create risk record if risk is significant
        if risk_score < 40:
            return None
        
        # Determine risk level
        if risk_score >= 76:
            risk_level = "critical"
        elif risk_score >= 60:
            risk_level = "high"
        elif risk_score >= 40:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        # Try to get associated payment attempt
        payment_attempt = None
        if order_id:
            try:
                payment_attempt = PaymentAttempt.objects.filter(
                    order_id=order_id,
                    status__in=["pending", "paid"],
                ).order_by("-created_at").first()
            except Exception as e:
                logger.warning(f"Error finding payment attempt: {e}")
        
        risk, created = PaymentRisk.objects.update_or_create(
            payment_attempt=payment_attempt if payment_attempt else None,
            order_id=order_id or 0,
            defaults={
                "store_id": store_id or 0,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "flagged": risk_score >= 75,
                "ip_address": ip_address,
                "triggered_rules": risk_details.get("triggered_rules", []),
                "is_new_customer": risk_details.get("is_new_customer", False),
                "unusual_amount": risk_details.get("unusual_amount", False),
                "velocity_count_5min": risk_details.get("velocity_count_5min", 0),
                "velocity_count_1hour": risk_details.get("velocity_count_1hour", 0),
            },
        )
        
        return risk
    
    @staticmethod
    def handle_webhook_retry(
        webhook_event: WebhookEvent,
        error: Optional[str] = None,
        schedule_retry: bool = True,
    ) -> None:
        """
        Handle webhook processing failure and schedule retry.
        
        Args:
            webhook_event: WebhookEvent instance
            error: Error message if any
            schedule_retry: Whether to schedule retry
        """
        webhook_event.retry_count += 1
        webhook_event.last_error = error or "Unknown error"
        
        if schedule_retry and webhook_event.retry_count < 3:
            # Calculate next retry time: exponential backoff
            backoff_seconds = min(2 ** webhook_event.retry_count, 3600)  # Max 1 hour
            webhook_event.next_retry_after = (
                timezone.now() + timezone.timedelta(seconds=backoff_seconds)
            )
            webhook_event.status = "retry_pending"
        else:
            webhook_event.status = "failed"
        
        webhook_event.save(
            update_fields=[
                "retry_count",
                "last_error",
                "next_retry_after",
                "status",
            ]
        )
        
        log_webhook_event(
            provider=webhook_event.provider,
            event_id=webhook_event.event_id,
            signature_verified=webhook_event.signature_verified,
            processed=False,
            error=error,
        )
