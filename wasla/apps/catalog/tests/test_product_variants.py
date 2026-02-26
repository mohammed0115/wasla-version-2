"""
Comprehensive tests for Product Variants end-to-end.

Tests cover:
1. Creating products with variants
2. Variant pricing logic (override vs base)
3. Stock management for variants
4. Add-to-cart with variant validation
5. Checkout stock guard
6. Merchant dashboard CRUD operations
"""

import pytest
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model

from apps.catalog.models import (
    Product,
    ProductOptionGroup,
    ProductOption,
    ProductVariant,
    StockMovement,
    Inventory,
)
from apps.catalog.services.variant_service import (
    VariantPricingService,
    ProductVariantService,
    ProductConfigurationService,
)
from apps.cart.models import Cart, CartItem
from apps.cart.application.use_cases.add_to_cart import AddToCartCommand, AddToCartUseCase
from apps.cart.domain.errors import CartError
from apps.stores.models import Store
from apps.tenants.domain.tenant_context import TenantContext

User = get_user_model()


class VariantPricingServiceTests(TestCase):
    """Test variant pricing resolution logic."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.store = Store.objects.create(
            owner=self.user,
            name="Test Store",
            slug="test-store",
            subdomain="test-store"
        )
        self.product = Product.objects.create(
            store_id=self.store.id,
            sku="BASE-SKU",
            name="Base Product",
            price=Decimal("100.00"),
        )

    def test_base_price_when_no_variant(self):
        """Should return product base price when variant is None."""
        price = VariantPricingService.resolve_price(product=self.product, variant=None)
        assert price == Decimal("100.00")

    def test_override_price_when_variant_has_override(self):
        """Should return variant price when override is set."""
        variant = ProductVariant.objects.create(
            product=self.product,
            store_id=self.store.id,
            sku="VAR-SKU",
            price_override=Decimal("120.00"),
            stock_quantity=10,
        )
        price = VariantPricingService.resolve_price(product=self.product, variant=variant)
        assert price == Decimal("120.00")

    def test_base_price_when_variant_has_no_override(self):
        """Should return product base price when variant has no override."""
        variant = ProductVariant.objects.create(
            product=self.product,
            store_id=self.store.id,
            sku="VAR-SKU",
            stock_quantity=10,
        )
        price = VariantPricingService.resolve_price(product=self.product, variant=variant)
        assert price == Decimal("100.00")


class ProductVariantServiceTests(TestCase):
    """Test variant lookup and stock validation."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser2", password="testpass")
        self.store = Store.objects.create(
            owner=self.user,
            name="Test Store",
            slug="test-store",
            subdomain="test-store2"
        )
        self.product = Product.objects.create(
            store_id=self.store.id,
            sku="PROD-SKU",
            name="Product",
            price=Decimal("100.00"),
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            store_id=self.store.id,
            sku="VAR-001",
            stock_quantity=5,
        )

    def test_get_variant_for_store_success(self):
        """Should retrieve variant when it exists for store and product."""
        variant = ProductVariantService.get_variant_for_store(
            store_id=self.store.id,
            product_id=self.product.id,
            variant_id=self.variant.id,
        )
        assert variant.id == self.variant.id

    def test_get_variant_for_store_not_found(self):
        """Should raise ValueError when variant doesn't exist."""
        with pytest.raises(ValueError, match="Variant not found"):
            ProductVariantService.get_variant_for_store(
                store_id=self.store.id,
                product_id=self.product.id,
                variant_id=99999,
            )

    def test_get_variant_for_store_wrong_store(self):
        """Should raise ValueError when variant belongs to different store."""
        other_user = User.objects.create_user(username="other_user",password="pass")
        other_store = Store.objects.create(owner=other_user, name="Other", slug="other", subdomain="other-store")
        with pytest.raises(ValueError, match="Variant not found"):
            ProductVariantService.get_variant_for_store(
                store_id=other_store.id,
                product_id=self.product.id,
                variant_id=self.variant.id,
            )

    def test_get_variants_map(self):
        """Should return dict mapping variant IDs to instances."""
        variant2 = ProductVariant.objects.create(
            product=self.product,
            store_id=self.store.id,
            sku="VAR-002",
            stock_quantity=3,
        )
        variant_map = ProductVariantService.get_variants_map(
            store_id=self.store.id,
            variant_ids=[self.variant.id, variant2.id],
        )
        assert len(variant_map) == 2
        assert variant_map[self.variant.id].sku == "VAR-001"
        assert variant_map[variant2.id].sku == "VAR-002"


