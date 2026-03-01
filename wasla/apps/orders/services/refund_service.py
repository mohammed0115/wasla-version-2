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

from apps.orders.models import RefundTransaction, RMA, ReturnItem, Order
from apps.orders.services.returns_service import RefundsService
from apps.payments.gateway import PaymentGatewayClient

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
        refund_tx = RefundsService.request_refund(
            order=order,
            amount=amount,
            reason=reason,
            rma=rma,
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
        try:
            gateway = PaymentGatewayClient(tenant_id=refund_tx.tenant_id)
            return RefundsService.process_refund(refund_tx, gateway)
        except Exception as e:
            refund_tx.status = RefundTransaction.STATUS_FAILED
            refund_tx.gateway_response = {"error": str(e)}
            refund_tx.save(update_fields=["status", "gateway_response"])
            logger.exception(
                "Refund processing error",
                extra={
                    "order_id": refund_tx.order_id,
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
