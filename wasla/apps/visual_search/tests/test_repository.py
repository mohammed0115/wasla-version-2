from decimal import Decimal

from django.test import TestCase

from apps.visual_search.infrastructure.models import ProductEmbedding
from apps.visual_search.infrastructure.repositories.django_visual_search_repository import (
    DjangoVisualSearchRepository,
)
from catalog.models import Product
from tenants.models import Tenant


class DjangoVisualSearchRepositoryTests(TestCase):
    def setUp(self) -> None:
        self.tenant_1 = Tenant.objects.create(slug="vs-1", name="VS 1")
        self.tenant_2 = Tenant.objects.create(slug="vs-2", name="VS 2")

        self.product_1 = Product.objects.create(
            store_id=self.tenant_1.id,
            sku="VS-1",
            name="Tenant 1 Product",
            price=Decimal("100.00"),
            is_active=True,
        )
        self.product_2 = Product.objects.create(
            store_id=self.tenant_2.id,
            sku="VS-2",
            name="Tenant 2 Product",
            price=Decimal("99.00"),
            is_active=True,
        )

        ProductEmbedding.objects.create(
            store_id=self.tenant_1.id,
            product=self.product_1,
            similarity_hint=0.95,
        )
        ProductEmbedding.objects.create(
            store_id=self.tenant_2.id,
            product=self.product_2,
            similarity_hint=0.99,
        )

    def test_find_similar_products_enforces_tenant_isolation(self):
        repository = DjangoVisualSearchRepository()
        rows = repository.find_similar_products(
            tenant_id=self.tenant_1.id,
            embedding_vector=[0.9],
            limit=10,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].product_id, self.product_1.id)
