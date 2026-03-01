"""BNPL Provider adapters for Tabby and Tamara."""

import hmac
import hashlib
from abc import ABC, abstractmethod
from decimal import Decimal
import requests
from django.conf import settings
from core.infrastructure.circuit_breaker import CircuitBreaker
from apps.bnpl.models import BnplProvider, BnplTransaction, BnplWebhookLog
from apps.orders.models import Order


class BnplProviderInterface(ABC):
    """Abstract interface for BNPL providers."""

    def __init__(self, provider_config: BnplProvider):
        self.config = provider_config
        self.api_url = provider_config.get_api_url()

    @abstractmethod
    def create_session(self, order: Order) -> dict:
        """
        Create a payment session.

        Args:
            order: Order instance

        Returns:
            {
                "checkout_url": "...",
                "session_id": "...",
                "order_id": "..."
            }
        """
        raise NotImplementedError

    @abstractmethod
    def get_payment_status(self, provider_order_id: str) -> dict:
        """Get payment status from provider."""
        raise NotImplementedError

    @abstractmethod
    def verify_webhook_signature(self, payload: str, signature: str) -> bool:
        """Verify webhook signature."""
        raise NotImplementedError

    @abstractmethod
    def refund(self, provider_order_id: str, amount: Decimal) -> dict:
        """Refund a payment."""
        raise NotImplementedError


