"""
Phase C Launch Blockers Integration Tests.

Tests all 5 commerce features blocking production launch:
1. Shipping Zones - Zone matching and rate calculation
2. Promotions Engine - Coupon validation and discount application
3. BNPL Integration - Payment initiation and webhook handling
4. Subscription Limits - Plan enforcement (products, staff, orders)
5. Notification Idempotency - Duplicate email prevention
"""

import pytest
import hashlib
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.db import transaction

from apps.shipping.services.shipping_zone_service import (
    ShippingZoneService,
    ShippingZoneMatchError,
)
from apps.coupons.services.coupon_service import (
    CouponService,
    PromotionService,
    CouponValidationError,
)
from apps.bnpl.services.bnpl_service import (
    BnplService,
    BnplWebhookError,
    BnplIntegrationError,
)
from apps.subscriptions.services.subscription_limit_service import (
    SubscriptionLimitService,
    SubscriptionLimitExceededError,
)
from apps.notifications.services.order_notification_service import (
    OrderNotificationService,
    OrderNotificationModel,
)

# Mock models for testing
from apps.orders.models import Order
from apps.shipping.models import ShippingZone, ShippingRate
from apps.coupons.models import Coupon
from apps.bnpl.models import BnplProvider, BnplTransaction
from apps.subscriptions.models import StoreSubscription, SubscriptionPlan


@pytest.mark.django_db
class TestShippingZonesBlocker:
    """Test Blocker 1: Shipping Zones"""
    
    def setup_method(self):
        self.service = ShippingZoneService()
    
    def test_find_zone_for_country_returns_matching_zone(self):
        """Test zone matching for valid country."""
        # Create test data
        zone = ShippingZone.objects.create(
            name="Gulf Region",
            countries="SA,AE,KW",
            priority=1,
            is_active=True,
        )
        
        result = self.service.find_zone_for_country("SA")
        assert result is not None
        assert result["zone_id"] == zone.id
        assert result["zone_name"] == "Gulf Region"
    
    def test_find_zone_for_country_raises_error_for_unsupported(self):
        """Test error handling for unsupported country."""
        with pytest.raises(ShippingZoneMatchError):
            self.service.find_zone_for_country("INVALID")
    
    def test_calculate_shipping_cost_includes_weight(self):
        """Test shipping cost calculation includes weight."""
        zone = ShippingZone.objects.create(
            name="Test Zone",
            countries="SA",
            priority=1,
            is_active=True,
        )
        rate = ShippingRate.objects.create(
            zone=zone,
            min_weight=0,
            max_weight=10,
            base_cost=50.00,
            per_kg_cost=5.00,
        )
        
        cost = self.service.calculate_shipping_cost(
            zone_id=zone.id,
            order_total=500.00,
            weight_kg=2.5,
        )
        
        # Base 50 + (2.5 * 5) = 62.50
        assert cost["total_cost"] == Decimal("62.50")
        assert cost["base_cost"] == Decimal("50.00")
        assert cost["weight_cost"] == Decimal("12.50")
    
    def test_free_shipping_applied_at_threshold(self):
        """Test free shipping for orders above threshold."""
        zone = ShippingZone.objects.create(
            name="Test Zone",
            countries="SA",
            priority=1,
            is_active=True,
            free_shipping_threshold=500.00,
        )
        
        is_free = self.service.calculate_shipping_cost(
            zone_id=zone.id,
            order_total=600.00,
            weight_kg=1.0,
        )["is_free"]
        
        assert is_free is True
    
    def test_validate_shipping_for_checkout_blocks_without_zone(self):
        """Test checkout validation blocks if no shipping zone available."""
        with pytest.raises(ShippingZoneMatchError):
            self.service.validate_shipping_for_checkout(
                customer_country="INVALID",
                order_total=500.00,
            )
    
    def test_priority_determines_zone_selection(self):
        """Test priority-based zone selection."""
        # Create overlapping zones with different priorities
        zone_low = ShippingZone.objects.create(
            name="Low Priority Zone",
            countries="SA,AE",
            priority=10,
            is_active=True,
        )
        zone_high = ShippingZone.objects.create(
            name="High Priority Zone",
            countries="SA",
            priority=1,
            is_active=True,
        )
        
        result = self.service.find_zone_for_country("SA")
        assert result["zone_id"] == zone_high.id  # Higher priority (lower number)


