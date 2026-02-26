from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from django.db import IntegrityError, transaction

from apps.catalog.models import Category, Inventory, Product, ProductImage, ProductOption, ProductOptionGroup, ProductVariant
from apps.stores.models import Store


class VariantPricingService:
    @staticmethod
    def resolve_price(*, product: Product, variant: ProductVariant | None = None) -> Decimal:
        if variant and variant.price_override is not None:
            return Decimal(str(variant.price_override))
        return Decimal(str(product.price))


class ProductVariantService:
    @staticmethod
    def get_variant_for_store(*, store_id: int, product_id: int, variant_id: int) -> ProductVariant:
        variant = ProductVariant.objects.filter(
            id=variant_id,
            store_id=store_id,
            product_id=product_id,
        ).first()
        if not variant:
            raise ValueError("Variant not found.")
        return variant

    @staticmethod
    def get_variants_map(*, store_id: int, variant_ids: Iterable[int]) -> dict[int, ProductVariant]:
        ids = [int(variant_id) for variant_id in variant_ids if variant_id]
        if not ids:
            return {}
        return {
            item.id: item
            for item in ProductVariant.objects.filter(store_id=store_id, id__in=ids).select_related("product")
        }

    @staticmethod
    def assert_checkout_stock(*, store_id: int, items: Iterable[dict]) -> None:
        for item in items:
            quantity = int(item.get("quantity") or 0)
            if quantity < 1:
                raise ValueError("Quantity must be at least 1.")

            variant = item.get("variant")
            if variant is not None:
                if variant.store_id != store_id:
                    raise ValueError("Variant store mismatch.")
                if not variant.is_active:
                    raise ValueError("Variant is inactive.")
                if int(variant.stock_quantity) < quantity:
                    raise ValueError("Variant out of stock.")
                continue

            product = item.get("product")
            if not product:
                raise ValueError("Product is required.")
            inventory = Inventory.objects.filter(product_id=product.id).first()
            if not inventory or int(inventory.quantity) < quantity:
                raise ValueError(f"Insufficient stock for '{product}'.")