class TabbyAdapter(BnplProviderInterface):
    """Tabby payment provider adapter."""

    def create_session(self, order: Order) -> dict:
        """Create Tabby checkout session."""
        url = f"{self.api_url}/api/v1/checkout"

        shipping = order.shipping_address
        buyer_name = shipping.full_name or order.customer_name or "Customer"
        buyer_email = order.email
        buyer_phone = shipping.phone or order.customer_phone or None

        # Prepare order data
        payload = {
            "payment": {
                "amount": float(order.total_amount),
                "currency": "SAR",
                "description": f"Order #{order.id}",
                "buyer": {
                    "email": buyer_email,
                    "phone": buyer_phone,
                    "name": buyer_name,
                },
                "order": {
                    "reference_id": str(order.id),
                    "items": [
                        {
                            "title": item.product.name,
                            "description": "",
                            "quantity": item.quantity,
                            "unit_price": float(item.unit_price_snapshot),
                            "reference_id": f"item_{item.id}",
                        }
                        for item in order.items.all()
                    ],
                },
            },
            "lang": "ar",
            "merchant_code": self.config.merchant_id,
            "merchant_urls": {
                "success": f"{settings.SITE_URL}/checkout/tabby-success/",
                "failure": f"{settings.SITE_URL}/checkout/tabby-failure/",
                "cancel": f"{settings.SITE_URL}/checkout/cancel/",
            },
        }

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        try:
            breaker = CircuitBreaker("bnpl.tabby")
            response = breaker.call(requests.post, url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            return {
                "checkout_url": data.get("checkout", {}).get("redirect_url"),
                "session_id": data.get("id"),
                "order_id": data.get("order", {}).get("reference_id"),
                "status": "success",
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }

    def get_payment_status(self, provider_order_id: str) -> dict:
        """Get payment status from Tabby."""
        url = f"{self.api_url}/api/v1/payments/{provider_order_id}"

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
        }

        try:
            breaker = CircuitBreaker("bnpl.tabby")
            response = breaker.call(requests.get, url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            status_map = {
                "CREATED": BnplTransaction.STATUS_PENDING,
                "APPROVED": BnplTransaction.STATUS_APPROVED,
                "REJECTED": BnplTransaction.STATUS_REJECTED,
                "CLOSED": BnplTransaction.STATUS_PAID,
                "EXPIRED": BnplTransaction.STATUS_CANCELLED,
            }

            return {
                "status": status_map.get(data.get("status"), "unknown"),
                "provider_status": data.get("status"),
                "data": data,
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }

    def verify_webhook_signature(self, payload: str, signature: str) -> bool:
        """Verify Tabby webhook signature."""
        if not self.config.webhook_secret:
            return False

        computed_signature = hmac.new(
            self.config.webhook_secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(computed_signature, signature)

    def refund(self, provider_order_id: str, amount: Decimal) -> dict:
        """Refund a Tabby payment."""
        url = f"{self.api_url}/api/v1/payments/{provider_order_id}/refunds"

        payload = {
            "amount": float(amount),
        }

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        try:
            breaker = CircuitBreaker("bnpl.tabby")
            response = breaker.call(requests.post, url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            return {"status": "success", "data": response.json()}
        except Exception as e:
            return {"status": "error", "error": str(e)}


class TamaraAdapter(BnplProviderInterface):
    """Tamara payment provider adapter."""

    def create_session(self, order: Order) -> dict:
        """Create Tamara checkout session."""
        url = f"{self.api_url}/api/v1/checkout"

        shipping = order.shipping_address
        buyer_name = shipping.full_name or order.customer_name or "Customer"
        first_name = buyer_name.split()[0] if buyer_name else "Customer"

        payload = {
            "order_reference_id": str(order.id),
            "total_amount": {
                "amount": float(order.total_amount),
                "currency": "SAR",
            },
            "items": [
                {
                    "name": item.product.name,
                    "quantity": item.quantity,
                    "unit_price": {
                        "amount": float(item.unit_price_snapshot),
                        "currency": "SAR",
                    },
                    "reference_id": f"item_{item.id}",
                }
                for item in order.items.all()
            ],
            "customer": {
                "first_name": first_name,
                "email": order.email,
                "phone": shipping.phone or order.customer_phone or None,
            },
            "shipping_address": {
                "country_code": "SA",
                "region": shipping.city or "",
                "address_line1": shipping.line1 or "",
                "address_line2": shipping.line2 or "",
            },
            "payment_type": "PAY_BY_INSTALMENTS",
            "instalments": 3,
            "merchant_url": {
                "success": f"{settings.SITE_URL}/checkout/tamara-success/",
                "failure": f"{settings.SITE_URL}/checkout/tamara-failure/",
                "cancel": f"{settings.SITE_URL}/checkout/cancel/",
                "notification": f"{settings.SITE_URL}/api/webhooks/tamara/",
            },
        }

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        try:
            breaker = CircuitBreaker("bnpl.tamara")
            response = breaker.call(requests.post, url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            checkout_id = data.get("checkout", {}).get("id")

            return {
                "checkout_url": f"{self.api_url}/checkout/{checkout_id}",
                "session_id": checkout_id,
                "order_id": str(order.id),
                "status": "success",
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }

    def get_payment_status(self, provider_order_id: str) -> dict:
        """Get payment status from Tamara."""
        url = f"{self.api_url}/api/v1/orders/{provider_order_id}"

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
        }

        try:
            breaker = CircuitBreaker("bnpl.tamara")
            response = breaker.call(requests.get, url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            status_map = {
                "NEW": BnplTransaction.STATUS_PENDING,
                "APPROVED": BnplTransaction.STATUS_APPROVED,
                "DECLINED": BnplTransaction.STATUS_REJECTED,
                "CANCELLED": BnplTransaction.STATUS_CANCELLED,
                "COMPLETED": BnplTransaction.STATUS_PAID,
            }

            return {
                "status": status_map.get(data.get("status"), "unknown"),
                "provider_status": data.get("status"),
                "data": data,
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }

    def verify_webhook_signature(self, payload: str, signature: str) -> bool:
        """Verify Tamara webhook signature."""
        if not self.config.webhook_secret:
            return False

        computed_signature = hmac.new(
            self.config.webhook_secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(computed_signature, signature)

    def refund(self, provider_order_id: str, amount: Decimal) -> dict:
        """Refund a Tamara payment."""
        url = f"{self.api_url}/api/v1/orders/{provider_order_id}/reverse"

        payload = {
            "amount": {
                "amount": float(amount),
                "currency": "SAR",
            },
        }

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        try:
            breaker = CircuitBreaker("bnpl.tamara")
            response = breaker.call(requests.post, url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            return {"status": "success", "data": response.json()}
        except Exception as e:
            return {"status": "error", "error": str(e)}


class BnplPaymentOrchestrator:
    """Routes BNPL payments to appropriate provider."""

    ADAPTER_MAP = {
        BnplProvider.PROVIDER_TABBY: TabbyAdapter,
        BnplProvider.PROVIDER_TAMARA: TamaraAdapter,
    }

    @staticmethod
    def create_payment_session(order: Order, provider: str) -> dict:
        """
        Create a payment session with specified provider.

        Args:
            order: Order instance
            provider: "tabby" or "tamara"

        Returns:
            {
                "status": "success|error",
                "checkout_url": "...",
                "session_id": "...",
            }
        """
        try:
            # Get provider config
            config = BnplProvider.objects.get(
                store_id=order.store_id,
                provider=provider,
                is_active=True,
            )
        except BnplProvider.DoesNotExist:
            return {
                "status": "error",
                "error": f"Provider {provider} not configured",
            }

        # Get adapter
        adapter_class = BnplPaymentOrchestrator.ADAPTER_MAP.get(provider)
        if not adapter_class:
            return {
                "status": "error",
                "error": f"Unknown provider: {provider}",
            }

        # Create session
        adapter = adapter_class(config)
        return adapter.create_session(order)

    @staticmethod
    def get_adapter(provider_config: BnplProvider) -> BnplProviderInterface:
        """Get adapter for provider."""
        adapter_class = BnplPaymentOrchestrator.ADAPTER_MAP.get(
            provider_config.provider
        )
        if not adapter_class:
            raise ValueError(f"Unknown provider: {provider_config.provider}")

        return adapter_class(provider_config)

    @staticmethod
    def process_webhook(provider: str, payload: dict, signature: str) -> dict:
        """
        Process webhook from BNPL provider.

        Args:
            provider: "tabby" or "tamara"
            payload: Webhook payload
            signature: Request signature for verification

        Returns:
            {"status": "success|error", "message": "..."}
        """
        # Find transaction
        provider_order_id = payload.get("order", {}).get("reference_id") or payload.get(
            "order_reference_id"
        )

        try:
            transaction = BnplTransaction.objects.get(
                provider_order_id=provider_order_id,
                provider=provider,
            )
        except BnplTransaction.DoesNotExist:
            return {
                "status": "error",
                "error": "Transaction not found",
            }

        # Get provider config
        try:
            config = BnplProvider.objects.get(
                store_id=transaction.order.store_id,
                provider=provider,
            )
        except BnplProvider.DoesNotExist:
            return {
                "status": "error",
                "error": "Provider not configured",
            }

        # Verify signature
        adapter = BnplPaymentOrchestrator.get_adapter(config)
        import json

        payload_str = json.dumps(payload, sort_keys=True)
        is_valid = adapter.verify_webhook_signature(payload_str, signature)

        # Log webhook
        event_type = payload.get("event_type", "unknown")
        status = payload.get("status", payload.get("order", {}).get("status"))

        webhook_log = BnplWebhookLog.objects.create(
            transaction=transaction,
            event_type=event_type,
            status=status,
            payload=payload,
            signature_verified=is_valid,
        )

        if not is_valid:
            return {
                "status": "error",
                "error": "Invalid signature",
            }

        # Update transaction status
        status_map = {
            "APPROVED": BnplTransaction.STATUS_APPROVED,
            "AUTHORIZED": BnplTransaction.STATUS_AUTHORIZED,
            "REJECTED": BnplTransaction.STATUS_REJECTED,
            "CANCELLED": BnplTransaction.STATUS_CANCELLED,
            "COMPLETED": BnplTransaction.STATUS_PAID,
            "PAID": BnplTransaction.STATUS_PAID,
            "approved": BnplTransaction.STATUS_APPROVED,
            "authorized": BnplTransaction.STATUS_AUTHORIZED,
            "failed": BnplTransaction.STATUS_REJECTED,
            "cancelled": BnplTransaction.STATUS_CANCELLED,
        }

        new_status = status_map.get(status)
        if new_status:
            transaction.status = new_status
            transaction.response_data = payload
            transaction.save()

            webhook_log.processed = True
            webhook_log.save()

            # Update order status if payment approved
            if new_status == BnplTransaction.STATUS_APPROVED:
                transaction.order.status = "processing"
                transaction.order.payment_status = "confirmed"
                transaction.order.save(update_fields=["status", "payment_status"])

        return {
            "status": "success",
            "message": f"Webhook processed: {event_type}",
        }
