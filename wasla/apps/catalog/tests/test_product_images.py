from __future__ import annotations

from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings

from apps.catalog.models import Product, ProductImage
from apps.stores.models import Store
from apps.tenants.models import Tenant


def _sample_png(name: str = "sample.png"):
    from PIL import Image

    output = BytesIO()
    Image.new("RGB", (2, 2), color=(255, 0, 0)).save(output, format="PNG")
    output.seek(0)
    return SimpleUploadedFile(name=name, content=output.read(), content_type="image/png")


class ProductImageModelTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        user = get_user_model().objects.create_user(username="owner-image-model", password="pass12345")
        tenant = Tenant.objects.create(slug="tenant-image-model", name="Tenant Image Model", is_active=True)
        store = Store.objects.create(
            owner=user,
            tenant=tenant,
            name="Image Store",
            slug="image-store",
            subdomain="image-store",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )
        self.product = Product.objects.create(
            store_id=store.id,
            sku="IMG-BASE",
            name="Image Product",
            price="10.00",
            is_active=True,
        )

    def test_first_image_becomes_primary_and_updates_product_image(self):
        first = ProductImage.objects.create(product=self.product, image=_sample_png("first.png"), position=1)
        self.product.refresh_from_db()

        self.assertTrue(first.is_primary)
        self.assertTrue(bool(self.product.image))

    def test_only_one_primary_image_per_product(self):
        first = ProductImage.objects.create(product=self.product, image=_sample_png("first.png"), position=1)
        second = ProductImage.objects.create(
            product=self.product,
            image=_sample_png("second.png"),
            position=2,
            is_primary=True,
        )

        first.refresh_from_db()
        second.refresh_from_db()
        self.product.refresh_from_db()

        self.assertFalse(first.is_primary)
        self.assertTrue(second.is_primary)
        self.assertEqual(self.product.image.name, second.image.name)


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", ".localhost"])
class ProductImageBackwardCompatibilityAPITests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner-image-api", password="pass12345")
        self.client.force_login(self.owner)
        self.tenant = Tenant.objects.create(slug="tenant-image-api", name="Tenant Image API", is_active=True)
        self.store = Store.objects.create(
            owner=self.owner,
            tenant=self.tenant,
            name="Image API Store",
            slug="image-api-store",
            subdomain="image-api-store",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )

    def test_legacy_image_field_creates_primary_product_image(self):
        response = self.client.post(
            "/api/catalog/products/",
            data={
                "sku": "LEG-IMG-1",
                "name": "Legacy Image Product",
                "price": "55.00",
                "quantity": 3,
                "image": _sample_png("legacy.png"),
            },
            HTTP_HOST="image-api-store.localhost",
        )
        self.assertEqual(response.status_code, 201)

        product = Product.objects.get(sku="LEG-IMG-1", store_id=self.store.id)
        images = ProductImage.objects.filter(product=product)
        self.assertEqual(images.count(), 1)
        self.assertTrue(images.first().is_primary)
        self.assertTrue(bool(product.image))
