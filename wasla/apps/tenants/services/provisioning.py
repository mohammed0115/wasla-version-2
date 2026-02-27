from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.stores.models import Store, StoreSettings, StoreSetupStep
from apps.subscriptions.models import PaymentTransaction, StoreSubscription, SubscriptionPlan
from apps.tenants.models import StoreProfile, Tenant, TenantMembership
from apps.tenants.services.audit_service import TenantAuditService


def merchant_has_active_store(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return Store.objects.filter(
        owner=user,
        tenant__is_active=True,
        tenant__is_published=True,
        status=Store.STATUS_ACTIVE,
    ).exists()


def _resolve_default_plan() -> SubscriptionPlan | None:
    plan_qs = SubscriptionPlan.objects.filter(is_active=True)
    field_names = {field.name for field in SubscriptionPlan._meta.get_fields()}
    if "is_default" in field_names:
        default_plan = plan_qs.filter(is_default=True).order_by("price", "id").first()
        if default_plan:
            return default_plan
    return plan_qs.order_by("price", "id").first()


def _resolve_merchant_tenant(merchant, payment: PaymentTransaction | None = None) -> Tenant | None:
    if payment and payment.tenant_id:
        return payment.tenant

    profile = StoreProfile.objects.select_related("tenant").filter(owner=merchant).order_by("tenant_id").first()
    if profile:
        return profile.tenant

    membership = (
        TenantMembership.objects.select_related("tenant")
        .filter(
            user=merchant,
            role=TenantMembership.ROLE_OWNER,
            is_active=True,
            tenant__is_active=True,
        )
        .order_by("tenant_id")
        .first()
    )
    if membership:
        return membership.tenant
    return None


def _build_unique_store_slug(base_value: str) -> str:
    base_slug = slugify(base_value or "store")[:45] or "store"
    candidate = base_slug
    suffix = 1
    while Store.objects.filter(slug=candidate).exists() or Store.objects.filter(subdomain=candidate).exists():
        suffix += 1
        candidate = f"{base_slug[:40]}-{suffix}"
    return candidate


@transaction.atomic
def provision_store_after_payment(merchant, plan=None, payment=None) -> Store:
    UserModel = get_user_model()
    if not isinstance(merchant, UserModel):
        raise ValueError("Merchant user is required for provisioning.")

    tenant = _resolve_merchant_tenant(merchant=merchant, payment=payment)
    if not tenant:
        base_slug = _build_unique_store_slug(getattr(merchant, "username", "store"))
        tenant = Tenant.objects.create(
            slug=base_slug,
            subdomain=base_slug,
            name=(merchant.get_full_name() or merchant.username or base_slug).strip()[:200] or base_slug,
            is_active=True,
            is_published=False,
            setup_step=4,
            setup_completed=True,
            setup_completed_at=timezone.now(),
        )
        TenantMembership.objects.get_or_create(
            tenant=tenant,
            user=merchant,
            defaults={"role": TenantMembership.ROLE_OWNER, "is_active": True},
        )
        StoreProfile.objects.get_or_create(
            tenant=tenant,
            defaults={
                "owner": merchant,
                "store_info_completed": True,
                "setup_step": 4,
                "is_setup_complete": True,
            },
        )

    selected_plan = plan or (getattr(payment, "plan", None) if payment else None) or _resolve_default_plan()
    if selected_plan is None:
        raise ValueError("No active subscription plan found for provisioning.")

    store = Store.objects.filter(tenant_id=tenant.id).order_by("id").first()
    if not store:
        store = Store.objects.filter(owner=merchant, tenant__isnull=True).order_by("id").first()

    slug_source = tenant.slug or tenant.subdomain or getattr(merchant, "username", "store")
    target_slug = _build_unique_store_slug(slug_source)

    if store:
        updates = []
        if store.tenant_id != tenant.id:
            store.tenant = tenant
            updates.append("tenant")
        if not store.slug:
            store.slug = target_slug
            updates.append("slug")
        if not store.subdomain:
            store.subdomain = store.slug or target_slug
            updates.append("subdomain")
        if store.status != Store.STATUS_ACTIVE:
            store.status = Store.STATUS_ACTIVE
            updates.append("status")
        if updates:
            store.save(update_fields=updates)
    else:
        store = Store.objects.create(
            owner=merchant,
            tenant=tenant,
            name=(tenant.name or merchant.username or target_slug).strip()[:255] or target_slug,
            slug=target_slug,
            subdomain=target_slug,
            status=Store.STATUS_ACTIVE,
        )

    StoreSettings.objects.get_or_create(store=store)
    StoreSetupStep.objects.get_or_create(store=store)

    tenant_updates = []
    if not tenant.is_active:
        tenant.is_active = True
        tenant_updates.append("is_active")
    if not tenant.is_published:
        tenant.is_published = True
        tenant_updates.append("is_published")
    if tenant.setup_step != 4:
        tenant.setup_step = 4
        tenant_updates.append("setup_step")
    if not tenant.setup_completed:
        tenant.setup_completed = True
        tenant_updates.append("setup_completed")
    if not tenant.setup_completed_at:
        tenant.setup_completed_at = timezone.now()
        tenant_updates.append("setup_completed_at")
    if not tenant.subdomain:
        tenant.subdomain = store.subdomain
        tenant_updates.append("subdomain")
    if tenant_updates:
        tenant.save(update_fields=tenant_updates + ["updated_at"])

    start_date = timezone.now().date()
    end_date = start_date + timedelta(days=365 if selected_plan.billing_cycle == "yearly" else 30)
    subscription, _ = StoreSubscription.objects.update_or_create(
        store_id=tenant.id,
        defaults={
            "plan": selected_plan,
            "status": "active",
            "start_date": start_date,
            "end_date": end_date,
        },
    )

    if payment is not None:
        payment.subscription = subscription
        update_fields = ["subscription"]
        if payment.status != PaymentTransaction.STATUS_PAID:
            payment.status = PaymentTransaction.STATUS_PAID
            update_fields.append("status")
        if payment.paid_at is None:
            payment.paid_at = timezone.now()
            update_fields.append("paid_at")
        payment.save(update_fields=update_fields)

    TenantAuditService.record_action(
        tenant,
        "payment_approved_store_provisioned",
        actor=getattr(merchant, "username", "system"),
        details="Store provisioned after payment approval.",
        metadata={
            "store_id": store.id,
            "plan_id": selected_plan.id,
            "payment_id": getattr(payment, "id", None),
        },
    )

    return store