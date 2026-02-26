from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.catalog.models import Inventory, Product
from apps.catalog.services.product_service import ProductService
from apps.catalog.services.variant_service import ProductConfigurationService
from apps.stores.models import Store
from apps.tenants.models import Tenant


class InventoryAutoStatusTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(username="inv-auto-owner", password="pass12345")
        self.tenant = Tenant.objects.create(slug="tenant-inv-auto", name="Tenant Inv Auto", is_active=True)
        self.store = Store.objects.create(
            owner=self.owner,
            tenant=self.tenant,
            name="Inv Auto Store",
            slug="inv-auto-store",
            subdomain="inv-auto-store",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )

    def test_create_product_with_zero_quantity_is_inactive(self):
        product = ProductService.create_product(
            store_id=self.store.id,
            sku="AUTO-0",
            name="Auto Zero",
            price=Decimal("10.00"),
            quantity=0,
            is_active=True,
        )
        product.refresh_from_db()
        inventory = Inventory.objects.get(product=product)

        self.assertFalse(product.is_active)
        self.assertEqual(inventory.quantity, 0)
        self.assertFalse(inventory.in_stock)

    def test_inventory_save_syncs_product_status(self):
        product = Product.objects.create(
            store_id=self.store.id,
            sku="AUTO-SYNC",
            name="Auto Sync",
            price=Decimal("15.00"),
            is_active=True,
        )
        inventory = Inventory.objects.create(product=product, quantity=3, in_stock=True)

        product.refresh_from_db()
        self.assertTrue(product.is_active)

        inventory.quantity = 0
        inventory.save()
        product.refresh_from_db()
        self.assertFalse(product.is_active)
        self.assertFalse(inventory.in_stock)

        inventory.quantity = 5
        inventory.save()
        product.refresh_from_db()
        self.assertTrue(product.is_active)
        self.assertTrue(inventory.in_stock)

    def test_product_configuration_upsert_uses_stock_for_status(self):
        product = ProductConfigurationService.upsert_product_with_variants(
            store=self.store,
            payload={
                "sku": "CFG-1",
                "name": "Cfg Product",
                "price": Decimal("20.00"),
                "quantity": 0,
                "is_active": True,
                "variants": [],
            },
        )
        product.refresh_from_db()
        self.assertFalse(product.is_active)

        updated = ProductConfigurationService.upsert_product_with_variants(
            store=self.store,
            payload={
                "sku": "CFG-1",
                "name": "Cfg Product",
                "price": Decimal("20.00"),
                "quantity": 7,
                "is_active": False,
                "variants": [],
            },
            product=product,
        )
        updated.refresh_from_db()
        self.assertTrue(updated.is_active)