@pytest.mark.django_db
class TestPromotionsEngineBlocker:
    """Test Blocker 2: Promotions Engine"""
    
    def setup_method(self):
        self.coupon_service = CouponService()
        self.promo_service = PromotionService()
    
    def test_valid_coupon_validation_succeeds(self):
        """Test validation of active, non-expired coupon."""
        coupon = Coupon.objects.create(
            code="SUMMER50",
            discount_value=Decimal("50.00"),
            discount_type="fixed",
            start_date=timezone.now() - timedelta(days=1),
            end_date=timezone.now() + timedelta(days=30),
            usage_limit=100,
            is_active=True,
        )
        
        result = self.coupon_service.validate_coupon_code("SUMMER50")
        assert result["valid"] is True
        assert result["coupon_id"] == coupon.id
    
    def test_expired_coupon_validation_fails(self):
        """Test validation fails for expired coupon."""
        Coupon.objects.create(
            code="EXPIRED",
            discount_value=Decimal("50.00"),
            discount_type="fixed",
            start_date=timezone.now() - timedelta(days=30),
            end_date=timezone.now() - timedelta(days=1),
            is_active=True,
        )
        
        with pytest.raises(CouponValidationError) as exc_info:
            self.coupon_service.validate_coupon_code("EXPIRED")
        assert "expired" in str(exc_info.value).lower()
    
    def test_usage_limit_enforced(self):
        """Test coupon with reached usage limit is rejected."""
        coupon = Coupon.objects.create(
            code="LIMITED",
            discount_value=Decimal("50.00"),
            discount_type="fixed",
            usage_limit=1,
            usage_count=1,  # Already used
            is_active=True,
        )
        
        with pytest.raises(CouponValidationError) as exc_info:
            self.coupon_service.validate_coupon_code("LIMITED")
        assert "usage limit" in str(exc_info.value).lower()
    
    def test_minimum_purchase_validation(self):
        """Test coupon with minimum purchase requirement."""
        coupon = Coupon.objects.create(
            code="MIN100",
            discount_value=Decimal("50.00"),
            discount_type="fixed",
            minimum_purchase=Decimal("100.00"),
            is_active=True,
        )
        
        result = self.coupon_service.validate_coupon_code(
            "MIN100",
            order_total=Decimal("50.00"),
        )
        
        assert result["valid"] is False
        assert "minimum purchase" in result["error"].lower()
    
    def test_fixed_discount_calculation(self):
        """Test fixed amount discount calculation."""
        coupon = Coupon.objects.create(
            code="FIXED50",
            discount_value=Decimal("50.00"),
            discount_type="fixed",
            is_active=True,
        )
        
        discount = self.coupon_service.apply_coupon(
            coupon_id=coupon.id,
            order_total=Decimal("500.00"),
        )
        
        assert discount["discount_amount"] == Decimal("50.00")
        assert discount["final_total"] == Decimal("450.00")
    
    def test_percentage_discount_calculation(self):
        """Test percentage discount calculation."""
        coupon = Coupon.objects.create(
            code="PERCENT10",
            discount_value=Decimal("10.00"),  # 10%
            discount_type="percentage",
            is_active=True,
        )
        
        discount = self.coupon_service.apply_coupon(
            coupon_id=coupon.id,
            order_total=Decimal("500.00"),
        )
        
        assert discount["discount_amount"] == Decimal("50.00")  # 10% of 500
        assert discount["final_total"] == Decimal("450.00")
    
    def test_percentage_discount_capped(self):
        """Test percentage discount is capped at max_discount."""
        coupon = Coupon.objects.create(
            code="PERCENT50CAP",
            discount_value=Decimal("50.00"),  # 50%
            discount_type="percentage",
            max_discount=Decimal("100.00"),  # Cap at 100
            is_active=True,
        )
        
        discount = self.coupon_service.apply_coupon(
            coupon_id=coupon.id,
            order_total=Decimal("500.00"),
        )
        
        # Would be 250, but capped at 100
        assert discount["discount_amount"] == Decimal("100.00")
    
    def test_coupon_usage_recorded(self):
        """Test coupon usage is incremented after order."""
        coupon = Coupon.objects.create(
            code="TRACK",
            discount_value=Decimal("50.00"),
            usage_count=0,
            is_active=True,
        )
        
        self.coupon_service.record_coupon_usage(coupon_id=coupon.id)
        
        coupon.refresh_from_db()
        assert coupon.usage_count == 1
    
    def test_promotion_service_wraps_coupon_service(self):
        """Test PromotionService delegates to CouponService."""
        coupon = Coupon.objects.create(
            code="PROMO",
            discount_value=Decimal("50.00"),
            is_active=True,
        )
        
        result = self.promo_service.validate_coupon_code("PROMO")
        assert result["valid"] is True


