from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.catalog.models import Inventory, Product
from apps.catalog.services.product_service import ProductService
from apps.catalog.services.variant_service import ProductConfigurationService
from apps.stores.models import Store
from apps.tenants.models import Tenant


class ProductVisibilityStateTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(username="vis-owner", password="pass12345")
        self.tenant = Tenant.objects.create(slug="vis-tenant", name="Vis Tenant", is_active=True)
        self.store = Store.objects.create(
            owner=self.owner,
            tenant=self.tenant,
            name="Vis Store",
            slug="vis-store",
            subdomain="vis-store",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )

    def test_hidden_visibility_kept_when_stock_available(self):
        product = ProductService.create_product(
            store_id=self.store.id,
            sku="VIS-1",
            name="Hidden Product",
            price=Decimal("10.00"),
            quantity=8,
            visibility=Product.VISIBILITY_HIDDEN,
        )
        product.refresh_from_db()
        self.assertEqual(product.visibility, Product.VISIBILITY_HIDDEN)
        self.assertFalse(product.is_active)

    def test_disabled_visibility_when_out_of_stock(self):
        product = ProductService.create_product(
            store_id=self.store.id,
            sku="VIS-2",
            name="Disabled Product",
            price=Decimal("12.00"),
            quantity=0,
            visibility=Product.VISIBILITY_ENABLED,
        )
        product.refresh_from_db()
        self.assertEqual(product.visibility, Product.VISIBILITY_DISABLED)
        self.assertFalse(product.is_active)

    def test_inventory_restock_promotes_disabled_to_enabled(self):
        product = Product.objects.create(
            store_id=self.store.id,
            sku="VIS-3",
            name="Restock Product",
            price=Decimal("15.00"),
            visibility=Product.VISIBILITY_DISABLED,
            is_active=False,
        )
        inventory = Inventory.objects.create(product=product, quantity=0, in_stock=False)

        inventory.quantity = 5
        inventory.save()
        product.refresh_from_db()

        self.assertEqual(product.visibility, Product.VISIBILITY_ENABLED)
        self.assertTrue(product.is_active)

    def test_upsert_accepts_hidden_visibility(self):
        product = ProductConfigurationService.upsert_product_with_variants(
            store=self.store,
            payload={
                "sku": "VIS-4",
                "name": "Upsert Hidden",
                "price": Decimal("18.00"),
                "quantity": 6,
                "visibility": Product.VISIBILITY_HIDDEN,
                "variants": [],
            },
        )
        product.refresh_from_db()
        self.assertEqual(product.visibility, Product.VISIBILITY_HIDDEN)
        self.assertFalse(product.is_active)