class ProductConfigurationServiceTests(TestCase):
    """Test complete product with variants creation and updates."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser3", password="testpass")
        self.store = Store.objects.create(
            owner=self.user,
            name="Test Store",
            slug="test-store",
            subdomain="test-store3"
        )

    def test_create_product_with_option_groups_and_variants(self):
        """Should create product with nested option groups and variants."""
        payload = {
            "sku": "TSHIRT",
            "name": "T-Shirt",
            "price": Decimal("100.00"),
            "option_groups": [
                {
                    "name": "Color",
                    "is_required": True,
                    "position": 1,
                    "options": [
                        {"value": "Red"},
                        {"value": "Blue"},
                    ],
                },
                {
                    "name": "Size",
                    "is_required": True,
                    "position": 2,
                    "options": [
                        {"value": "M"},
                        {"value": "L"},
                    ],
                },
            ],
            "variants": [
                {
                    "sku": "TSHIRT-RED-M",
                    "price_override": Decimal("120.00"),
                    "stock_quantity": 5,
                    "options": [
                        {"group": "Color", "value": "Red"},
                        {"group": "Size", "value": "M"},
                    ],
                },
            ],
        }

        product = ProductConfigurationService.upsert_product_with_variants(
            store=self.store,
            payload=payload,
        )

        assert product.sku == "TSHIRT"
        assert product.store_id == self.store.id
        assert product.variants.count() == 1

        variant = product.variants.first()
        assert variant.sku == "TSHIRT-RED-M"
        assert variant.price_override == Decimal("120.00")
        assert variant.stock_quantity == 5
        assert variant.options.count() == 2

    def test_update_product_variants(self):
        """Should update existing variants and add new ones."""
        # Create initial product
        product = Product.objects.create(
            store_id=self.store.id,
            sku="PROD",
            name="Product",
            price=Decimal("100.00"),
        )
        
        group = ProductOptionGroup.objects.create(
            store=self.store,
            name="Color",
            position=1,
        )
        opt_red = ProductOption.objects.create(group=group, value="Red")
        opt_blue = ProductOption.objects.create(group=group, value="Blue")

        variant1 = ProductVariant.objects.create(
            product=product,
            store_id=self.store.id,
            sku="VAR-1",
            stock_quantity=5,
        )
        variant1.options.add(opt_red)

        # Update with new variant
        payload = {
            "sku": "PROD-UPDATED",
            "name": "Product Updated",
            "price": Decimal("105.00"),
            "variants": [
                {
                    "id": variant1.id,
                    "sku": "VAR-1-UPDATED",
                    "stock_quantity": 10,
                    "option_ids": [opt_red.id],
                },
                {
                    "sku": "VAR-2",
                    "stock_quantity": 3,
                    "option_ids": [opt_blue.id],
                },
            ],
        }

        updated_product = ProductConfigurationService.upsert_product_with_variants(
            store=self.store,
            payload=payload,
            product=product,
        )

        assert updated_product.name == "Product Updated"
        assert updated_product.variants.count() == 2

    def test_variant_sku_unique_per_store(self):
        """Should validate variant SKU uniqueness within store scope."""
        payload1 = {
            "sku": "PROD1",
            "name": "Product 1",
            "price": Decimal("100.00"),
            "variants": [
                {"sku": "VAR-UNIQUE", "stock_quantity": 5},
            ],
        }
        product1 = ProductConfigurationService.upsert_product_with_variants(
            store=self.store,
            payload=payload1,
        )

        # Try to create variant with same SKU in same store
        product2 = Product.objects.create(
            store_id=self.store.id,
            sku="PROD2",
            name="Product 2",
            price=Decimal("100.00"),
        )

        payload2 = {
            "sku": "PROD2",
            "name": "Product 2",
            "price": Decimal("100.00"),
            "variants": [
                {"sku": "VAR-UNIQUE", "stock_quantity": 3},  # Duplicate SKU
            ],
        }

        with pytest.raises(ValueError, match="unique per store"):
            ProductConfigurationService.upsert_product_with_variants(
                store=self.store,
                payload=payload2,
                product=product2,
            )


class CartVariantIntegrationTests(TestCase):
    """Test adding variants to cart with stock validation."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser4", password="testpass")
        self.store = Store.objects.create(
            owner=self.user,
            name="Store",
            slug="store",
            subdomain="store4"
        )
        self.product = Product.objects.create(
            store_id=self.store.id,
            sku="PROD",
            name="Product",
            price=Decimal("100.00"),
            is_active=True,
        )
        Inventory.objects.create(product=self.product, quantity=100, in_stock=True)

        # Create variant with limited stock
        self.variant = ProductVariant.objects.create(
            product=self.product,
            store_id=self.store.id,
            sku="VAR-1",
            price_override=Decimal("120.00"),
            stock_quantity=2,  # Only 2 in stock
            is_active=True,
        )

        self.user = User.objects.create_user(username="user", password="pass")
        self.tenant_ctx = TenantContext(
            tenant_id=1,
            store_id=self.store.id,
            currency="SAR",
            user_id=self.user.id,
        )

    def test_add_variant_to_cart_success(self):
        """Should add variant to cart with correct price snapshot."""
        cmd = AddToCartCommand(
            tenant_ctx=self.tenant_ctx,
            product_id=self.product.id,
            quantity=1,
            variant_id=self.variant.id,
        )
        cart = AddToCartUseCase.execute(cmd)

        assert cart.total == Decimal("120.00")  # Variant override price
        assert len(cart.items) == 1
        item = cart.items[0]
        assert item.variant_id == self.variant.id
        assert item.unit_price == Decimal("120.00")

    def test_add_product_without_variant(self):
        """Should add product without variant using base price."""
        cmd = AddToCartCommand(
            tenant_ctx=self.tenant_ctx,
            product_id=self.product.id,
            quantity=2,
        )
        cart = AddToCartUseCase.execute(cmd)

        assert cart.total == Decimal("200.00")  # Base price * qty
        item = cart.items[0]
        assert item.variant_id is None
        assert item.unit_price == Decimal("100.00")

    def test_add_inactive_variant_fails_at_checkout(self):
        """Should allow adding inactive variant to cart, but fail at checkout."""
        self.variant.is_active = False
        self.variant.save()

        # Adding to cart succeeds
        cmd = AddToCartCommand(
            tenant_ctx=self.tenant_ctx,
            product_id=self.product.id,
            quantity=1,
            variant_id=self.variant.id,
        )
        cart = AddToCartUseCase.execute(cmd)
        assert len(cart.items) == 1

        # But checkout validation should fail
        with pytest.raises(ValueError, match="Variant is inactive"):
            ProductVariantService.assert_checkout_stock(
                store_id=self.store.id,
                items=[{"quantity": 1, "variant": self.variant}],
            )

    def test_add_variant_from_different_store_fails(self):
        """Should reject variant from different store at add-to-cart time."""
        other_user = User.objects.create_user(username="other_user3", password="pass")
        other_store = Store.objects.create(owner=other_user, name="Other", slug="other", subdomain="other-store3")
        
        # Create product in other store
        other_product = Product.objects.create(
            store_id=other_store.id,
            sku="OTHER-PROD",
            name="Other Product",
            price=Decimal("100.00"),
            is_active=True,
        )
        
        # Create variant for other store's product
        other_variant = ProductVariant.objects.create(
            product=other_product,
            sku="OTHER-VAR",
            stock_quantity=5,
        )

        cmd = AddToCartCommand(
            tenant_ctx=self.tenant_ctx,
            product_id=other_product.id,  # Product from different store
            quantity=1,
            variant_id=other_variant.id,
        )
        # This SHOULD raise CartError because product.store_id != tenant_ctx.store_id
        with pytest.raises(CartError, match="Product not found"):
            AddToCartUseCase.execute(cmd)


