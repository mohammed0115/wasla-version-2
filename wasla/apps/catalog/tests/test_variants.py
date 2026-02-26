from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings

from apps.cart.models import Cart, CartItem
from apps.catalog.models import Inventory, Product, ProductOption, ProductOptionGroup, ProductVariant
from apps.checkout.application.use_cases.create_order_from_checkout import (
    CreateOrderFromCheckoutCommand,
    CreateOrderFromCheckoutUseCase,
)
from apps.checkout.domain.errors import InvalidCheckoutStateError
from apps.checkout.models import CheckoutSession
from apps.stores.models import Store
from apps.tenants.domain.tenant_context import TenantContext
from apps.tenants.models import Tenant


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", ".localhost"])
class CatalogVariantsAPITests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner-variants", password="pass12345")
        self.client.force_login(self.owner)
        self.tenant = Tenant.objects.create(slug="tenant-variants", name="Tenant Variants", is_active=True)
        self.store = Store.objects.create(
            owner=self.owner,
            tenant=self.tenant,
            name="Variants Store",
            slug="variants-store",
            subdomain="variants-store",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )

    def test_create_product_with_nested_variants_and_resolve_price(self):
        payload = {
            "sku": "TEE-BASE",
            "name": "T-Shirt",
            "price": "100.00",
            "quantity": 50,
            "option_groups": [
                {
                    "name": "Color",
                    "is_required": True,
                    "position": 1,
                    "options": [{"value": "Red"}, {"value": "Blue"}],
                },
                {
                    "name": "Size",
                    "is_required": True,
                    "position": 2,
                    "options": [{"value": "M"}, {"value": "L"}],
                },
            ],
            "variants": [
                {
                    "sku": "TEE-RED-M",
                    "price_override": "120.00",
                    "stock_quantity": 7,
                    "is_active": True,
                    "options": [{"group": "Color", "value": "Red"}, {"group": "Size", "value": "M"}],
                }
            ],
        }

        response = self.client.post(
            "/api/catalog/products/",
            data=payload,
            content_type="application/json",
            HTTP_HOST="variants-store.localhost",
        )
        self.assertEqual(response.status_code, 201)
        product_id = response.json()["id"]

        product = Product.objects.get(id=product_id)
        self.assertEqual(product.store_id, self.store.id)
        variant = ProductVariant.objects.get(product=product)
        self.assertEqual(variant.sku, "TEE-RED-M")
        self.assertEqual(variant.stock_quantity, 7)

        price_response = self.client.get(
            f"/api/catalog/products/{product.id}/price/?variant_id={variant.id}",
            HTTP_HOST="variants-store.localhost",
        )
        self.assertEqual(price_response.status_code, 200)
        self.assertEqual(price_response.json()["price"], "120.00")

        stock_response = self.client.get(
            f"/api/catalog/variants/{variant.id}/stock/",
            HTTP_HOST="variants-store.localhost",
        )
        self.assertEqual(stock_response.status_code, 200)
        self.assertEqual(stock_response.json()["stock_quantity"], 7)


class CheckoutVariantStockGuardTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        User = get_user_model()
        self.user = User.objects.create_user(username="buyer-variants", password="pass12345")
        self.tenant = Tenant.objects.create(slug="tenant-checkout-variants", name="Tenant Checkout", is_active=True)
        self.store = Store.objects.create(
            owner=self.user,
            tenant=self.tenant,
            name="Checkout Variant Store",
            slug="checkout-variant-store",
            subdomain="checkout-variant-store",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )

    def test_checkout_is_blocked_when_variant_stock_is_zero(self):
        product = Product.objects.create(
            store_id=self.store.id,
            sku="MUG-BASE",
            name="Mug",
            price=Decimal("80.00"),
            is_active=True,
        )
        Inventory.objects.create(product=product, quantity=20, in_stock=True)

        group = ProductOptionGroup.objects.create(store=self.store, name="Color", is_required=True, position=1)
        option = ProductOption.objects.create(group=group, value="Black")
        variant = ProductVariant.objects.create(
            store_id=self.store.id,
            product=product,
            sku="MUG-BLACK",
            price_override=Decimal("90.00"),
            stock_quantity=0,
            is_active=True,
        )
        variant.options.add(option)

        cart = Cart.objects.create(store_id=self.store.id, user=self.user, currency="SAR")
        CartItem.objects.create(
            cart=cart,
            product=product,
            variant=variant,
            quantity=1,
            unit_price_snapshot=Decimal("90.00"),
        )

        session = CheckoutSession.objects.create(
            store_id=self.store.id,
            cart=cart,
            status=CheckoutSession.STATUS_PAYMENT,
            shipping_address_json={
                "full_name": "Buyer",
                "email": "buyer@example.com",
                "phone": "0500000000",
                "line1": "Riyadh",
                "city": "Riyadh",
                "country": "SA",
            },
        )

        tenant_ctx = TenantContext(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            currency="SAR",
            user_id=self.user.id,
            session_key=None,
        )

        with self.assertRaisesMessage(InvalidCheckoutStateError, "Variant out of stock."):
            CreateOrderFromCheckoutUseCase.execute(
                CreateOrderFromCheckoutCommand(tenant_ctx=tenant_ctx, session_id=session.id)
            )


