"""
Refund Service - Handles refunds via payment orchestrator.

Integrates RMA flow with payment gateway refunds.
Supports partial refunds with audit trail.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import logging

from apps.orders.models_extended import RefundTransaction, RMA, ReturnItem
from apps.orders.models import Order
from apps.payments.infrastructure.orchestrator import PaymentOrchestrator

logger = logging.getLogger("orders.refund")


class RefundService:
    """Service for managing refunds through payment providers."""
    
    @staticmethod
    @transaction.atomic
    def initiate_refund(
        order: Order,
        amount: Decimal,
        rma: RMA | None = None,
        reason: str = "Customer return",
    ) -> RefundTransaction:
        """
        Initiate refund for an order.
        
        Args:
            order: Order to refund
            amount: Refund amount
            rma: Associated RMA instance
            reason: Refund reason description
            
        Returns:
            RefundTransaction instance
            
        Raises:
            ValueError: If refundable amount exceeded
        """
        # Validate refund amount
        refundable = order.total_amount - order.refunded_amount
        if amount > refundable:
            raise ValueError(
                f"Refund amount {amount} exceeds refundable {refundable}"
            )
        
        # Create refund transaction record
        refund_tx = RefundTransaction.objects.create(
            tenant_id=order.tenant_id,
            store_id=order.store_id,
            order=order,
            rma=rma,
            amount=amount,
            currency=order.currency,
            refund_reason=reason,
            status=RefundTransaction.STATUS_INITIATED,
        )
        
        logger.info(
            "Refund initiated",
            extra={
                "order_id": order.id,
                "refund_id": str(refund_tx.id),
                "amount": str(amount),
                "currency": order.currency,
            },
        )
        
        return refund_tx
    
    @staticmethod
    @transaction.atomic
    def process_refund(refund_tx: RefundTransaction) -> RefundTransaction:
        """
        Process refund through payment provider.
        
        Args:
            refund_tx: RefundTransaction to process
            
        Returns:
            Updated RefundTransaction
        """
        order = refund_tx.order
        
        # Get original payment attempt (simplified - use latest successful)
        from apps.payments.models import PaymentAttempt
        payment_attempt = PaymentAttempt.objects.filter(
            order_id=order.id,
            status__in=["confirmed", "completed"],
        ).order_by("-created_at").first()
        
        if not payment_attempt:
            logger.warning(
                "No successful payment found for refund",
                extra={"order_id": order.id, "refund_id": str(refund_tx.id)},
            )
            refund_tx.status = RefundTransaction.STATUS_FAILED
            refund_tx.gateway_response = {"error": "No payment to refund"}
            refund_tx.save(update_fields=["status", "gateway_response"])
            return refund_tx
        
        try:
            refund_tx.status = RefundTransaction.STATUS_PROCESSING
            refund_tx.save(update_fields=["status"])
            
            # Call payment orchestrator to process refund
            orchestrator = PaymentOrchestrator()
            result = orchestrator.refund_payment(
                payment_attempt=payment_attempt,
                amount=refund_tx.amount,
                reason=refund_tx.refund_reason,
            )
            
            if result.get("ok"):
                refund_tx.status = RefundTransaction.STATUS_COMPLETED
                refund_tx.refund_id = result.get("refund_id", "")
                refund_tx.gateway_response = result
                refund_tx.completed_at = timezone.now()
                
                # Update order refunded amount
                order.refunded_amount += refund_tx.amount
                order.save(update_fields=["refunded_amount"])
                
                logger.info(
                    "Refund completed",
                    extra={
                        "order_id": order.id,
                        "refund_id": str(refund_tx.id),
                        "amount": str(refund_tx.amount),
                        "provider": payment_attempt.provider,
                    },
                )
            else:
                refund_tx.status = RefundTransaction.STATUS_FAILED
                refund_tx.gateway_response = result
                
                logger.error(
                    "Refund failed",
                    extra={
                        "order_id": order.id,
                        "refund_id": str(refund_tx.id),
                        "error": result.get("error", "Unknown error"),
                    },
                )
            
            refund_tx.save(update_fields=["status", "refund_id", "gateway_response", "completed_at"])
            
        except Exception as e:
            refund_tx.status = RefundTransaction.STATUS_FAILED
            refund_tx.gateway_response = {"error": str(e)}
            refund_tx.save(update_fields=["status", "gateway_response"])
            
            logger.exception(
                "Refund processing error",
                extra={
                    "order_id": order.id,
                    "refund_id": str(refund_tx.id),
                    "error": str(e),
                },
            )
        
        return refund_tx
    
    @staticmethod
    @transaction.atomic
    def process_rma_refund(rma: RMA) -> list[RefundTransaction]:
        """
        Process refund for a complete RMA.
        
        Args:
            rma: ReturnMerchandiseAuthorization instance
            
        Returns:
            List of RefundTransaction instances
        """
        refunds = []
        total_refund = Decimal("0")
        
        for return_item in rma.items.filter(status=ReturnItem.STATUS_APPROVED):
            # Calculate refund for this item
            order_item = return_item.order_item
            item_refund = order_item.price * return_item.quantity_returned
            
            refund_tx = RefundService.initiate_refund(
                order=rma.order,
                amount=item_refund,
                rma=rma,
                reason=f"RMA {rma.rma_number} - Return of {order_item.product.name}",
            )
            
            # Process refund
            RefundService.process_refund(refund_tx)
            refunds.append(refund_tx)
            total_refund += item_refund
            
            # Update return item status
            return_item.refund_amount = item_refund
            return_item.status = ReturnItem.STATUS_REFUNDED
            return_item.save(update_fields=["refund_amount", "status"])
        
        # Update order status based on total refund
        order = rma.order
        if order.refunded_amount >= order.total_amount:
            order.status = "refunded"
        elif order.refunded_amount > 0:
            order.status = "partially_refunded"
        order.save(update_fields=["status", "refunded_amount"])
        
        logger.info(
            "RMA refund processed",
            extra={
                "rma_number": rma.rma_number,
                "order_id": order.id,
                "total_refund": str(total_refund),
                "num_refunds": len(refunds),
            },
        )
        
        return refunds
    
    @staticmethod
    def calculate_refundable_amount(order: Order) -> Decimal:
        """Get remaining refundable amount for an order."""
        return order.total_amount - order.refunded_amount
