from __future__ import annotations

from dataclasses import dataclass
import time
from decimal import Decimal
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.conf import settings

from apps.orders.models import Order
from apps.payments.application.facade import PaymentGatewayFacade
from apps.payments.domain.ports import PaymentRedirect
from apps.payments.models import PaymentIntent, PaymentAttempt, PaymentRisk, PaymentProviderSettings
from apps.payments.application.use_cases.payment_outcomes import apply_payment_success
from apps.payments.security import FraudDetectionService, ProviderCommunicationLogger
from apps.payments.security.retry_logic import PaymentProviderRetry, RetryConfig
from apps.payments.state_machine import transition_payment_attempt_status
from apps.payments.structured_logging import log_payment_structured
from apps.tenants.domain.tenant_context import TenantContext
from apps.analytics.application.telemetry import TelemetryService, actor_from_tenant_ctx
from apps.analytics.domain.types import ObjectRef


@dataclass(frozen=True)
class InitiatePaymentCommand:
    tenant_ctx: TenantContext
    order_id: int
    provider_code: str
    return_url: str
    idempotency_key: str
    ip_address: str = ""
    user_agent: str = ""


class InitiatePaymentUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: InitiatePaymentCommand) -> PaymentRedirect:
        if not (cmd.idempotency_key or "").strip():
            raise ValueError("idempotency_key is required")

        order = (
            Order.objects.for_tenant(cmd.tenant_ctx.store_id)
            .select_for_update()
            .filter(id=cmd.order_id)
            .first()
        )
        if not order:
            raise ValueError("Order not found.")
        if order.payment_status == "paid":
            return PaymentRedirect(redirect_url=cmd.return_url, client_secret=None, provider_reference=None)

        bnpl_min_amount = Decimal(str(getattr(settings, "BNPL_MIN_AMOUNT", "200")))
        if cmd.provider_code in {"tabby", "tamara"} and order.total_amount < bnpl_min_amount:
            raise ValueError(f"BNPL requires minimum order amount of {bnpl_min_amount} SAR.")

        existing_attempt = (
            PaymentAttempt.objects.select_for_update()
            .filter(
                store_id=cmd.tenant_ctx.store_id,
                order=order,
                idempotency_key=cmd.idempotency_key,
            )
            .first()
        )
        if existing_attempt:
            if existing_attempt.status == PaymentAttempt.STATUS_CONFIRMED:
                return PaymentRedirect(
                    redirect_url=cmd.return_url,
                    client_secret=None,
                    provider_reference=existing_attempt.provider_reference,
                )
            if existing_attempt.status in {
                PaymentAttempt.STATUS_INITIATED,
                PaymentAttempt.STATUS_PENDING,
                PaymentAttempt.STATUS_RETRY_PENDING,
                PaymentAttempt.STATUS_FLAGGED,
            }:
                return PaymentRedirect(
                    redirect_url="",
                    client_secret=None,
                    provider_reference=existing_attempt.provider_reference,
                )

        # Run fraud detection before initiating payment
        fraud_result = FraudDetectionService.check_payment_risk(
            tenant_id=cmd.tenant_ctx.tenant_id,
            order_id=order.id,
            amount=order.total_amount,
            currency=order.currency or cmd.tenant_ctx.currency,
        )

        gateway = PaymentGatewayFacade.get(cmd.provider_code, tenant_id=cmd.tenant_ctx.tenant_id)

        payment_attempt = PaymentAttempt.objects.create(
            store_id=cmd.tenant_ctx.store_id,
            order=order,
            provider=gateway.code,
            method=gateway.code,
            amount=order.total_amount,
            currency=order.currency or cmd.tenant_ctx.currency,
            status=PaymentAttempt.STATUS_INITIATED,
            idempotency_key=cmd.idempotency_key,
            ip_address=cmd.ip_address or None,
            user_agent=cmd.user_agent or "",
            risk_score=fraud_result["risk_score"],
            is_flagged=fraud_result["is_flagged"],
        )

        velocity_window_start = timezone.now() - timedelta(minutes=5)
        velocity_count = 0
        if cmd.ip_address:
            velocity_count = PaymentAttempt.objects.filter(
                store_id=cmd.tenant_ctx.store_id,
                ip_address=cmd.ip_address,
                created_at__gte=velocity_window_start,
            ).count()

        risk_score = int(fraud_result["risk_score"])
        if velocity_count > 5:
            risk_score = min(risk_score + 30, 100)
        flagged = risk_score > 70 or velocity_count > 5

        PaymentRisk.objects.create(
            tenant_id=cmd.tenant_ctx.tenant_id,
            store_id=cmd.tenant_ctx.store_id,
            order=order,
            payment_attempt=payment_attempt,
            risk_score=risk_score,
            velocity_count_5min=velocity_count,
            ip_address=cmd.ip_address or None,
            flagged=flagged,
            triggered_rules=list((fraud_result.get("checks") or {}).keys()),
            review_decision="pending",
        )
        payment_attempt.risk_score = risk_score
        payment_attempt.is_flagged = flagged
        payment_attempt.save(update_fields=["risk_score", "is_flagged", "updated_at"])

        if flagged:
            transition_payment_attempt_status(payment_attempt, PaymentAttempt.STATUS_FLAGGED, reason="risk_threshold")
            log_payment_structured(
                event="risk_flagged",
                store_id=cmd.tenant_ctx.store_id,
                order_id=order.id,
                provider=gateway.code,
                idempotency_key=cmd.idempotency_key,
                status="flagged",
                extra={"risk_score": risk_score, "velocity_count": velocity_count},
            )
            return PaymentRedirect(redirect_url="", client_secret=None, provider_reference=None)

        if FraudDetectionService.should_block_payment(risk_score):
            transition_payment_attempt_status(payment_attempt, PaymentAttempt.STATUS_FAILED, reason="risk_blocked")
            raise ValueError(f"Payment blocked due to high risk score: {risk_score}")
        
        # Enforce idempotency - get or create intent
        intent, created = PaymentIntent.objects.select_for_update().get_or_create(
            tenant_id=cmd.tenant_ctx.tenant_id,
            store_id=cmd.tenant_ctx.store_id,
            order=order,
            provider_code=gateway.code,
            idempotency_key=cmd.idempotency_key,
            defaults={
                "amount": order.total_amount,
                "currency": order.currency or cmd.tenant_ctx.currency,
                "status": "pending",
                "risk_score": risk_score,
                "is_flagged": flagged,
                "fraud_checks": fraud_result["checks"],
                "attempt_count": 1,
            },
        )
        
        # If intent already exists, increment attempt count and update fraud info
        if not created:
            intent.attempt_count += 1
            intent.risk_score = risk_score
            intent.is_flagged = flagged
            intent.fraud_checks = fraud_result["checks"]
            intent.save(update_fields=["attempt_count", "risk_score", "is_flagged", "fraud_checks"])

        # Log provider communication with structured logging
        log_key = f"{cmd.idempotency_key}:initiate:{intent.attempt_count}"

        provider_settings = PaymentProviderSettings.objects.filter(
            tenant_id=cmd.tenant_ctx.tenant_id,
            provider_code=gateway.code,
        ).first()
        retry_config = RetryConfig(
            max_attempts=getattr(provider_settings, "retry_max_attempts", 3) or 3,
            initial_delay_ms=200,
            max_delay_ms=3000,
        )

        operation_start = time.monotonic()
        log_payment_structured(
            event="charge_request",
            store_id=cmd.tenant_ctx.store_id,
            order_id=order.id,
            provider=gateway.code,
            idempotency_key=cmd.idempotency_key,
            status="requested",
        )

        with ProviderCommunicationLogger.track_operation(
            tenant_id=cmd.tenant_ctx.tenant_id,
            provider_code=gateway.code,
            operation="initiate_payment",
            request_data={
                "order_id": order.id,
                "amount": str(order.total_amount),
                "currency": order.currency or cmd.tenant_ctx.currency,
                "return_url": cmd.return_url,
            },
            idempotency_key=log_key,
            attempt_number=intent.attempt_count,
        ) as tracker:
            def _invoke_provider():
                return gateway.initiate_payment(
                    order=order,
                    amount=order.total_amount,
                    currency=order.currency or cmd.tenant_ctx.currency,
                    return_url=cmd.return_url,
                )

            def _on_retry(attempt_number, error):
                payment_attempt.retry_count = attempt_number
                payment_attempt.retry_pending = True
                payment_attempt.last_retry_at = timezone.now()
                payment_attempt.raw_response = {
                    **(payment_attempt.raw_response or {}),
                    "last_retry_error": str(error),
                }
                transition_payment_attempt_status(
                    payment_attempt,
                    PaymentAttempt.STATUS_RETRY_PENDING,
                    reason="provider_retry",
                )
                payment_attempt.save(
                    update_fields=[
                        "retry_count",
                        "retry_pending",
                        "last_retry_at",
                        "raw_response",
                        "updated_at",
                    ]
                )
                log_payment_structured(
                    event="retry_attempt",
                    store_id=cmd.tenant_ctx.store_id,
                    order_id=order.id,
                    provider=gateway.code,
                    idempotency_key=cmd.idempotency_key,
                    status="retrying",
                    extra={"retry_attempt": attempt_number, "error": str(error)},
                )

            try:
                redirect = PaymentProviderRetry.execute_with_retry(
                    operation=_invoke_provider,
                    config=retry_config,
                    on_retry=_on_retry,
                )
            except Exception as exc:
                payment_attempt.retry_pending = True
                transition_payment_attempt_status(
                    payment_attempt,
                    PaymentAttempt.STATUS_RETRY_PENDING,
                    reason="provider_timeout_or_error",
                )
                payment_attempt.raw_response = {
                    **(payment_attempt.raw_response or {}),
                    "error": str(exc),
                }
                payment_attempt.save(update_fields=["retry_pending", "raw_response", "updated_at"])
                raise
            
            tracker.set_response({
                "redirect_url": redirect.redirect_url,
                "provider_reference": redirect.provider_reference,
            }, status_code=200)
        
        if not intent.provider_reference:
            intent.provider_reference = redirect.provider_reference or ""
            intent.save(update_fields=["provider_reference"])

        payment_attempt.provider_reference = redirect.provider_reference or ""
        payment_attempt.retry_pending = False
        payment_attempt.raw_response = {
            **(payment_attempt.raw_response or {}),
            "redirect_url": redirect.redirect_url,
            "client_secret": redirect.client_secret,
        }
        transition_payment_attempt_status(payment_attempt, PaymentAttempt.STATUS_PENDING, reason="provider_redirect")
        payment_attempt.save(update_fields=["provider_reference", "retry_pending", "raw_response", "updated_at"])

        duration_ms = int((time.monotonic() - operation_start) * 1000)
        log_payment_structured(
            event="charge_response",
            store_id=cmd.tenant_ctx.store_id,
            order_id=order.id,
            provider=gateway.code,
            idempotency_key=cmd.idempotency_key,
            status="pending",
            duration_ms=duration_ms,
        )

        TelemetryService.track(
            event_name="payment.initiated",
            tenant_ctx=cmd.tenant_ctx,
            actor_ctx=actor_from_tenant_ctx(tenant_ctx=cmd.tenant_ctx, actor_type="CUSTOMER"),
            object_ref=ObjectRef(object_type="ORDER", object_id=order.id),
            properties={
                "provider_code": gateway.code,
                "amount": str(order.total_amount),
                "risk_score": risk_score,
                "is_flagged": flagged,
            },
        )

        if gateway.code == "dummy":
            apply_payment_success(intent=intent, order=order, tenant_ctx=cmd.tenant_ctx)
            return PaymentRedirect(
                redirect_url=cmd.return_url,
                client_secret=None,
                provider_reference=intent.provider_reference,
            )

        return redirect