class VariantPricingServiceTests(TestCase):
    """Test price resolution logic with and without variants."""

    def setUp(self) -> None:
        super().setUp()
        User = get_user_model()
        self.user = User.objects.create_user(username="pricing-test", password="pass12345")
        self.tenant = Tenant.objects.create(slug="tenant-pricing", name="Pricing", is_active=True)
        self.store = Store.objects.create(
            owner=self.user,
            tenant=self.tenant,
            name="Pricing Store",
            slug="pricing-store",
            subdomain="pricing-store",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )
        self.product = Product.objects.create(
            store_id=self.store.id,
            sku="PROD-001",
            name="Test Product",
            price=Decimal("100.00"),
            is_active=True,
        )

    def test_price_resolution_without_variant_returns_base_price(self):
        from apps.catalog.services.variant_service import VariantPricingService

        price = VariantPricingService.resolve_price(product=self.product, variant=None)
        self.assertEqual(price, Decimal("100.00"))

    def test_price_resolution_with_variant_no_override_returns_base_price(self):
        from apps.catalog.services.variant_service import VariantPricingService

        variant = ProductVariant.objects.create(
            store_id=self.store.id,
            product=self.product,
            sku="PROD-001-VAR",
            price_override=None,
            stock_quantity=10,
            is_active=True,
        )

        price = VariantPricingService.resolve_price(product=self.product, variant=variant)
        self.assertEqual(price, Decimal("100.00"))

    def test_price_resolution_with_variant_override_returns_override_price(self):
        from apps.catalog.services.variant_service import VariantPricingService

        variant = ProductVariant.objects.create(
            store_id=self.store.id,
            product=self.product,
            sku="PROD-001-PREMIUM",
            price_override=Decimal("150.00"),
            stock_quantity=5,
            is_active=True,
        )

        price = VariantPricingService.resolve_price(product=self.product, variant=variant)
        self.assertEqual(price, Decimal("150.00"))

    def test_price_resolution_with_zero_override_returns_zero(self):
        from apps.catalog.services.variant_service import VariantPricingService

        variant = ProductVariant.objects.create(
            store_id=self.store.id,
            product=self.product,
            sku="PROD-001-FREE",
            price_override=Decimal("0.00"),
            stock_quantity=100,
            is_active=True,
        )

        price = VariantPricingService.resolve_price(product=self.product, variant=variant)
        self.assertEqual(price, Decimal("0.00"))


