"""
Returns & Refunds Service

Manages RMA (Return Merchandise Authorization), return items, and refund processing.
Supports partial returns and exchanges with payment orchestrator integration.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import uuid

from django.db.models import Sum

from ..models import Order, OrderItem, RMA, ReturnItem, RefundTransaction


class ReturnsService:
    """
    Manage returns and exchanges with RMA workflow.
    
    RMA Workflow:
    1. request_rma() - Customer requests return
    2. approve_rma() - Store approves return (generates RMA #)
    3. track_shipment() - Customer ships item back
    4. receive_return() - Store receives returned item
    5. inspect_return() - Store inspects condition
    6. complete_rma() - Process refund/exchange
    """
    
    @staticmethod
    def get_next_rma_number(tenant_id: int, store_id: int) -> str:
        """
        Generate next RMA number.
        Format: RMA-<TENANT>-<STORE>-<SEQUENTIAL>
        """
        last_rma = RMA.objects.filter(
            tenant_id=tenant_id,
            order__store_id=store_id,
        ).order_by('-id').first()
        
        sequence = 1
        if last_rma:
            parts = last_rma.rma_number.split('-')
            if len(parts) == 4:
                try:
                    sequence = int(parts[3]) + 1
                except (ValueError, IndexError):
                    sequence = last_rma.id + 1
        
        return f"RMA-{tenant_id:06d}-{store_id:06d}-{sequence:08d}"
    
    @staticmethod
    @transaction.atomic
    def request_rma(
        order: Order,
        items: list[dict],
        reason: str,
        reason_description: str = "",
        is_exchange: bool = False,
        exchange_product_id: int | None = None,
    ) -> RMA:
        """
        Create new RMA request.
        
        Args:
            order: The Order to return
            items: List of dicts with {'order_item_id': X, 'quantity': Y}
            reason: RMA reason code
            reason_description: Detailed reason
            is_exchange: True if exchange instead of return
            exchange_product_id: Product ID for exchange
            
        Returns:
            Created RMA instance
        """
        from apps.catalog.models import Product
        
        exchange_product = None
        if is_exchange and exchange_product_id:
            exchange_product = Product.objects.get(id=exchange_product_id)
        
        rma_number = ReturnsService.get_next_rma_number(order.tenant_id, order.store_id)
        
        rma = RMA.objects.create(
            tenant_id=order.tenant_id,
            store_id=order.store_id,
            order=order,
            rma_number=rma_number,
            reason=reason,
            reason_description=reason_description,
            is_exchange=is_exchange,
            exchange_product=exchange_product,
            status=RMA.STATUS_REQUESTED,
        )
        
        # Create return items
        total_refund = Decimal("0.00")
        for item_spec in items:
            order_item = OrderItem.objects.get(
                id=item_spec['order_item_id'],
                order=order
            )
            quantity = item_spec['quantity']
            
            # Refund = quantity * unit price
            refund_amount = quantity * order_item.price
            total_refund += refund_amount
            
            ReturnItem.objects.create(
                tenant_id=order.tenant_id,
                rma=rma,
                order_item=order_item,
                quantity_returned=quantity,
                condition=ReturnItem.CONDITION_USED,
                refund_amount=refund_amount,
                status=ReturnItem.STATUS_PENDING,
            )
        
        return rma
    
    @staticmethod
    @transaction.atomic
    def approve_rma(rma: RMA, comment: str = "") -> RMA:
        """
        Approve RMA request.
        
        Args:
            rma: The RMA to approve
            comment: Optional approval comment
            
        Returns:
            Updated RMA instance
        """
        if rma.status != RMA.STATUS_REQUESTED:
            raise ValueError(f"Cannot approve RMA in {rma.status} status")
        
        rma.status = RMA.STATUS_APPROVED
        rma.approved_at = timezone.now()
        rma.save(update_fields=["status", "approved_at"])
        
        return rma
    
    @staticmethod
    @transaction.atomic
    def reject_rma(rma: RMA, reason: str = "") -> RMA:
        """
        Reject RMA request.
        
        Args:
            rma: The RMA to reject
            reason: Reason for rejection
            
        Returns:
            Updated RMA instance
        """
        if rma.status != RMA.STATUS_REQUESTED:
            raise ValueError(f"Cannot reject RMA in {rma.status} status")
        
        rma.status = RMA.STATUS_REJECTED
        rma.reason_description = f"REJECTED: {reason}\n{rma.reason_description}"
        rma.save(update_fields=["status", "reason_description"])
        
        return rma
    
    @staticmethod
    @transaction.atomic
    def track_return_shipment(
        rma: RMA,
        carrier: str,
        tracking_number: str,
    ) -> RMA:
        """
        Record return shipment tracking.
        
        Args:
            rma: The RMA
            carrier: Carrier name (DHL, FedEx, etc)
            tracking_number: Tracking number
            
        Returns:
            Updated RMA instance
        """
        if rma.status != RMA.STATUS_APPROVED:
            raise ValueError(f"Cannot track return for RMA in {rma.status} status")
        
        rma.status = RMA.STATUS_IN_TRANSIT
        rma.return_carrier = carrier
        rma.return_tracking_number = tracking_number
        rma.save(update_fields=["status", "return_carrier", "return_tracking_number"])
        
        return rma
    
    @staticmethod
    @transaction.atomic
    def receive_return(rma: RMA) -> RMA:
        """
        Mark return as received at warehouse.
        
        Args:
            rma: The RMA
            
        Returns:
            Updated RMA instance
        """
        if rma.status != RMA.STATUS_IN_TRANSIT:
            raise ValueError(f"Cannot receive return for RMA in {rma.status} status")
        
        rma.status = RMA.STATUS_RECEIVED
        rma.received_at = timezone.now()
        rma.save(update_fields=["status", "received_at"])
        
        return rma
    
    @staticmethod
    @transaction.atomic
    def inspect_return(
        rma: RMA,
        inspections: list[dict],
    ) -> RMA:
        """
        Inspect returned items and update condition/refund status.
        
        Args:
            rma: The RMA
            inspections: List of dicts with {'return_item_id': X, 'condition': Y, 'refund_amount': Z}
            
        Returns:
            Updated RMA instance
        """
        if rma.status != RMA.STATUS_RECEIVED:
            raise ValueError(f"Cannot inspect RMA in {rma.status} status")
        
        for inspection in inspections:
            return_item = ReturnItem.objects.get(
                id=inspection['return_item_id'],
                rma=rma
            )
            
            return_item.condition = inspection.get('condition', return_item.condition)
            return_item.refund_amount = Decimal(str(inspection.get('refund_amount', return_item.refund_amount)))
            
            # Determine if approved based on condition
            if return_item.condition == ReturnItem.CONDITION_AS_NEW:
                return_item.status = ReturnItem.STATUS_APPROVED
            elif return_item.condition == ReturnItem.CONDITION_USED:
                return_item.status = ReturnItem.STATUS_APPROVED
            elif return_item.condition == ReturnItem.CONDITION_DAMAGED:
                # Partial refund for damaged items
                return_item.status = ReturnItem.STATUS_APPROVED
            else:
                # Defective - full refund
                return_item.status = ReturnItem.STATUS_APPROVED
            
            return_item.save(update_fields=["condition", "refund_amount", "status"])
        
        # Move RMA to inspected
        rma.status = RMA.STATUS_INSPECTED
        rma.save(update_fields=["status"])
        
        return rma
    
    @staticmethod
    @transaction.atomic
    def complete_rma(rma: RMA, refund_method: str = "original_payment") -> RMA:
        """
        Complete RMA: process refund and close out RMA.
        
        Args:
            rma: The RMA
            refund_method: 'original_payment', 'store_credit', 'exchange'
            
        Returns:
            Updated RMA instance
        """
        if rma.status != RMA.STATUS_INSPECTED:
            raise ValueError(f"Cannot complete RMA in {rma.status} status")
        
        # Calculate total refund
        total_refund = sum(
            item.refund_amount
            for item in rma.items.filter(status=ReturnItem.STATUS_APPROVED)
        )
        
        # Create refund transaction if method is original_payment
        if refund_method == "original_payment" and total_refund > 0:
            RefundsService.request_refund(
                order=rma.order,
                rma=rma,
                amount=total_refund,
                reason="RMA approved return",
            )
        
        rma.status = RMA.STATUS_COMPLETED
        rma.completed_at = timezone.now()
        rma.save(update_fields=["status", "completed_at"])
        
        return rma
    
    @staticmethod
    def get_rma_summary(rma: RMA) -> dict:
        """Get RMA summary details."""
        return_items = rma.items.all()
        total_items = sum(item.quantity_returned for item in return_items)
        total_refund = sum(item.refund_amount for item in return_items)
        
        return {
            "rma_number": rma.rma_number,
            "order_number": rma.order.order_number,
            "reason": rma.get_reason_display(),
            "status": rma.get_status_display(),
            "is_exchange": rma.is_exchange,
            "total_items": total_items,
            "total_refund_amount": float(total_refund),
            "created_at": str(rma.requested_at),
            "completed_at": str(rma.completed_at) if rma.completed_at else None,
        }


class RefundsService:
    """
    Manage refund processing with payment orchestrator.
    
    Workflow:
    1. request_refund() - Create refund request
    2. process_refund() - Submit to payment gateway
    3. complete_refund() - Mark as completed
    4. handle_refund_webhook() - Process gateway callback
    """
    
    @staticmethod
    def get_next_refund_id(tenant_id: int) -> str:
        """Generate unique refund ID."""
        return f"RF-{tenant_id:06d}-{uuid.uuid4().hex[:12].upper()}"
    
    @staticmethod
    @transaction.atomic
    def request_refund(
        order: Order,
        amount: Decimal,
        reason: str = "",
        rma: RMA | None = None,
    ) -> RefundTransaction:
        """
        Create refund request.
        
        Args:
            order: The Order to refund
            amount: Amount to refund
            reason: Reason for refund
            rma: Optional RMA associated with refund
            
        Returns:
            Created RefundTransaction instance
        """
        if amount <= 0:
            raise ValueError("Refund amount must be positive")

        # Lock order for accurate refund calculations
        locked_order = Order.objects.select_for_update().get(id=order.id)

        # Idempotency: if refund exists for same RMA and still active, return it
        if rma:
            existing = RefundTransaction.objects.filter(
                order=locked_order,
                rma=rma,
            ).exclude(status__in=[RefundTransaction.STATUS_FAILED, RefundTransaction.STATUS_CANCELLED]).first()
            if existing:
                return existing

        total_requested = (
            RefundTransaction.objects.filter(
                order=locked_order,
            )
            .exclude(status__in=[RefundTransaction.STATUS_FAILED, RefundTransaction.STATUS_CANCELLED])
            .aggregate(total=Sum("amount"))
            .get("total")
            or Decimal("0")
        )

        remaining = locked_order.total_amount - total_requested
        if amount > remaining:
            raise ValueError("Refund amount exceeds remaining refundable balance")

        refund_id = RefundsService.get_next_refund_id(order.tenant_id)

        refund = RefundTransaction.objects.create(
            tenant_id=order.tenant_id,
            store_id=order.store_id,
            order=locked_order,
            rma=rma,
            refund_id=refund_id,
            amount=amount,
            currency=order.currency,
            refund_reason=reason,
            status=RefundTransaction.STATUS_INITIATED,
        )

        return refund
    
    @staticmethod
    @transaction.atomic
    def process_refund(refund: RefundTransaction, gateway_client=None) -> RefundTransaction:
        """
        Process refund via payment gateway.
        
        Args:
            refund: The RefundTransaction to process
            gateway_client: Payment gateway client (from payment orchestrator)
            
        Returns:
            Updated RefundTransaction instance
        """
        if refund.status != RefundTransaction.STATUS_INITIATED:
            raise ValueError(f"Cannot process refund in {refund.status} status")
        
        # If gateway client provided, submit refund
        if gateway_client:
            try:
                # Call payment orchestrator
                response = gateway_client.request_refund(
                    order_id=refund.order_id,
                    amount=refund.amount,
                    reason=refund.refund_reason,
                    metadata={"refund_id": refund.refund_id, "rma": refund.rma_id},
                )
                refund.gateway_response = response.get('data', response)
                if response.get("status") == "success":
                    if response.get("completed"):
                        refund = RefundsService.complete_refund(refund)
                    else:
                        refund.status = RefundTransaction.STATUS_PROCESSING
                else:
                    refund.status = RefundTransaction.STATUS_FAILED
            except Exception as e:
                refund.gateway_response = {"error": str(e)}
                refund.status = RefundTransaction.STATUS_FAILED
        else:
            # Assume processing without gateway
            refund = RefundsService.complete_refund(refund)
        
        refund.save(update_fields=["status", "gateway_response"])
        return refund
    
    @staticmethod
    @transaction.atomic
    def complete_refund(refund: RefundTransaction) -> RefundTransaction:
        """
        Mark refund as completed.
        
        Args:
            refund: The RefundTransaction to complete
            
        Returns:
            Updated RefundTransaction instance
        """
        if refund.status == RefundTransaction.STATUS_COMPLETED:
            return refund
        
        from apps.wallet.services.wallet_service import WalletService
        from django.db.models import F

        refund.status = RefundTransaction.STATUS_COMPLETED
        refund.completed_at = timezone.now()
        refund.save(update_fields=["status", "completed_at"])

        # Atomically update order refunded_amount and wallet
        order = Order.objects.select_for_update().get(id=refund.order_id)
        Order.objects.filter(id=order.id).update(
            refunded_amount=F("refunded_amount") + refund.amount
        )
        order.refresh_from_db(fields=["refunded_amount"])
        if order.refunded_amount >= order.total_amount:
            order.status = "refunded"
        elif order.refunded_amount > 0:
            order.status = "partially_refunded"
        order.save(update_fields=["status"])
        WalletService.on_refund(
            store_id=order.store_id,
            tenant_id=order.tenant_id,
            amount=refund.amount,
            reference=f"refund:{refund.id}",
        )

        return refund
    
    @staticmethod
    @transaction.atomic
    def fail_refund(refund: RefundTransaction, error_msg: str = "") -> RefundTransaction:
        """
        Mark refund as failed.
        
        Args:
            refund: The RefundTransaction to fail
            error_msg: Error message
            
        Returns:
            Updated RefundTransaction instance
        """
        refund.status = RefundTransaction.STATUS_FAILED
        if error_msg:
            response = refund.gateway_response or {}
            response['error'] = error_msg
            refund.gateway_response = response
        
        refund.save(update_fields=["status", "gateway_response"])
        return refund
    
    @staticmethod
    def get_refund_summary(refund: RefundTransaction) -> dict:
        """Get refund summary for display."""
        return {
            "refund_id": refund.refund_id,
            "order_number": refund.order.order_number,
            "amount": float(refund.amount),
            "currency": refund.currency,
            "reason": refund.refund_reason,
            "status": refund.get_status_display(),
            "created_at": str(refund.created_at),
            "completed_at": str(refund.completed_at) if refund.completed_at else None,
        }
