from __future__ import annotations

import io
import random
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.models import Category, Product, Inventory

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:  # pragma: no cover
    Image = None


AR_HELP = """أمر لإنشاء منتجات ديمو "أقرب للواقع" داخل متجر محدد (store_id = tenant_id).

الهدف:
- تجهيز كتالوج جاهز للديمو خلال دقيقة.
- الصور مُولَّدة بنمطين: خلفية بيضاء (white_background=True غالباً) وخلفية ملونة.
- ألوان/سطوع متعمدين لتفعيل فلاتر Visual Search (color/brightness/white_background).

مناسب لـ:
- Demo للإدارة
- اختبار الفهرسة + Visual Search بسرعة
"""

EN_HELP = """Seed more realistic demo products (with generated images) for a given store (store_id == tenant_id).

Goal:
- Create a demo catalog quickly.
- Generated images include both white-background and colored-background variants to exercise Visual Search filters.
"""


def _ensure_category(store_id: int, name: str, parent: Category | None = None) -> Category:
    obj, _ = Category.objects.get_or_create(store_id=store_id, name=name, parent=parent)
    return obj


def _rgb_for_color_label(label: str, brightness: str = "normal") -> tuple[int, int, int]:
    base = {
        "red": (231, 76, 60),
        "orange": (230, 126, 34),
        "yellow": (241, 196, 15),
        "green": (46, 204, 113),
        "cyan": (26, 188, 156),
        "blue": (52, 152, 219),
        "purple": (155, 89, 182),
        "gray": (149, 165, 166),
        "black": (44, 62, 80),
        "white": (245, 245, 245),
    }.get(label, (52, 152, 219))

    def clamp(x: int) -> int:
        return max(0, min(255, x))

    if brightness == "dark":
        return tuple(clamp(int(c * 0.65)) for c in base)
    if brightness == "bright":
        return tuple(clamp(int(c + (255 - c) * 0.35)) for c in base)
    return base


def _draw_icon(draw: ImageDraw.ImageDraw, kind: str, color: tuple[int, int, int]) -> None:
    """Draw a simple object shape in the center to make embeddings/attributes more stable."""
    # Canvas is 768x768
    cx, cy = 384, 380
    if kind == "tshirt":
        # Simple t-shirt: body + sleeves
        body = [(cx - 130, cy - 120), (cx + 130, cy - 120), (cx + 130, cy + 170), (cx - 130, cy + 170)]
        left_sleeve = [(cx - 210, cy - 90), (cx - 130, cy - 120), (cx - 130, cy + 20), (cx - 210, cy + 20)]
        right_sleeve = [(cx + 210, cy - 90), (cx + 130, cy - 120), (cx + 130, cy + 20), (cx + 210, cy + 20)]
        draw.polygon(body, fill=color)
        draw.polygon(left_sleeve, fill=color)
        draw.polygon(right_sleeve, fill=color)
        # collar
        draw.ellipse([cx - 40, cy - 140, cx + 40, cy - 70], fill=(255, 255, 255))
    elif kind == "shoe":
        # Simple sneaker
        draw.rounded_rectangle([cx - 170, cy + 40, cx + 170, cy + 140], radius=30, fill=color)
        draw.rounded_rectangle([cx - 120, cy - 30, cx + 120, cy + 60], radius=40, fill=color)
        # sole
        draw.rectangle([cx - 175, cy + 130, cx + 175, cy + 155], fill=(255, 255, 255))
    elif kind == "phone":
        draw.rounded_rectangle([cx - 110, cy - 170, cx + 110, cy + 190], radius=35, fill=color)
        draw.ellipse([cx - 15, cy + 165, cx + 15, cy + 195], fill=(255, 255, 255))
        draw.rounded_rectangle([cx - 85, cy - 135, cx + 85, cy + 135], radius=20, fill=(0, 0, 0))
    elif kind == "bag":
        draw.rounded_rectangle([cx - 150, cy - 80, cx + 150, cy + 170], radius=30, fill=color)
        draw.arc([cx - 90, cy - 170, cx + 90, cy - 20], start=200, end=-20, fill=(255, 255, 255), width=12)
    elif kind == "lamp":
        # base + stand + shade
        draw.ellipse([cx - 90, cy + 140, cx + 90, cy + 200], fill=color)
        draw.rectangle([cx - 12, cy - 40, cx + 12, cy + 150], fill=color)
        draw.polygon([(cx - 140, cy - 40), (cx + 140, cy - 40), (cx + 90, cy + 60), (cx - 90, cy + 60)], fill=color)
    else:
        # generic box
        draw.rounded_rectangle([cx - 180, cy - 120, cx + 180, cy + 180], radius=35, fill=color)


def _generate_demo_image(
    label: str,
    price_text: str,
    *,
    object_kind: str,
    object_color: str,
    brightness: str,
    white_background: bool,
) -> bytes:
    if Image is None:
        raise CommandError("Pillow is required to generate demo images. Install pillow.")

    bg = (255, 255, 255) if white_background else _rgb_for_color_label("gray", "dark")
    obj_rgb = _rgb_for_color_label(object_color, brightness)

    img = Image.new("RGB", (768, 768), color=bg)
    draw = ImageDraw.Draw(img)

    # Border card
    pad = 36
    border = (230, 230, 230) if white_background else (255, 255, 255)
    draw.rounded_rectangle([pad, pad, 768 - pad, 768 - pad], radius=28, outline=border, width=6)

    # Object
    _draw_icon(draw, object_kind, obj_rgb)

    # Label (small, bottom)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    txt_color = (30, 30, 30) if white_background else (255, 255, 255)
    draw.text((pad + 18, 768 - pad - 55), label[:34], fill=txt_color, font=font)
    draw.text((pad + 18, 768 - pad - 30), price_text, fill=txt_color, font=font)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    buf.seek(0)
    return buf.read()