@pytest.mark.django_db
class TestBnplIntegrationBlocker:
    """Test Blocker 3: BNPL Integration"""
    
    def setup_method(self):
        self.service = BnplService()
    
    def test_bnpl_payment_initiation_creates_transaction(self):
        """Test BNPL payment initiation creates transaction record."""
        provider = BnplProvider.objects.create(
            name="Tabby",
            api_key="test_key",
            webhook_secret="test_secret",
            is_active=True,
        )
        order = Order.objects.create(
            order_number="ORD123",
            total_price=Decimal("500.00"),
        )
        
        result = self.service.initiate_payment(
            order_id=order.id,
            provider_id=provider.id,
            customer_email="test@example.com",
        )
        
        assert result["success"] is True
        assert "transaction_id" in result
        assert "payment_url" in result
        
        transaction = BnplTransaction.objects.get(id=result["transaction_id"])
        assert transaction.order_id == order.id
        assert transaction.provider_id == provider.id
    
    def test_webhook_signature_verification(self):
        """Test webhook signature verification prevents tampering."""
        provider = BnplProvider.objects.create(
            name="Tabby",
            webhook_secret="secret123",
            is_active=True,
        )
        
        payload = {"order_id": "123", "status": "approved"}
        
        # Generate correct signature
        import hmac
        correct_sig = hmac.new(
            b"secret123",
            str(payload).encode(),
            "sha256",
        ).hexdigest()
        
        # Verify correct signature passes
        is_valid = self.service._verify_webhook_signature(
            payload=payload,
            webhook_secret="secret123",
            provided_signature=correct_sig,
        )
        assert is_valid is True
        
        # Invalid signature fails
        is_valid = self.service._verify_webhook_signature(
            payload=payload,
            webhook_secret="secret123",
            provided_signature="invalid",
        )
        assert is_valid is False
    
    def test_webhook_updates_order_status_on_approval(self):
        """Test webhook updates order status when BNPL approved."""
        provider = BnplProvider.objects.create(
            name="Tabby",
            webhook_secret="secret",
            is_active=True,
        )
        order = Order.objects.create(
            order_number="ORD456",
            total_price=Decimal("500.00"),
            payment_status="pending",
        )
        transaction = BnplTransaction.objects.create(
            order=order,
            provider=provider,
            amount=Decimal("500.00"),
            provider_reference="ref123",
            status="initiated",
        )
        
        webhook_data = {
            "order_id": order.id,
            "transaction_id": transaction.id,
            "status": "approved",
        }
        
        result = self.service.handle_webhook(webhook_data=webhook_data)
        
        assert result["success"] is True
        
        transaction.refresh_from_db()
        order.refresh_from_db()
        assert transaction.status == "approved"
        assert order.payment_status == "paid"
    
    def test_webhook_rejects_invalid_transaction_id(self):
        """Test webhook rejects non-existent transaction."""
        webhook_data = {
            "transaction_id": 99999,  # Non-existent
            "status": "approved",
        }
        
        with pytest.raises(BnplWebhookError) as exc_info:
            self.service.handle_webhook(webhook_data=webhook_data)
        assert "transaction not found" in str(exc_info.value).lower()
    
    def test_get_transaction_status(self):
        """Test retrieving BNPL transaction status."""
        provider = BnplProvider.objects.create(
            name="Tabby",
            is_active=True,
        )
        order = Order.objects.create(order_number="ORD789")
        transaction = BnplTransaction.objects.create(
            order=order,
            provider=provider,
            status="approved",
        )
        
        status = self.service.get_transaction_status(transaction_id=transaction.id)
        
        assert status["status"] == "approved"
        assert status["order_id"] == order.id