class VariantStockValidationTests(TestCase):
    """Test variant stock validation logic."""

    def setUp(self) -> None:
        super().setUp()
        User = get_user_model()
        self.user = User.objects.create_user(username="stock-test", password="pass12345")
        self.tenant = Tenant.objects.create(slug="tenant-stock", name="Stock", is_active=True)
        self.store = Store.objects.create(
            owner=self.user,
            tenant=self.tenant,
            name="Stock Store",
            slug="stock-store",
            subdomain="stock-store",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )
        self.product = Product.objects.create(
            store_id=self.store.id,
            sku="PROD-STOCK",
            name="Stock Product",
            price=Decimal("100.00"),
            is_active=True,
        )
        Inventory.objects.create(product=self.product, quantity=50, in_stock=True)

    def test_assert_checkout_stock_passes_with_sufficient_variant_stock(self):
        from apps.catalog.services.variant_service import ProductVariantService

        variant = ProductVariant.objects.create(
            store_id=self.store.id,
            product=self.product,
            sku="PROD-STOCK-VAR",
            stock_quantity=10,
            is_active=True,
        )

        items = [{"product": self.product, "variant": variant, "quantity": 5}]

        # Should not raise
        ProductVariantService.assert_checkout_stock(store_id=self.store.id, items=items)

    def test_assert_checkout_stock_fails_with_insufficient_variant_stock(self):
        from apps.catalog.services.variant_service import ProductVariantService

        variant = ProductVariant.objects.create(
            store_id=self.store.id,
            product=self.product,
            sku="PROD-STOCK-VAR",
            stock_quantity=3,
            is_active=True,
        )

        items = [{"product": self.product, "variant": variant, "quantity": 5}]

        with self.assertRaisesMessage(ValueError, "Variant out of stock."):
            ProductVariantService.assert_checkout_stock(store_id=self.store.id, items=items)

    def test_assert_checkout_stock_fails_with_inactive_variant(self):
        from apps.catalog.services.variant_service import ProductVariantService

        variant = ProductVariant.objects.create(
            store_id=self.store.id,
            product=self.product,
            sku="PROD-STOCK-INACTIVE",
            stock_quantity=100,
            is_active=False,
        )

        items = [{"product": self.product, "variant": variant, "quantity": 1}]

        with self.assertRaisesMessage(ValueError, "Variant is inactive."):
            ProductVariantService.assert_checkout_stock(store_id=self.store.id, items=items)

    def test_assert_checkout_stock_fails_with_store_mismatch(self):
        from apps.catalog.services.variant_service import ProductVariantService

        # Create variant with different store_id
        variant = ProductVariant.objects.create(
            store_id=999,
            product=self.product,
            sku="PROD-STOCK-OTHER",
            stock_quantity=10,
            is_active=True,
        )

        items = [{"product": self.product, "variant": variant, "quantity": 1}]

        with self.assertRaisesMessage(ValueError, "Variant store mismatch."):
            ProductVariantService.assert_checkout_stock(store_id=self.store.id, items=items)

    def test_assert_checkout_stock_fails_with_zero_quantity(self):
        from apps.catalog.services.variant_service import ProductVariantService

        variant = ProductVariant.objects.create(
            store_id=self.store.id,
            product=self.product,
            sku="PROD-STOCK-VAR",
            stock_quantity=10,
            is_active=True,
        )

        items = [{"product": self.product, "variant": variant, "quantity": 0}]

        with self.assertRaisesMessage(ValueError, "Quantity must be at least 1."):
            ProductVariantService.assert_checkout_stock(store_id=self.store.id, items=items)

    def test_assert_checkout_stock_passes_for_non_variant_product(self):
        from apps.catalog.services.variant_service import ProductVariantService

        items = [{"product": self.product, "variant": None, "quantity": 10}]

        # Should not raise (uses Inventory)
        ProductVariantService.assert_checkout_stock(store_id=self.store.id, items=items)

    def test_assert_checkout_stock_fails_for_non_variant_insufficient_inventory(self):
        from apps.catalog.services.variant_service import ProductVariantService

        items = [{"product": self.product, "variant": None, "quantity": 100}]

        with self.assertRaisesMessage(ValueError, "Insufficient stock"):
            ProductVariantService.assert_checkout_stock(store_id=self.store.id, items=items)


