from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.catalog.models import Category
from apps.catalog.services.product_service import ProductService
from apps.catalog.services.variant_service import ProductConfigurationService
from apps.stores.models import Store
from apps.tenants.models import Tenant


class ProductCategoryRequirementTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(username="cat-owner", password="pass12345")
        self.tenant = Tenant.objects.create(slug="cat-tenant", name="Cat Tenant", is_active=True)
        self.store = Store.objects.create(
            owner=self.owner,
            tenant=self.tenant,
            name="Cat Store",
            slug="cat-store",
            subdomain="cat-store",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )

    def test_create_product_without_categories_assigns_default(self):
        product = ProductService.create_product(
            store_id=self.store.id,
            sku="CAT-001",
            name="Category Product",
            price=Decimal("12.00"),
            quantity=4,
        )

        self.assertEqual(product.categories.count(), 1)
        self.assertEqual(product.categories.first().name, "General")

    def test_create_product_with_categories_uses_provided(self):
        category = Category.objects.create(store_id=self.store.id, name="Shoes")
        product = ProductService.create_product(
            store_id=self.store.id,
            sku="CAT-002",
            name="Shoe Product",
            price=Decimal("19.00"),
            quantity=2,
            categories=[category],
        )

        self.assertEqual(product.categories.count(), 1)
        self.assertEqual(product.categories.first().id, category.id)

    def test_upsert_product_assigns_default_category_when_missing(self):
        product = ProductConfigurationService.upsert_product_with_variants(
            store=self.store,
            payload={
                "sku": "CFG-CAT-1",
                "name": "Cfg Cat Product",
                "price": Decimal("17.00"),
                "quantity": 3,
                "variants": [],
            },
        )

        self.assertEqual(product.categories.count(), 1)
        self.assertEqual(product.categories.first().name, "General")

    def test_upsert_product_accepts_explicit_category_ids(self):
        category = Category.objects.create(store_id=self.store.id, name="Accessories")
        product = ProductConfigurationService.upsert_product_with_variants(
            store=self.store,
            payload={
                "sku": "CFG-CAT-2",
                "name": "Cfg Category Product",
                "price": Decimal("22.00"),
                "quantity": 6,
                "category_ids": [category.id],
                "variants": [],
            },
        )

        self.assertEqual(product.categories.count(), 1)
        self.assertEqual(product.categories.first().id, category.id)