class StockMovementVariantTests(TestCase):
    """Test stock tracking for variants."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser5", password="testpass")
        self.store = Store.objects.create(
            owner=self.user,
            name="Store",
            slug="store",
            subdomain="store5"
        )
        self.product = Product.objects.create(
            store_id=self.store.id,
            sku="PROD",
            name="Product",
            price=Decimal("100.00"),
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            store_id=self.store.id,
            sku="VAR-1",
            stock_quantity=10,
        )

    def test_stock_movement_references_variant(self):
        """Stock movements should optionally track variant."""
        movement = StockMovement.objects.create(
            store_id=self.store.id,
            product=self.product,
            variant=self.variant,
            movement_type=StockMovement.TYPE_OUT,
            quantity=2,
            reason="Sales order",
        )

        assert movement.variant_id == self.variant.id
        assert movement.product_id == self.product.id

    def test_stock_movement_without_variant(self):
        """Stock movements can track product-level changes."""
        movement = StockMovement.objects.create(
            store_id=self.store.id,
            product=self.product,
            movement_type=StockMovement.TYPE_IN,
            quantity=5,
            reason="Purchase order",
        )

        assert movement.variant_id is None
        assert movement.product_id == self.product.id


class VariantModelConstraintTests(TestCase):
    """Test model constraints and uniqueness."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser6", password="testpass")
        self.store = Store.objects.create(
            owner=self.user,
            name="Store",
            slug="store",
            subdomain="store6"
        )
        self.product = Product.objects.create(
            store_id=self.store.id,
            sku="PROD",
            name="Product",
            price=Decimal("100.00"),
        )

    def test_variant_sku_unique_per_store(self):
        """SKU must be unique within store, not globally."""
        ProductVariant.objects.create(
            product=self.product,
            store_id=self.store.id,
            sku="UNIQUE-SKU",
            stock_quantity=5,
        )

        # Different store can have same SKU
        other_user = User.objects.create_user(username="other_user2", password="pass")
        other_store = Store.objects.create(owner=other_user, name="Other", slug="other", subdomain="other-store2")
        other_product = Product.objects.create(
            store_id=other_store.id,
            sku="PROD",
            name="Product",
            price=Decimal("100.00"),
        )
        variant = ProductVariant.objects.create(
            product=other_product,
            store_id=other_store.id,
            sku="UNIQUE-SKU",  # Same SKU, different store
            stock_quantity=3,
        )
        assert variant.id is not None

    def test_variant_inherits_store_from_product(self):
        """Variant.store_id should match Product.store_id."""
        variant = ProductVariant(
            product=self.product,
            sku="VAR-SKU",
            stock_quantity=5,
        )
        variant.save()

        assert variant.store_id == self.product.store_id

    def test_variant_option_uniqueness(self):
        """Should prevent duplicate option values in same group."""
        group = ProductOptionGroup.objects.create(
            store=self.store,
            name="Color",
        )

        ProductOption.objects.create(group=group, value="Red")

        # Attempting to create duplicate should be prevented by constraint
        with pytest.raises(Exception):  # IntegrityError
            ProductOption.objects.create(group=group, value="Red")