class VariantConstraintsTests(TestCase):
    """Test database constraints and uniqueness."""

    def setUp(self) -> None:
        super().setUp()
        User = get_user_model()
        self.user = User.objects.create_user(username="constraints-test", password="pass12345")
        self.tenant = Tenant.objects.create(slug="tenant-constraints", name="Constraints", is_active=True)
        self.store = Store.objects.create(
            owner=self.user,
            tenant=self.tenant,
            name="Constraints Store",
            slug="constraints-store",
            subdomain="constraints-store",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )
        self.product = Product.objects.create(
            store_id=self.store.id,
            sku="PROD-CONSTRAINT",
            name="Constraint Product",
            price=Decimal("100.00"),
            is_active=True,
        )

    def test_variant_sku_unique_per_store(self):
        from django.db import IntegrityError

        ProductVariant.objects.create(
            store_id=self.store.id,
            product=self.product,
            sku="UNIQUE-SKU",
            stock_quantity=10,
            is_active=True,
        )

        # Duplicate SKU in same store should fail
        with self.assertRaises(IntegrityError):
            ProductVariant.objects.create(
                store_id=self.store.id,
                product=self.product,
                sku="UNIQUE-SKU",
                stock_quantity=5,
                is_active=True,
            )

    def test_variant_sku_can_be_same_in_different_stores(self):
        # Create second store
        store2 = Store.objects.create(
            owner=self.user,
            tenant=self.tenant,
            name="Store 2",
            slug="store-2",
            subdomain="store-2",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )
        product2 = Product.objects.create(
            store_id=store2.id,
            sku="PROD-2",
            name="Product 2",
            price=Decimal("100.00"),
            is_active=True,
        )

        # Same SKU in different stores should succeed
        ProductVariant.objects.create(
            store_id=self.store.id,
            product=self.product,
            sku="SHARED-SKU",
            stock_quantity=10,
            is_active=True,
        )

        variant2 = ProductVariant.objects.create(
            store_id=store2.id,
            product=product2,
            sku="SHARED-SKU",
            stock_quantity=5,
            is_active=True,
        )

        self.assertEqual(variant2.sku, "SHARED-SKU")

    def test_variant_store_id_auto_syncs_from_product(self):
        variant = ProductVariant.objects.create(
            product=self.product,
            sku="AUTO-SYNC-SKU",
            stock_quantity=10,
            is_active=True,
        )

        self.assertEqual(variant.store_id, self.product.store_id)

    def test_option_group_name_unique_per_store(self):
        from django.db import IntegrityError

        ProductOptionGroup.objects.create(store=self.store, name="Color", is_required=True, position=1)

        # Duplicate name in same store should fail
        with self.assertRaises(IntegrityError):
            ProductOptionGroup.objects.create(store=self.store, name="Color", is_required=False, position=2)

    def test_option_value_unique_per_group(self):
        from django.db import IntegrityError

        group = ProductOptionGroup.objects.create(store=self.store, name="Size", is_required=True, position=1)
        ProductOption.objects.create(group=group, value="M")

        # Duplicate value in same group should fail
        with self.assertRaises(IntegrityError):
            ProductOption.objects.create(group=group, value="M")


class VariantServiceTests(TestCase):
    """Test variant service helper methods."""

    def setUp(self) -> None:
        super().setUp()
        User = get_user_model()
        self.user = User.objects.create_user(username="service-test", password="pass12345")
        self.tenant = Tenant.objects.create(slug="tenant-service", name="Service", is_active=True)
        self.store = Store.objects.create(
            owner=self.user,
            tenant=self.tenant,
            name="Service Store",
            slug="service-store",
            subdomain="service-store",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )
        self.product = Product.objects.create(
            store_id=self.store.id,
            sku="PROD-SERVICE",
            name="Service Product",
            price=Decimal("100.00"),
            is_active=True,
        )

    def test_get_variant_for_store_success(self):
        from apps.catalog.services.variant_service import ProductVariantService

        variant = ProductVariant.objects.create(
            store_id=self.store.id,
            product=self.product,
            sku="VAR-001",
            stock_quantity=10,
            is_active=True,
        )

        result = ProductVariantService.get_variant_for_store(
            store_id=self.store.id, product_id=self.product.id, variant_id=variant.id
        )

        self.assertEqual(result.id, variant.id)

    def test_get_variant_for_store_wrong_store_fails(self):
        from apps.catalog.services.variant_service import ProductVariantService

        variant = ProductVariant.objects.create(
            store_id=self.store.id,
            product=self.product,
            sku="VAR-002",
            stock_quantity=10,
            is_active=True,
        )

        with self.assertRaisesMessage(ValueError, "Variant not found."):
            ProductVariantService.get_variant_for_store(store_id=999, product_id=self.product.id, variant_id=variant.id)

    def test_get_variants_map_returns_dict(self):
        from apps.catalog.services.variant_service import ProductVariantService

        variant1 = ProductVariant.objects.create(
            store_id=self.store.id, product=self.product, sku="VAR-MAP-1", stock_quantity=10, is_active=True
        )
        variant2 = ProductVariant.objects.create(
            store_id=self.store.id, product=self.product, sku="VAR-MAP-2", stock_quantity=5, is_active=True
        )

        variant_map = ProductVariantService.get_variants_map(
            store_id=self.store.id, variant_ids=[variant1.id, variant2.id]
        )

        self.assertEqual(len(variant_map), 2)
        self.assertEqual(variant_map[variant1.id].sku, "VAR-MAP-1")
        self.assertEqual(variant_map[variant2.id].sku, "VAR-MAP-2")

    def test_get_variants_map_empty_list_returns_empty_dict(self):
        from apps.catalog.services.variant_service import ProductVariantService

        variant_map = ProductVariantService.get_variants_map(store_id=self.store.id, variant_ids=[])
        self.assertEqual(variant_map, {})