class Command(BaseCommand):
    help = f"{EN_HELP}\n\n{AR_HELP}"

    def add_arguments(self, parser):
        parser.add_argument("--store-id", type=int, required=True, help="Tenant/Store id (store_id).")
        parser.add_argument("--count", type=int, default=24, help="How many demo products to create (default=24).")
        parser.add_argument("--reset", action="store_true", help="Delete existing products for this store before seeding.")
        parser.add_argument("--with-inventory", action="store_true", help="Also create inventory rows (default off).")
        parser.add_argument(
            "--white-bg-ratio",
            type=float,
            default=0.65,
            help="Ratio of products generated with a white background (default=0.65).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        store_id = options["store_id"]
        count = max(1, int(options["count"] or 24))
        reset = bool(options.get("reset"))
        with_inventory = bool(options.get("with_inventory"))
        white_bg_ratio = float(options.get("white_bg_ratio") or 0.65)

        if Image is None:
            raise CommandError("Pillow is required to generate demo images. Install pillow or disable image generation.")

        if reset:
            Inventory.objects.filter(product__store_id=store_id).delete()
            Product.objects.filter(store_id=store_id).delete()
            Category.objects.filter(store_id=store_id).delete()

        # Realistic category tree (store-scoped)
        cat_fashion = _ensure_category(store_id, "Fashion")
        cat_men = _ensure_category(store_id, "Men", parent=cat_fashion)
        cat_women = _ensure_category(store_id, "Women", parent=cat_fashion)
        cat_shoes = _ensure_category(store_id, "Shoes", parent=cat_fashion)
        cat_accessories = _ensure_category(store_id, "Accessories", parent=cat_fashion)

        cat_electronics = _ensure_category(store_id, "Electronics")
        cat_phones = _ensure_category(store_id, "Phones & Accessories", parent=cat_electronics)
        cat_wearables = _ensure_category(store_id, "Wearables", parent=cat_electronics)

        cat_home = _ensure_category(store_id, "Home")
        cat_kitchen = _ensure_category(store_id, "Kitchen", parent=cat_home)
        cat_lighting = _ensure_category(store_id, "Lighting", parent=cat_home)

        # Demo product templates: (category, object_kind, name_en, name_ar, material, style)
        templates = [
            (cat_men, "tshirt", "Linen Shirt", "قميص كتان", "linen", "casual"),
            (cat_women, "tshirt", "Summer Dress", "فستان صيفي", "cotton", "casual"),
            (cat_shoes, "shoe", "Running Sneakers", "حذاء رياضي للجري", "mesh", "sport"),
            (cat_shoes, "shoe", "Classic Sneakers", "سنيكرز كلاسيك", "leather", "street"),
            (cat_accessories, "bag", "Everyday Backpack", "حقيبة ظهر يومية", "polyester", "street"),
            (cat_phones, "phone", "Phone Case", "جراب هاتف", "silicone", "minimal"),
            (cat_wearables, "phone", "Smart Watch", "ساعة ذكية", "metal", "modern"),
            (cat_kitchen, "box", "Coffee Mug", "كوب قهوة", "ceramic", "minimal"),
            (cat_lighting, "lamp", "Desk Lamp", "مصباح مكتب", "plastic", "modern"),
        ]

        color_cycle = ["red", "blue", "green", "orange", "yellow", "purple", "cyan", "gray", "black"]
        brightness_cycle = ["normal", "bright", "dark"]

        created = 0

        for i in range(1, count + 1):
            tpl = templates[(i - 1) % len(templates)]
            category, obj_kind, name_en, name_ar, material, style = tpl

            color = color_cycle[(i - 1) % len(color_cycle)]
            brightness = brightness_cycle[(i - 1) % len(brightness_cycle)]
            white_bg = (random.random() < white_bg_ratio)

            sku = f"DEMO-{i:03d}"

            # Prices by category group
            if category in [cat_phones, cat_wearables]:
                price = Decimal(str(random.choice([399.0, 499.0, 699.0, 899.0, 1199.0])))
            elif category in [cat_shoes]:
                price = Decimal(str(random.choice([149.0, 199.0, 249.0, 299.0])))
            else:
                price = Decimal(str(random.choice([39.0, 59.0, 79.0, 99.0, 129.0])))

            # Enrich name so CLIP/text search can benefit in demos
            # (kept short; also helps humans browsing the catalog)
            name = f"{name_en} - {color.title()} ({material}, {style}) #{i}"

            p = Product.objects.create(
                store_id=store_id,
                sku=sku,
                name=name,
                price=price,
                description_ar=f"{name_ar} (لون: {color}) — منتج تجريبي لاختبار البحث البصري والفلاتر.",
                description_en=f"{name_en} in {color}. Demo product for Visual Search (filters: color/brightness/white background).",
                is_active=True,
            )
            p.categories.add(category)

            # Generate a controlled image
            img_bytes = _generate_demo_image(
                label=name_en,
                price_text=f"{price} SAR",
                object_kind=obj_kind,
                object_color=color,
                brightness=brightness,
                white_background=white_bg,
            )
            filename = f"demo_{sku.lower()}_{color}_{brightness}_{'wb' if white_bg else 'cb'}.jpg"
            p.image.save(filename, ContentFile(img_bytes), save=True)

            if with_inventory:
                Inventory.objects.create(product=p, quantity=random.randint(5, 50), in_stock=True)

            created += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded {created} realistic demo products for store_id={store_id}. reset={reset}"))
