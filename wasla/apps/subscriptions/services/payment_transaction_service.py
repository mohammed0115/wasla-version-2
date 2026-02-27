from __future__ import annotations

from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from apps.tenants.models import Tenant, TenantMembership
from apps.tenants.services.provisioning import provision_store_after_payment

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
            owner = None
            profile = getattr(tenant, "store_profile", None)
            if profile is not None:
                owner = getattr(profile, "owner", None)
            if owner is None:
                owner_membership = (
                    TenantMembership.objects.select_related("user")
                    .filter(
                        tenant=tenant,
                        role=TenantMembership.ROLE_OWNER,
                        is_active=True,
                    )
                    .order_by("id")
                    .first()
                )
                if owner_membership:
                    owner = owner_membership.user

            if owner is None:
                raise ValueError("Cannot approve payment: tenant owner not found.")

            store = provision_store_after_payment(merchant=owner, plan=plan, payment=tx)
            subscription = StoreSubscription.objects.filter(store_id=store.tenant_id).order_by("-created_at").first()
            if subscription and tx.subscription_id != subscription.id:
                tx.subscription = subscription
                tx.save(update_fields=["subscription"])

        return tx
