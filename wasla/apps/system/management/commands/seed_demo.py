from __future__ import annotations

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.catalog.models import Category, Product
from apps.orders.models import Order
from apps.stores.models import Store


class Command(BaseCommand):
    help = "Seed demo data for Wasla V2 (merchant store, products, and a sample order)."

    def add_arguments(self, parser):
        parser.add_argument("--email", default="merchant@wasla.local")
        parser.add_argument("--password", default="admin123")
        parser.add_argument("--store", default="Wasla Demo Store")

    def handle(self, *args, **options):
        User = get_user_model()
        email = options["email"]
        password = options["password"]
        store_name = options["store"]

        user, created = User.objects.get_or_create(
            username=email,
            defaults={"email": email, "is_staff": True, "is_active": True},
        )
        if created:
            user.set_password(password)
            user.save()

        store, _ = Store.objects.get_or_create(
            owner=user,
            defaults={
                "name": store_name,
                "subdomain": "demo",
                "description": "Seeded store for local testing",
            },
        )

        fashion, _ = Category.objects.get_or_create(store_id=store.id, name="Fashion")
        electronics, _ = Category.objects.get_or_create(store_id=store.id, name="Electronics")

        p1, _ = Product.objects.get_or_create(
            store_id=store.id,
            name="Classic T-Shirt",
            defaults={
                "description": "Soft cotton tee (seed)",
                "price": Decimal("59.00"),
                "currency": "SAR",
                "is_active": True,
            },
        )
        p1.categories.set([fashion])

        p2, _ = Product.objects.get_or_create(
            store_id=store.id,
            name="Wireless Earbuds",
            defaults={
                "description": "Noise reduction (seed)",
                "price": Decimal("199.00"),
                "currency": "SAR",
                "is_active": True,
            },
        )
        p2.categories.set([electronics])

        items = [
            {"product_id": p1.id, "name": p1.name, "qty": 1, "unit_price": str(p1.price)},
            {"product_id": p2.id, "name": p2.name, "qty": 1, "unit_price": str(p2.price)},
        ]
        total = p1.price + p2.price

        Order.objects.get_or_create(
            store_id=store.id,
            customer_email="customer@example.com",
            defaults={
                "total_amount": total,
                "currency": "SAR",
                "status": Order.Status.PAID,
                "payment_status": Order.PaymentStatus.PAID,
                "shipping_address": "Riyadh, SA",
                "items": json.dumps(items),
            },
        )

        self.stdout.write(self.style.SUCCESS("Seed completed."))
        self.stdout.write(f"Login: {email} / {password}")
        self.stdout.write("Open merchant dashboard: /merchant/dashboard")