class ProductConfigurationService:
    @staticmethod
    @transaction.atomic
    def upsert_product_with_variants(
        *,
        store: Store,
        payload: dict,
        product: Product | None = None,
    ) -> Product:
        quantity = max(0, int(payload.get("quantity", 0) or 0))
        product_fields = {
            "sku": str(payload.get("sku", "")).strip(),
            "name": str(payload.get("name", "")).strip(),
            "price": payload.get("price"),
            "description_ar": payload.get("description_ar", "") or "",
            "description_en": payload.get("description_en", "") or "",
            "is_active": quantity > 0,
        }
        if "image" in payload:
            product_fields["image"] = payload.get("image")

        if not product_fields["sku"]:
            raise ValueError("SKU is required")
        if not product_fields["name"]:
            raise ValueError("Product name is required")

        if product is None:
            product = Product.objects.create(store_id=store.id, **product_fields)
        else:
            if product.store_id != store.id:
                raise ValueError("Product store mismatch")
            for field_name, field_value in product_fields.items():
                setattr(product, field_name, field_value)
            product.save()

        Inventory.objects.update_or_create(
            product=product,
            defaults={"quantity": quantity, "in_stock": quantity > 0},
        )

        if payload.get("image"):
            ProductConfigurationService._upsert_legacy_primary_image(
                product=product,
                image_file=payload.get("image"),
                alt_text=product.name,
            )

        images_payload = payload.get("images")
        if images_payload is not None:
            ProductConfigurationService._replace_images(product=product, images_payload=images_payload)

        option_groups = payload.get("option_groups")
        if option_groups is not None:
            ProductConfigurationService._replace_option_groups(store=store, groups_payload=option_groups)

        variants = payload.get("variants")
        if variants is not None:
            ProductConfigurationService._replace_variants(
                store=store,
                product=product,
                variants_payload=variants,
            )

        ProductConfigurationService._sync_product_categories(
            store=store,
            product=product,
            category_ids=payload.get("category_ids"),
        )

        return product

    @staticmethod
    def _sync_product_categories(*, store: Store, product: Product, category_ids: list[int] | None) -> None:
        if category_ids is not None:
            normalized_ids = [int(category_id) for category_id in category_ids if category_id]
            selected_categories = list(Category.objects.filter(store_id=store.id, id__in=normalized_ids))
            if len(selected_categories) != len(set(normalized_ids)):
                raise ValueError("One or more categories were not found in this store.")
            product.categories.set(selected_categories)

        if not product.categories.exists():
            default_category, _ = Category.objects.get_or_create(store_id=store.id, name="General")
            product.categories.add(default_category)

    @staticmethod
    def _replace_option_groups(*, store: Store, groups_payload: list[dict]) -> None:
        for group_payload in groups_payload:
            group_id = group_payload.get("id")
            defaults = {
                "name": str(group_payload.get("name", "")).strip(),
                "is_required": bool(group_payload.get("is_required", False)),
                "position": int(group_payload.get("position", 0) or 0),
            }
            if not defaults["name"]:
                raise ValueError("Option group name is required.")

            if group_id:
                group = ProductOptionGroup.objects.filter(id=group_id, store=store).first()
                if not group:
                    raise ValueError("Option group not found.")
                for field_name, field_value in defaults.items():
                    setattr(group, field_name, field_value)
                group.save()
            else:
                group = ProductOptionGroup.objects.create(store=store, **defaults)

            keep_option_ids: list[int] = []
            for option_payload in group_payload.get("options") or []:
                option_id = option_payload.get("id")
                value = str(option_payload.get("value", "")).strip()
                if not value:
                    raise ValueError("Option value is required.")
                if option_id:
                    option = ProductOption.objects.filter(id=option_id, group=group).first()
                    if not option:
                        raise ValueError("Option not found.")
                    option.value = value
                    option.save(update_fields=["value"])
                else:
                    option, _ = ProductOption.objects.get_or_create(group=group, value=value)
                keep_option_ids.append(option.id)

            ProductOption.objects.filter(group=group).exclude(id__in=keep_option_ids).delete()

    @staticmethod
    def _replace_variants(*, store: Store, product: Product, variants_payload: list[dict]) -> None:
        keep_variant_ids: list[int] = []
        for variant_payload in variants_payload:
            variant_id = variant_payload.get("id")
            sku = str(variant_payload.get("sku", "")).strip()
            if not sku:
                raise ValueError("Variant SKU is required.")

            defaults = {
                "sku": sku,
                "price_override": variant_payload.get("price_override"),
                "stock_quantity": max(0, int(variant_payload.get("stock_quantity", 0) or 0)),
                "is_active": bool(variant_payload.get("is_active", True)),
            }

            try:
                if variant_id:
                    variant = ProductVariant.objects.filter(id=variant_id, product=product, store_id=store.id).first()
                    if not variant:
                        raise ValueError("Variant not found.")
                    for field_name, field_value in defaults.items():
                        setattr(variant, field_name, field_value)
                    variant.save()
                else:
                    variant = ProductVariant.objects.create(product=product, store_id=store.id, **defaults)
            except IntegrityError as exc:
                raise ValueError("Variant SKU must be unique per store.") from exc

            option_ids = [int(option_id) for option_id in (variant_payload.get("option_ids") or []) if option_id]
            if option_ids:
                options = list(
                    ProductOption.objects.filter(id__in=option_ids, group__store_id=store.id).select_related("group")
                )
                if len(options) != len(set(option_ids)):
                    raise ValueError("One or more options were not found in this store.")
            else:
                options = ProductConfigurationService._resolve_options_by_label(
                    store=store,
                    options_payload=variant_payload.get("options") or [],
                )

            if options:
                variant.options.set(options)
            else:
                variant.options.clear()

            keep_variant_ids.append(variant.id)

        ProductVariant.objects.filter(product=product, store_id=store.id).exclude(id__in=keep_variant_ids).delete()

    @staticmethod
    def _upsert_legacy_primary_image(*, product: Product, image_file, alt_text: str = "") -> None:
        primary = ProductImage.objects.filter(product=product, is_primary=True).first()
        if primary:
            primary.image = image_file
            if alt_text:
                primary.alt_text = alt_text
            primary.save()
            return

        ProductImage.objects.create(
            product=product,
            image=image_file,
            alt_text=alt_text,
            position=0,
            is_primary=True,
        )

    @staticmethod
    def _replace_images(*, product: Product, images_payload: list[dict]) -> None:
        keep_image_ids: list[int] = []
        for image_payload in images_payload:
            image_id = image_payload.get("id")
            image_file = image_payload.get("image")
            defaults = {
                "alt_text": str(image_payload.get("alt_text", "") or ""),
                "position": int(image_payload.get("position", 0) or 0),
                "is_primary": bool(image_payload.get("is_primary", False)),
            }

            if image_id:
                product_image = ProductImage.objects.filter(id=image_id, product=product).first()
                if not product_image:
                    raise ValueError("Product image not found.")
                for field_name, field_value in defaults.items():
                    setattr(product_image, field_name, field_value)
                if image_file:
                    product_image.image = image_file
                product_image.save()
            else:
                if not image_file:
                    raise ValueError("Image file is required for new product images.")
                product_image = ProductImage.objects.create(product=product, image=image_file, **defaults)

            keep_image_ids.append(product_image.id)

        ProductImage.objects.filter(product=product).exclude(id__in=keep_image_ids).delete()

    @staticmethod
    def _resolve_options_by_label(*, store: Store, options_payload: list[dict]) -> list[ProductOption]:
        resolved: list[ProductOption] = []
        for raw_item in options_payload:
            group_name = str(raw_item.get("group", "")).strip()
            value = str(raw_item.get("value", "")).strip()
            if not group_name or not value:
                raise ValueError("Variant options must include group and value.")

            group = ProductOptionGroup.objects.filter(store=store, name=group_name).first()
            if not group:
                raise ValueError(f"Option group '{group_name}' not found.")
            option = ProductOption.objects.filter(group=group, value=value).first()
            if not option:
                raise ValueError(f"Option '{value}' not found in group '{group_name}'.")
            resolved.append(option)
        return resolved