@pytest.mark.django_db
class TestSubscriptionLimitsBlocker:
    """Test Blocker 4: Subscription Limits"""
    
    def setup_method(self):
        self.service = SubscriptionLimitService()
    
    def test_product_limit_enforced(self):
        """Test subscription product limit is enforced."""
        plan = SubscriptionPlan.objects.create(
            name="Basic",
            max_products=5,
        )
        subscription = StoreSubscription.objects.create(
            plan=plan,
        )
        
        result = self.service.check_product_limit(
            subscription_id=subscription.id,
            current_product_count=5,
        )
        
        # At limit - next product would exceed
        assert result["allowed"] is False
        assert result["limit"] == 5
    
    def test_product_limit_allows_under_limit(self):
        """Test product creation allowed under limit."""
        plan = SubscriptionPlan.objects.create(
            name="Basic",
            max_products=10,
        )
        subscription = StoreSubscription.objects.create(
            plan=plan,
        )
        
        result = self.service.check_product_limit(
            subscription_id=subscription.id,
            current_product_count=5,
        )
        
        assert result["allowed"] is True
        assert result["current"] == 5
        assert result["limit"] == 10
    
    def test_staff_user_limit_enforced(self):
        """Test subscription staff user limit is enforced."""
        plan = SubscriptionPlan.objects.create(
            name="Basic",
            max_staff_users=3,
        )
        subscription = StoreSubscription.objects.create(
            plan=plan,
        )
        
        result = self.service.check_staff_user_limit(
            subscription_id=subscription.id,
            current_staff_count=3,
        )
        
        assert result["allowed"] is False
    
    def test_monthly_orders_limit_enforced(self):
        """Test subscription monthly orders limit is enforced."""
        plan = SubscriptionPlan.objects.create(
            name="Basic",
            max_orders_monthly=1000,
        )
        subscription = StoreSubscription.objects.create(
            plan=plan,
        )
        
        result = self.service.check_monthly_orders_limit(
            subscription_id=subscription.id,
            current_month_order_count=1000,
        )
        
        assert result["allowed"] is False
        assert result["limit"] == 1000
    
    def test_limit_exceeded_error_raised_with_context(self):
        """Test SubscriptionLimitExceededError includes friendly message."""
        plan = SubscriptionPlan.objects.create(
            name="Basic",
            max_products=5,
        )
        subscription = StoreSubscription.objects.create(
            plan=plan,
        )
        
        with pytest.raises(SubscriptionLimitExceededError) as exc_info:
            result = self.service.check_product_limit(
                subscription_id=subscription.id,
                current_product_count=5,
            )
            if not result["allowed"]:
                raise SubscriptionLimitExceededError(result["message"])
        
        assert "product" in str(exc_info.value).lower()
    
    def test_subscription_summary_returns_all_limits(self):
        """Test get_subscription_summary returns current usage + limits."""
        plan = SubscriptionPlan.objects.create(
            name="Premium",
            max_products=100,
            max_staff_users=50,
            max_orders_monthly=5000,
        )
        subscription = StoreSubscription.objects.create(
            plan=plan,
        )
        
        summary = self.service.get_subscription_summary(subscription_id=subscription.id)
        
        assert summary["plan_name"] == "Premium"
        assert summary["products"]["limit"] == 100
        assert summary["staff_users"]["limit"] == 50
        assert summary["orders_monthly"]["limit"] == 5000


