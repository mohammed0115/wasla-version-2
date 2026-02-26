from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from django.db import transaction

from ..models import Category, Inventory, Product


class ProductService:
    """Catalog write operations (MVP).

    This project uses a simple multi-tenant pattern by scoping data with `store_id`.
    The service keeps Product + Inventory creation consistent.
    """

    @staticmethod
    @transaction.atomic
    def create_product(
        *,
        store_id: int,
        sku: str,
        name: str,
        price: Decimal,
        categories: Iterable[Category] | None = None,
        quantity: int = 0,
        image_file=None,
        is_active: bool = True,
        description_ar: str = "",
        description_en: str = "",
    ) -> Product:
        """Create a product and its inventory row.

        Notes:
        - Enforces tenant isolation by requiring categories to match the same `store_id`.
        - Creates/updates inventory for the created product.
        """

        if not sku:
            raise ValueError("SKU is required")
        if not name:
            raise ValueError("Product name is required")

        normalized_quantity = max(0, int(quantity or 0))

        product = Product.objects.create(
            store_id=store_id,
            sku=str(sku).strip(),
            name=str(name).strip(),
            price=price,
            is_active=normalized_quantity > 0,
            description_ar=description_ar or "",
            description_en=description_en or "",
            image=image_file,
        )

        ProductService._assign_categories(
            product=product,
            store_id=store_id,
            categories=categories,
        )

        Inventory.objects.update_or_create(
            product=product,
            defaults={
                "quantity": normalized_quantity,
                "in_stock": normalized_quantity > 0,
            },
        )

        return product

    @staticmethod
    def _assign_categories(*, product: Product, store_id: int, categories: Iterable[Category] | None) -> None:
        if categories:
            selected_categories = list(categories)
            for category in selected_categories:
                if getattr(category, "store_id", None) != store_id:
                    raise ValueError("Category store_id mismatch")
            product.categories.set(selected_categories)

        if not product.categories.exists():
            default_category, _ = Category.objects.get_or_create(
                store_id=store_id,
                name="General",
            )
            product.categories.add(default_category)
