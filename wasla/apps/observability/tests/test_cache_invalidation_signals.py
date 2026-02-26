from __future__ import annotations

from apps.catalog.models import Product
from core.infrastructure.store_cache import StoreCacheService



def test_product_save_bumps_catalog_cache_versions(db):
    store_id = 901
    before = StoreCacheService.get_namespace_version(store_id=store_id, namespace="product_detail")

    Product.objects.create(
        store_id=store_id,
        sku="SKU-901",
        name="Signal Test Product",
        price="10.00",
        is_active=True,
    )

    after = StoreCacheService.get_namespace_version(store_id=store_id, namespace="product_detail")
    assert after == before + 1


def test_product_update_invalidates_storefront_listing_cache(db):
    store_id = 902
    product = Product.objects.create(
        store_id=store_id,
        sku="SKU-902",
        name="Before",
        price="10.00",
        is_active=True,
    )

    value1, hit1 = StoreCacheService.get_or_set(
        store_id=store_id,
        namespace="storefront_products",
        key_parts=["home", "all"],
        producer=lambda: [product.name],
        timeout=60,
    )
    assert hit1 is False
    assert value1 == ["Before"]

    value2, hit2 = StoreCacheService.get_or_set(
        store_id=store_id,
        namespace="storefront_products",
        key_parts=["home", "all"],
        producer=lambda: ["Ignored"],
        timeout=60,
    )
    assert hit2 is True
    assert value2 == ["Before"]

    product.name = "After"
    product.save(update_fields=["name"])

    value3, hit3 = StoreCacheService.get_or_set(
        store_id=store_id,
        namespace="storefront_products",
        key_parts=["home", "all"],
        producer=lambda: [product.name],
        timeout=60,
    )
    assert hit3 is False
    assert value3 == ["After"]
