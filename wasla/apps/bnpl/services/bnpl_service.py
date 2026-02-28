"""
BNPL Service - Integrates Tabby/Tamara as first-class payment provider.

Financial Integrity Level: CRITICAL

This service:
- Initiates BNPL payment
- Verifies webhook signatures
- Maps provider states to order states
- Handles payment confirmation
"""

import logging
import hmac
import hashlib
from decimal import Decimal
from typing import Dict, Optional, Any
from django.db import transaction
from django.utils import timezone
import json

from apps.bnpl.models import BnplProvider, BnplTransaction
from apps.orders.models import Order

logger = logging.getLogger("wasla.bnpl")


class BnplWebhookError(Exception):
    """Raised when webhook signature verification fails."""
    pass


class BnplIntegrationError(Exception):
    """Raised when BNPL provider integration fails."""
    pass


class BnplService:
    """
    Integrates Tabby/Tamara as payment providers.
    
    Usage:
        service = BnplService()
        
        # 1. Initialize payment
        result = service.initiate_payment(
            order=order,
            provider="tabby",
        )
        # Returns: {"success": True, "payment_url": "https://...", "transaction_id": "txn_123"}
        
        # 2. Webhook callback
        result = service.handle_webhook(
            provider="tabby",
            signature="hmac_signature",
            payload=json.dumps(webhook_data),
        )
        # Returns: {" success": True, "order_id": order_id, "new_status": "paid"}
    """
    
    def initiate_payment(
        self,
        order: Order,
        provider: str = "tabby",  # "tabby" or "tamara"
    ) -> Dict[str, Any]:
        """
        Initiate BNPL payment for order.
        
        Args:
            order: Order instance
            provider: "tabby" or "tamara"
        
        Returns:
            {
                "success": True,
                "payment_url": "https://payment.tabby.ai/...",
                "provider_order_id": "tabby_order_123",
                "transaction_id": 456,  # BnplTransaction.id
            }
        
        Or on error:
            {
                "success": False,
                "error": "BNPL provider not configured",
            }
        """
        try:
            # Check provider is configured
            bnpl_provider = BnplProvider.objects.filter(
                store_id=order.store_id,
                provider=provider,
                is_active=True,
            ).first()
            
            if not bnpl_provider:
                return {
                    "success": False,
                    "error": f"BNPL provider '{provider}' not configured for store",
                }
            
            # Create BNPL transaction
            with transaction.atomic():
                bnpl_txn = BnplTransaction.objects.create(
                    order=order,
                    provider=provider,
                    provider_order_id=f"{provider}_{order.id}_{timezone.now().timestamp()}",
                    amount=order.total_amount,
                    currency=order.currency,
                    customer_email=order.customer_email,
                    customer_phone=order.customer_phone,
                    status=BnplTransaction.STATUS_PENDING,
                    installment_count=3,
                    installment_amount=order.total_amount / Decimal("3"),
                )
                
                # Build payment URL
                payment_url = self._build_payment_url(bnpl_provider, bnpl_txn, order)
                bnpl_txn.payment_url = payment_url
                bnpl_txn.save(update_fields=["payment_url"])
                
                logger.info(
                    f"BNPL payment initiated",
                    extra={
                        "order_id": order.id,
                        "provider": provider,
                        "transaction_id": bnpl_txn.id,
                        "amount": str(order.total_amount),
                    }
                )
                
                return {
                    "success": True,
                    "payment_url": payment_url,
                    "provider_order_id": bnpl_txn.provider_order_id,
                    "transaction_id": bnpl_txn.id,
                }
        
        except Exception as e:
            logger.exception(f"Error initiating BNPL payment: {e}")
            return {
                "success": False,
                "error": f"Error initiating payment: {str(e)}",
            }
    
    def _build_payment_url(
        self,
        bnpl_provider: BnplProvider,
        bnpl_txn: BnplTransaction,
        order: Order,
    ) -> str:
        """
        Build payment URL for provider.
        
        In production, this integrates with provider API.
        For MVP, returns placeholder URL.
        """
        if bnpl_provider.provider == BnplProvider.PROVIDER_TABBY:
            return (
                f"https://checkout.tabby.ai/"
                f"?order_id={bnpl_txn.provider_order_id}"
                f"&merchant_id={bnpl_provider.merchant_id}"
            )
        elif bnpl_provider.provider == BnplProvider.PROVIDER_TAMARA:
            return (
                f"https://checkout.tamara.co/"
                f"?order_id={bnpl_txn.provider_order_id}"
                f"&merchant_id={bnpl_provider.merchant_id}"
            )
        return ""
    
    def handle_webhook(
        self,
        provider: str,
        signature: str,
        payload: str,  # JSON string
    ) -> Dict[str, Any]:
        """
        Handle BNPL provider webhook.
        
        Args:
            provider: "tabby" or "tamara"
            signature: HMAC signature from provider
            payload: JSON payload string
        
        Returns:
            {
                "success": True,
                "order_id": order.id,
                "new_status": "paid",
            }
        
        Raises:
            BnplWebhookError if signature invalid
        """
        try:
            # Verify webhook signature
            webhook_data = json.loads(payload)
            
            if not self._verify_webhook_signature(provider, signature, payload):
                raise BnplWebhookError("Invalid webhook signature")
            
            # Extract provider order ID
            provider_order_id = webhook_data.get("order_id")
            if not provider_order_id:
                raise BnplWebhookError("order_id not in webhook payload")
            
            # Find BNPL transaction
            bnpl_txn = BnplTransaction.objects.select_for_update().filter(
                provider=provider,
                provider_order_id=provider_order_id,
            ).first()
            
            if not bnpl_txn:
                logger.warning(
                    f"BNPL webhook for unknown order: {provider_order_id}",
                    extra={"provider": provider}
                )
                return {
                    "success": False,
                    "error": f"BNPL transaction not found: {provider_order_id}",
                }
            
            # Map provider status to order status
            provider_status = webhook_data.get("status")
            order_status_mapping = {
                "approved": BnplTransaction.STATUS_APPROVED,
                "authorized": BnplTransaction.STATUS_AUTHORIZED,
                "rejected": BnplTransaction.STATUS_REJECTED,
                "paid": BnplTransaction.STATUS_PAID,
                "cancelled": BnplTransaction.STATUS_CANCELLED,
            }
            
            new_bnpl_status = order_status_mapping.get(provider_status, BnplTransaction.STATUS_PENDING)
            
            # Update transaction
            bnpl_txn.status = new_bnpl_status
            bnpl_txn.provider_reference = webhook_data.get("reference", "")
            bnpl_txn.save(update_fields=["status", "provider_reference"])
            
            # Update order status based on BNPL status
            order = bnpl_txn.order
            with transaction.atomic():
                if new_bnpl_status == BnplTransaction.STATUS_APPROVED:
                    order.payment_status = "confirmed"
                    order.status = "paid"
                elif new_bnpl_status == BnplTransaction.STATUS_REJECTED:
                    order.payment_status = "failed"
                    order.status = "cancelled"
                elif new_bnpl_status == BnplTransaction.STATUS_PAID:
                    order.payment_status = "confirmed"
                    order.status = "processing"
                
                order.save(update_fields=["payment_status", "status"])
            
            logger.info(
                f"BNPL webhook processed",
                extra={
                    "order_id": order.id,
                    "provider": provider,
                    "new_status": new_bnpl_status,
                }
            )
            
            return {
                "success": True,
                "order_id": order.id,
                "new_status": new_bnpl_status,
            }
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in BNPL webhook: {e}")
            return {
                "success": False,
                "error": f"Invalid JSON: {str(e)}",
            }
        except Exception as e:
            logger.exception(f"Error processing BNPL webhook: {e}")
            return {
                "success": False,
                "error": f"Error processing webhook: {str(e)}",
            }
    
    def _verify_webhook_signature(self, provider: str, signature: str, payload: str) -> bool:
        """
        Verify webhook signature from provider.
        
        Uses HMAC-SHA256 signature verification.
        """
        try:
            # Get provider settings (in production, fetch from config)
            # For MVP, use placeholder
            secret_key = "webhook_secret_key"  # Should come from settings
            
            expected_signature = hmac.new(
                secret_key.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
        
        except Exception as e:
            logger.error(f"Error verifying signature: {e}")
            return False
    
    def get_transaction_status(self, transaction_id: int) -> Optional[Dict[str, Any]]:
        """Get BNPL transaction status."""
        try:
            txn = BnplTransaction.objects.get(id=transaction_id)
            return {
                "status": txn.status,
                "amount": str(txn.amount),
                "provider": txn.provider,
                "created_at": txn.created_at.isoformat(),
            }
        except BnplTransaction.DoesNotExist:
            return None
