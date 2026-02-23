from __future__ import annotations

from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from apps.stores.models import Store
from apps.tenants.models import Tenant

from ..models import PaymentTransaction, StoreSubscription, SubscriptionPlan


class PaymentTransactionService:
    @staticmethod
    @transaction.atomic
    def record_manual_payment(
        *,
        tenant: Tenant,
        plan: SubscriptionPlan,
        amount,
        reference: str = "",
        currency: str = "SAR",
        status: str = PaymentTransaction.STATUS_PAID,
        recorded_by=None,
    ) -> PaymentTransaction:
        tx = PaymentTransaction.objects.create(
            tenant=tenant,
            plan=plan,
            amount=amount,
            currency=currency or "SAR",
            method=PaymentTransaction.METHOD_MANUAL,
            reference=(reference or "").strip(),
            status=status,
            recorded_by=recorded_by,
            paid_at=timezone.now() if status == PaymentTransaction.STATUS_PAID else None,
        )

        if status == PaymentTransaction.STATUS_PAID:
            start = date.today()
            end = start + (
                timedelta(days=30) if plan.billing_cycle == "monthly" else timedelta(days=365)
            )
            subscription, _ = StoreSubscription.objects.update_or_create(
                store_id=tenant.id,
                defaults={
                    "plan": plan,
                    "status": "active",
                    "start_date": start,
                    "end_date": end,
                },
            )
            tx.subscription = subscription
            tx.save(update_fields=["subscription"])

            Store.objects.filter(tenant_id=tenant.id).update(status=Store.STATUS_ACTIVE)
            Tenant.objects.filter(id=tenant.id).update(is_active=True)

        return tx