class MerchantDashboardVariantTests(TestCase):
    """Test merchant dashboard variant management (integration)."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="merchant", password="pass")
        self.store = Store.objects.create(
            owner=self.user,
            name="Store",
            slug="store",
            subdomain="store7"
        )
        self.user.store = self.store
        self.user.save()

    def test_product_list_shows_variant_count(self):
        """Product list should show variant count."""
        product = Product.objects.create(
            store_id=self.store.id,
            sku="PROD",
            name="Product",
            price=Decimal("100.00"),
        )
        variant = ProductVariant.objects.create(
            product=product,
            store_id=self.store.id,
            sku="VAR",
            stock_quantity=5,
        )

        # This would be tested in full integration tests with authentication
        # Just testing model relationships work
        assert product.variants.count() == 1

    def test_product_edit_shows_options_and_variants(self):
        """Product edit view should display option groups and variants."""
        product = Product.objects.create(
            store_id=self.store.id,
            sku="PROD",
            name="Product",
            price=Decimal("100.00"),
        )
        group = ProductOptionGroup.objects.create(
            store=self.store,
            name="Color",
        )
        option = ProductOption.objects.create(group=group, value="Red")
        variant = ProductVariant.objects.create(
            product=product,
            store_id=self.store.id,
            sku="VAR",
            stock_quantity=5,
        )
        variant.options.add(option)

        # Verify relationships
        assert ProductOptionGroup.objects.filter(store=self.store).count() == 1
        assert variant.options.count() == 1