@pytest.mark.django_db
class TestNotificationIdempotencyBlocker:
    """Test Blocker 5: Order Notification Idempotency"""
    
    def setup_method(self):
        self.service = OrderNotificationService()
    
    def test_notification_sent_once_on_first_call(self):
        """Test notification sent successfully on first attempt."""
        order = Order.objects.create(
            order_number="ORD999",
        )
        
        result = self.service.send_notification(
            order=order,
            event_type="order_confirmed",
            channel="email",
            recipient="customer@example.com",
            subject="Order Confirmed",
            message="Your order has been confirmed.",
        )
        
        assert result["success"] is True
        assert result["idempotent_reuse"] is False
        assert result["notification_id"] is not None
        
        notification = OrderNotificationModel.objects.get(id=result["notification_id"])
        assert notification.status == "sent"
        assert notification.sent_at is not None
    
    def test_same_event_not_sent_twice(self):
        """Test idempotency prevents duplicate sends."""
        order = Order.objects.create(order_number="ORD1000")
        
        # First send
        result1 = self.service.send_notification(
            order=order,
            event_type="order_confirmed",
            channel="email",
            recipient="customer@example.com",
            subject="Order Confirmed",
            message="Your order has been confirmed.",
        )
        
        # Second attempt (idempotent reuse)
        result2 = self.service.send_notification(
            order=order,
            event_type="order_confirmed",
            channel="email",
            recipient="customer@example.com",
            subject="Order Confirmed",
            message="Your order has been confirmed.",
        )
        
        assert result1["notification_id"] == result2["notification_id"]
        assert result2["idempotent_reuse"] is True
        
        # Only 1 notification record created
        count = OrderNotificationModel.objects.filter(order=order).count()
        assert count == 1
    
    def test_different_events_create_separate_notifications(self):
        """Test different event types create separate notifications."""
        order = Order.objects.create(order_number="ORD1001")
        
        result1 = self.service.send_notification(
            order=order,
            event_type="order_confirmed",
            channel="email",
            recipient="customer@example.com",
            subject="Order Confirmed",
            message="Your order has been confirmed.",
        )
        
        result2 = self.service.send_notification(
            order=order,
            event_type="order_shipped",
            channel="email",
            recipient="customer@example.com",
            subject="Order Shipped",
            message="Your order has shipped.",
        )
        
        assert result1["notification_id"] != result2["notification_id"]
        assert result1["idempotent_reuse"] is False
        assert result2["idempotent_reuse"] is False
        
        count = OrderNotificationModel.objects.filter(order=order).count()
        assert count == 2
    
    def test_retry_with_existing_pending_notification(self):
        """Test retry of pending notification without creating duplicate."""
        order = Order.objects.create(order_number="ORD1002")
        
        # Create pending notification
        notification = OrderNotificationModel.objects.create(
            order=order,
            event_type="order_confirmed",
            channel="email",
            idempotency_key=hashlib.sha256(
                f"{order.id}:order_confirmed:email".encode()
            ).hexdigest(),
            recipient="customer@example.com",
            status="pending",
        )
        
        # Retry send (should attempt and update status)
        result = self.service.send_notification(
            order=order,
            event_type="order_confirmed",
            channel="email",
            recipient="customer@example.com",
            subject="Order Confirmed",
            message="Your order has been confirmed.",
        )
        
        assert result["success"] is True
        assert result["notification_id"] == notification.id
        
        notification.refresh_from_db()
        assert notification.status == "sent"
        assert notification.retry_count == 1
    
    def test_notification_history_retrieval(self):
        """Test getting notification history for order."""
        order = Order.objects.create(order_number="ORD1003")
        
        # Send multiple notifications
        self.service.send_notification(
            order=order,
            event_type="order_confirmed",
            channel="email",
            recipient="customer@example.com",
            subject="Confirmed",
            message="Message",
        )
        
        self.service.send_notification(
            order=order,
            event_type="order_shipped",
            channel="email",
            recipient="customer@example.com",
            subject="Shipped",
            message="Message",
        )
        
        history = self.service.get_notification_history(order_id=order.id)
        
        assert len(history) == 2
        assert history[0]["status"] == "sent"
        assert history[1]["status"] == "sent"
    
    @patch("apps.notifications.services.order_notification_service.OrderNotificationService._send_email")
    def test_failed_notification_marked_as_failed(self, mock_send_email):
        """Test failed notification is marked as failed."""
        mock_send_email.return_value = False
        
        order = Order.objects.create(order_number="ORD1004")
        
        result = self.service.send_notification(
            order=order,
            event_type="order_confirmed",
            channel="email",
            recipient="customer@example.com",
            subject="Order Confirmed",
            message="Your order has been confirmed.",
        )
        
        assert result["success"] is False
        
        notification = OrderNotificationModel.objects.get(id=result["notification_id"])
        assert notification.status == "failed"
    
    def test_idempotency_key_includes_channel(self):
        """Test different channels create different idempotency keys."""
        order = Order.objects.create(order_number="ORD1005")
        
        result_email = self.service.send_notification(
            order=order,
            event_type="order_confirmed",
            channel="email",
            recipient="customer@example.com",
            subject="Confirmed",
            message="Message",
        )
        
        result_sms = self.service.send_notification(
            order=order,
            event_type="order_confirmed",
            channel="sms",
            recipient="+966501234567",
            subject="Confirmed",
            message="Message",
        )
        
        # Different notification IDs (different channels)
        assert result_email["notification_id"] != result_sms["notification_id"]
        
        count = OrderNotificationModel.objects.filter(order=order).count()
        assert count == 2
