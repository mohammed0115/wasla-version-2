from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.catalog.models import Inventory, Product
from apps.customers.models import Customer
from apps.orders.models import Order, OrderItem
from apps.payments.models import PaymentAttempt
from apps.settlements.models import Invoice, InvoiceLine, SettlementRecord
from apps.stores.models import Store
from apps.tenants.models import StoreProfile, Tenant


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", ".localhost"])
class MonthlyReportInvoiceDraftAPITests(APITestCase):
    def setUp(self) -> None:
        owner = get_user_model().objects.create_user(username="report-owner", password="pass12345")
        self.tenant = Tenant.objects.create(slug="report-tenant", name="Report Tenant")
        StoreProfile.objects.create(tenant=self.tenant, owner=owner)
        self.store = Store.objects.create(
            owner=owner,
            tenant=self.tenant,
            name="Report Store",
            slug="report-store",
            subdomain="report-store",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )
        self.client.force_login(owner)

        self.pending_a = self._create_settlement_record(
            amount=Decimal("100.00"),
            settlement_status=SettlementRecord.STATUS_PENDING,
            created_at=timezone.make_aware(datetime(2026, 2, 10, 10, 0, 0)),
            suffix="a",
        )
        self.pending_b = self._create_settlement_record(
            amount=Decimal("120.00"),
            settlement_status=SettlementRecord.STATUS_PENDING,
            created_at=timezone.make_aware(datetime(2026, 2, 12, 11, 0, 0)),
            suffix="b",
        )
        self.invoiced_c = self._create_settlement_record(
            amount=Decimal("90.00"),
            settlement_status=SettlementRecord.STATUS_INVOICED,
            created_at=timezone.make_aware(datetime(2026, 2, 14, 11, 0, 0)),
            suffix="c",
        )
        self._create_settlement_record(
            amount=Decimal("80.00"),
            settlement_status=SettlementRecord.STATUS_PENDING,
            created_at=timezone.make_aware(datetime(2026, 1, 20, 11, 0, 0)),
            suffix="old",
        )

    def test_monthly_report_aggregates_counts_and_totals(self):
        response = self.client.get(
            "/api/settlements/monthly-report/?year=2026&month=2",
            HTTP_HOST=f"{self.store.slug}.localhost",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        self.assertEqual(data["total_operations"], 3)
        self.assertEqual(Decimal(data["total_wasla_fee"]), Decimal("3.00"))
        self.assertEqual(len(data["settlement_ids"]), 3)

    def test_invoice_draft_is_idempotent(self):
        payload = {"year": 2026, "month": 2}

        first = self.client.post(
            "/api/settlements/invoices/draft/",
            data=payload,
            format="json",
            HTTP_HOST=f"{self.store.slug}.localhost",
        )
        second = self.client.post(
            "/api/settlements/invoices/draft/",
            data=payload,
            format="json",
            HTTP_HOST=f"{self.store.slug}.localhost",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)

        invoice_first = first.json()["data"]["invoice_id"]
        invoice_second = second.json()["data"]["invoice_id"]
        self.assertEqual(invoice_first, invoice_second)

        self.assertEqual(Invoice.objects.count(), 1)
        invoice = Invoice.objects.get(id=invoice_first)
        self.assertEqual(invoice.total_operations, 2)
        self.assertEqual(invoice.total_wasla_fee, Decimal("2.00"))

    def test_settlements_are_not_linked_twice(self):
        payload = {"year": 2026, "month": 2}

        self.client.post(
            "/api/settlements/invoices/draft/",
            data=payload,
            format="json",
            HTTP_HOST=f"{self.store.slug}.localhost",
        )
        self.client.post(
            "/api/settlements/invoices/draft/",
            data=payload,
            format="json",
            HTTP_HOST=f"{self.store.slug}.localhost",
        )

        self.assertEqual(InvoiceLine.objects.count(), 2)
        linked_ids = set(InvoiceLine.objects.values_list("settlement_id", flat=True))
        self.assertSetEqual(linked_ids, {self.pending_a.id, self.pending_b.id})

    def _create_settlement_record(
        self,
        *,
        amount: Decimal,
        settlement_status: str,
        created_at,
        suffix: str,
    ) -> SettlementRecord:
        customer = Customer.objects.create(
            store_id=self.store.id,
            email=f"buyer-{suffix}@example.com",
            full_name=f"Buyer {suffix}",
        )
        product = Product.objects.create(
            store_id=self.store.id,
            sku=f"SKU-{suffix}",
            name=f"Product {suffix}",
            price=amount,
            description_ar="",
            description_en="",
        )
        Inventory.objects.create(product=product, quantity=10, in_stock=True)

        order = Order.objects.create(
            tenant_id=self.tenant.id,
            store_id=self.store.id,
            order_number=f"ORD-{suffix}",
            customer=customer,
            total_amount=amount,
            currency="SAR",
            status="paid",
            payment_status="paid",
        )
        OrderItem.objects.create(
            tenant_id=self.tenant.id,
            order=order,
            product=product,
            quantity=1,
            price=amount,
        )

        attempt = PaymentAttempt.objects.create(
            store=self.store,
            order=order,
            provider="tap",
            method="card",
            amount=amount,
            currency="SAR",
            status=PaymentAttempt.STATUS_PAID,
            provider_reference=f"ref-{suffix}",
            idempotency_key=f"idem-{suffix}",
        )

        record = SettlementRecord.objects.create(
            store=self.store,
            order=order,
            payment_attempt=attempt,
            gross_amount=amount,
            wasla_fee=Decimal("1.00"),
            net_amount=amount - Decimal("1.00"),
            status=settlement_status,
        )
        SettlementRecord.objects.filter(id=record.id).update(created_at=created_at)
        record.refresh_from_db()
        return record
