from __future__ import annotations

import io
import random
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from PIL import Image, ImageDraw

from apps.catalog.models import Category, Product
from apps.catalog.services.product_service import ProductService
from apps.subscriptions.models import SubscriptionPlan
from apps.subscriptions.services.subscription_service import SubscriptionService
from apps.tenants.models import Tenant


def _generate_product_image(*, sku: str, size: int = 800) -> ContentFile:
    palette = [
        (37, 99, 235),   # blue
        (245, 158, 11),  # amber
        (16, 185, 129),  # green
        (236, 72, 153),  # pink
        (99, 102, 241),  # indigo
        (20, 184, 166),  # teal
    ]
    bg = random.choice(palette)
    image = Image.new("RGB", (size, size), bg)
    draw = ImageDraw.Draw(image)

    pad = int(size * 0.08)
    draw.rounded_rectangle(
        (pad, pad, size - pad, size - pad),
        radius=int(size * 0.08),
        outline=(255, 255, 255),
        width=int(size * 0.02),
    )

    label = sku.upper()
    draw.text((pad * 2, pad * 2), label, fill=(255, 255, 255))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return ContentFile(buffer.getvalue(), name=f"{sku.lower()}.png")


class Command(BaseCommand):
    help = "Seed sample tenant/catalog data (with sample product images)."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", default="default", help="Tenant slug to seed.")
        parser.add_argument(
            "--create-superuser",
            action="store_true",
            help="Create a demo superuser if none exists.",
        )
        parser.add_argument("--username", default="admin", help="Demo superuser username.")
        parser.add_argument("--password", default="admin12345", help="Demo superuser password.")

    @transaction.atomic
    def handle(self, *args, **options):
        tenant_slug: str = options["tenant"]
        tenant, _ = Tenant.objects.get_or_create(
            slug=tenant_slug,
            defaults={"name": tenant_slug.title(), "is_active": True},
        )

        plan = (
            SubscriptionPlan.objects.filter(name="Basic", is_active=True).first()
            or SubscriptionPlan.objects.filter(is_active=True).order_by("price", "id").first()
        )
        if plan and not SubscriptionService.get_active_subscription(tenant.id):
            SubscriptionService.subscribe_store(tenant.id, plan)

        if options["create_superuser"]:
            User = get_user_model()
            if not User.objects.filter(is_superuser=True).exists():
                User.objects.create_superuser(
                    username=options["username"],
                    password=options["password"],
                    email="",
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created superuser '{options['username']}' (password: {options['password']})"
                    )
                )

        categories = [
            "إلكترونيات",
            "ملابس",
            "منزل",
            "جمال",
            "رياضة",
            "أطفال",
            "بقالة",
        ]
        category_map: dict[str, Category] = {}
        for name in categories:
            cat, _ = Category.objects.get_or_create(store_id=tenant.id, name=name)
            category_map[name] = cat

        products = [
            ("SAMPLE-EL-001", "هاتف ذكي", "إلكترونيات", Decimal("199.00"), 25),
            ("SAMPLE-EL-002", "سماعات بلوتوث", "إلكترونيات", Decimal("39.00"), 80),
            ("SAMPLE-EL-003", "ساعة ذكية", "إلكترونيات", Decimal("59.00"), 40),
            ("SAMPLE-FA-001", "تيشيرت قطن", "ملابس", Decimal("12.00"), 120),
            ("SAMPLE-FA-002", "حذاء رياضي", "ملابس", Decimal("45.00"), 60),
            ("SAMPLE-HO-001", "مصباح مكتبي", "منزل", Decimal("18.00"), 30),
            ("SAMPLE-HO-002", "طقم أواني", "منزل", Decimal("75.00"), 15),
            ("SAMPLE-BE-001", "عطر", "جمال", Decimal("29.00"), 50),
            ("SAMPLE-SP-001", "كرة قدم", "رياضة", Decimal("15.00"), 40),
            ("SAMPLE-KI-001", "لعبة تعليمية", "أطفال", Decimal("22.00"), 35),
            ("SAMPLE-GR-001", "قهوة", "بقالة", Decimal("6.50"), 200),
            ("SAMPLE-GR-002", "شاي", "بقالة", Decimal("4.25"), 160),
        ]

        created = 0
        updated_images = 0
        for sku, name, category_name, price, qty in products:
            existing = Product.objects.filter(store_id=tenant.id, sku=sku).first()
            image_file = _generate_product_image(sku=sku)

            if existing:
                if not existing.image:
                    existing.image.save(image_file.name, image_file, save=True)
                    updated_images += 1
                continue

            ProductService.create_product(
                store_id=tenant.id,
                sku=sku,
                name=name,
                price=price,
                categories=[category_map[category_name]],
                quantity=qty,
                image_file=image_file,
            )
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded tenant '{tenant.slug}' (store_id={tenant.id}): categories={len(category_map)}, products_created={created}, images_updated={updated_images}"
            )
        )

