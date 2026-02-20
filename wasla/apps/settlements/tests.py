from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model

from apps.customers.models import Customer
from apps.orders.models import Order
from apps.settlements.application.use_cases.create_settlement import (
    CreateSettlementCommand,
    CreateSettlementUseCase,
)
from apps.settlements.models import SettlementItem
from apps.stores.models import Store
from apps.tenants.models import Tenant


class SettlementTenantTests(TestCase):
    def test_create_settlement_sets_tenant(self):
        tenant = Tenant.objects.create(slug="tenant-s", name="Tenant S", is_active=True)
        owner = get_user_model().objects.create_user(username="owner-settle", password="pass12345")
        store = Store.objects.create(
            owner=owner,
            tenant=tenant,
            name="Store S",
            slug="store-s",
            subdomain="store-s",
            status=Store.STATUS_ACTIVE,
            country="SA",
        )
        customer = Customer.objects.create(
            store_id=store.id,
            email="settlement@example.com",
            full_name="Settlement Customer",
            group="retail",
            is_active=True,
        )
        order = Order.objects.create(
            tenant_id=tenant.id,
            store_id=store.id,
            order_number="SETTLE-1",
            customer=customer,
            status="paid",
            payment_status="paid",
            total_amount=Decimal("50.00"),
        )

        period_start = date.today() - timedelta(days=1)
        period_end = date.today() + timedelta(days=1)
        settlement = CreateSettlementUseCase.execute(
            CreateSettlementCommand(store_id=store.id, period_start=period_start, period_end=period_end)
        )

        self.assertEqual(settlement.tenant_id, tenant.id)
        item = SettlementItem.objects.filter(settlement_id=settlement.id).first()
        self.assertIsNotNone(item)
        self.assertEqual(item.tenant_id, tenant.id)
