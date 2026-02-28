"""Tests for coupons app."""
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from apps.coupons.models import Coupon, CouponUsageLog
from apps.coupons.services import CouponValidationService, CouponAnalyticsService
from apps.stores.models import Store
from apps.tenants.models import Tenant


class CouponModelTest(TestCase):
    """Test Coupon model."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Test Tenant")
        self.store = Store.objects.create(
            tenant=self.tenant,
            name="Test Store",
            slug="test-store",
        )

    def test_coupon_creation(self):
        """Test creating a coupon."""
        coupon = Coupon.objects.create(
            store=self.store,
            code="SAVE20",
            discount_type=Coupon.DISCOUNT_PERCENTAGE,
            discount_value=Decimal("20.00"),
            end_date=timezone.now() + timedelta(days=30),
        )
        self.assertEqual(coupon.code, "SAVE20")
        self.assertEqual(coupon.discount_type, Coupon.DISCOUNT_PERCENTAGE)

    def test_coupon_percentage_discount(self):
        """Test percentage discount calculation."""
        coupon = Coupon.objects.create(
            store=self.store,
            code="20OFF",
            discount_type=Coupon.DISCOUNT_PERCENTAGE,
            discount_value=Decimal("20.00"),
            end_date=timezone.now() + timedelta(days=30),
        )
        discount = coupon.calculate_discount(Decimal("100.00"))
        self.assertEqual(discount, Decimal("20.00"))

    def test_coupon_fixed_discount(self):
        """Test fixed discount calculation."""
        coupon = Coupon.objects.create(
            store=self.store,
            code="50OFF",
            discount_type=Coupon.DISCOUNT_FIXED,
            discount_value=Decimal("50.00"),
            end_date=timezone.now() + timedelta(days=30),
        )
        discount = coupon.calculate_discount(Decimal("100.00"))
        self.assertEqual(discount, Decimal("50.00"))

    def test_coupon_max_discount_cap(self):
        """Test max discount cap for percentage coupons."""
        coupon = Coupon.objects.create(
            store=self.store,
            code="50PERCENT",
            discount_type=Coupon.DISCOUNT_PERCENTAGE,
            discount_value=Decimal("50.00"),
            max_discount_amount=Decimal("25.00"),
            end_date=timezone.now() + timedelta(days=30),
        )
        discount = coupon.calculate_discount(Decimal("100.00"))
        self.assertEqual(discount, Decimal("25.00"))  # Capped at max

    def test_coupon_expiry(self):
        """Test expired coupon."""
        coupon = Coupon.objects.create(
            store=self.store,
            code="EXPIRED",
            discount_type=Coupon.DISCOUNT_PERCENTAGE,
            discount_value=Decimal("10.00"),
            end_date=timezone.now() - timedelta(days=1),  # Expired
        )
        is_valid, error = CouponValidationService().validate_coupon(coupon)
        self.assertFalse(is_valid)
        self.assertIn("expired", error.lower())


class CouponValidationServiceTest(TestCase):
    """Test CouponValidationService."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Test Tenant")
        self.store = Store.objects.create(
            tenant=self.tenant,
            name="Test Store",
            slug="test-store",
        )
        self.service = CouponValidationService()

    def test_minimum_purchase_validation(self):
        """Test minimum purchase amount validation."""
        coupon = Coupon.objects.create(
            store=self.store,
            code="MIN100",
            discount_type=Coupon.DISCOUNT_FIXED,
            discount_value=Decimal("10.00"),
            minimum_purchase_amount=Decimal("100.00"),
            end_date=timezone.now() + timedelta(days=30),
        )
        is_valid, error = self.service.validate_coupon(
            coupon, subtotal=Decimal("50.00")
        )
        self.assertFalse(is_valid)
        self.assertIn("Minimum", error)

    def test_usage_limit(self):
        """Test global usage limit."""
        coupon = Coupon.objects.create(
            store=self.store,
            code="LIMITED",
            discount_type=Coupon.DISCOUNT_FIXED,
            discount_value=Decimal("10.00"),
            usage_limit=2,
            end_date=timezone.now() + timedelta(days=30),
        )
        # Simulate 2 uses
        coupon.times_used = 2
        coupon.save()

        is_valid, error = self.service.validate_coupon(coupon)
        self.assertFalse(is_valid)
        self.assertIn("usage limit", error.lower())
