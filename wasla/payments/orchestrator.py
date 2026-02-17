"""Payment Orchestrator - Central payment processing service."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from django.db import transaction

from orders.models import Order
from payments.models import PaymentIntent, PaymentProviderSettings, RefundRecord
from payments.infrastructure.gateways.tap_gateway import TapProvider
from payments.infrastructure.gateways.stripe_gateway import StripeProvider
from payments.infrastructure.gateways.paypal_gateway import PayPalProvider
from payments.domain.ports import PaymentRedirect
from tenants.domain.tenant_context import TenantContext


class PaymentOrchestrator:
    """
    Central payment orchestrator for handling multi-provider payments.
    
    Responsibilities:
    - Provider selection and instantiation
    - Tenant-specific credential injection
    - Idempotency enforcement
    - Transaction safety
    - Standardized response handling
    """

    PROVIDER_MAP = {
        "tap": TapProvider,
        "stripe": StripeProvider,
        "paypal": PayPalProvider,
    }

    @staticmethod
    @transaction.atomic
    def initiate_payment(
        order: Order,
        provider_code: str,
        tenant_ctx: TenantContext,
        return_url: str,
    ) -> PaymentRedirect:
        """
        Initiate payment via specified provider.
        
        Flow:
        1. Validate provider availability for tenant
        2. Create payment intent with idempotency key
        3. Call provider API
        4. Return redirect URL and client secret
        """
        # Get provider settings for this tenant
        settings = PaymentProviderSettings.objects.filter(
            tenant_id=tenant_ctx.tenant_id,
            provider_code=provider_code,
            is_enabled=True,
        ).first()

        if not settings:
            raise ValueError(f"Provider {provider_code} not available for this store")

        # Check for existing pending payment
        existing = PaymentIntent.objects.filter(
            order=order,
            provider_code=provider_code,
            status="pending",
        ).first()

        if existing:
            raise ValueError("Payment already in progress for this order")

        # Create idempotency key
        idempotency_key = f"{provider_code}:order_{order.id}:{tenant_ctx.tenant_id}"

        # Get or create payment intent
        intent, created = PaymentIntent.objects.get_or_create(
            store_id=tenant_ctx.tenant_id,
            order=order,
            provider_code=provider_code,
            idempotency_key=idempotency_key,
            defaults={
                "amount": order.total_amount,
                "currency": order.currency or tenant_ctx.currency,
                "status": "pending",
            },
        )

        if not created and intent.status != "pending":
            # Already processed, return existing reference
            return PaymentRedirect(
                redirect_url="",
                client_secret=intent.provider_reference,
                provider_reference=intent.provider_reference,
            )

        # Instantiate provider
        provider_class = PaymentOrchestrator.PROVIDER_MAP.get(provider_code)
        if not provider_class:
            raise ValueError(f"Unknown provider: {provider_code}")

        provider = provider_class(settings)

        # Call provider API
        result = provider.initiate_payment(
            order=order,
            amount=intent.amount,
            currency=intent.currency,
            return_url=return_url,
        )

        # Update intent with provider reference
        if result.provider_reference:
            intent.provider_reference = result.provider_reference
            intent.save(update_fields=["provider_reference"])

        return result

    @staticmethod
    @transaction.atomic
    def refund(
        intent_id: int,
        amount: Optional[Decimal] = None,
        reason: str = "",
        requested_by: str = "system",
    ) -> RefundRecord:
        """
        Process refund for a payment.
        
        Flow:
        1. Verify payment intent exists and is paid
        2. Get provider configuration
        3. Call provider refund API
        4. Create and store refund record
        """
        intent = PaymentIntent.objects.select_for_update().filter(
            id=intent_id,
            status="succeeded",
        ).first()

        if not intent:
            raise ValueError("Payment not found or not yet succeeded")

        # Use full amount if not specified
        if amount is None:
            amount = intent.amount

        if amount > intent.amount:
            raise ValueError("Refund amount exceeds payment amount")

        # Get provider settings
        settings = PaymentProviderSettings.objects.filter(
            tenant_id=intent.store_id,
            provider_code=intent.provider_code,
            is_enabled=True,
        ).first()

        if not settings:
            raise ValueError("Provider configuration not found")

        # Instantiate provider
        provider_class = PaymentOrchestrator.PROVIDER_MAP.get(intent.provider_code)
        if not provider_class:
            raise ValueError(f"Unknown provider: {intent.provider_code}")

        provider = provider_class(settings)

        # Call provider refund API
        try:
            refund_ref = provider.refund(
                payment_reference=intent.provider_reference,
                amount=amount,
                reason=reason,
            )
        except Exception as exc:
            refund_ref = ""
            status = RefundRecord.STATUS_FAILED
        else:
            status = RefundRecord.STATUS_APPROVED

        # Create refund record
        refund = RefundRecord.objects.create(
            payment_intent=intent,
            amount=amount,
            currency=intent.currency,
            provider_reference=refund_ref,
            status=status,
            reason=reason,
            requested_by=requested_by,
        )

        return refund

    @staticmethod
    def get_provider_fees(
        tenant_id: int,
        provider_code: str,
        amount: Decimal,
    ) -> dict:
        """
        Calculate provider and Wasla fees for a payment.
        
        Returns:
            {
                'gross_amount': Decimal,
                'provider_fee': Decimal,
                'wasla_commission': Decimal,
                'net_amount': Decimal,
            }
        """
        settings = PaymentProviderSettings.objects.filter(
            tenant_id=tenant_id,
            provider_code=provider_code,
        ).first()

        if not settings:
            return {
                "gross_amount": amount,
                "provider_fee": Decimal("0"),
                "wasla_commission": Decimal("0"),
                "net_amount": amount,
            }

        provider_fee = (amount * settings.transaction_fee_percent / Decimal("100")).quantize(
            Decimal("0.01")
        )
        wasla_commission = (amount * settings.wasla_commission_percent / Decimal("100")).quantize(
            Decimal("0.01")
        )
        net_amount = amount - provider_fee - wasla_commission

        return {
            "gross_amount": amount,
            "provider_fee": provider_fee,
            "wasla_commission": wasla_commission,
            "net_amount": net_amount,
        }
