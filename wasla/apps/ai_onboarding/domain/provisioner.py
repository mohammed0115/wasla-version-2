from __future__ import annotations

import datetime
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils.text import slugify
from django.utils import timezone

from apps.ai_onboarding.models import (
    OnboardingDecision,
    OnboardingProfile,
    ProvisioningActionLog,
    ProvisioningRequest,
)
from apps.catalog.models import Category
from apps.stores.models import Plan, Store, StoreSettings
from apps.subscriptions.models import StoreSubscription
from apps.tenants.application.use_cases.create_store import CreateStoreCommand, CreateStoreUseCase
from apps.tenants.models import StoreProfile, StoreShippingSettings
from apps.themes.models import StoreBranding


@dataclass(frozen=True)
class ProvisionResultDTO:
    store_id: int
    next_url: str


class ProvisioningEngine:
    @transaction.atomic
    def provision(self, profile_id: int, idempotency_key: str, actor_user) -> ProvisionResultDTO:
        profile = (
            OnboardingProfile.objects.select_related("store", "user")
            .select_for_update()
            .get(id=profile_id)
        )

        if profile.user_id != getattr(actor_user, "id", None):
            raise PermissionError("Cross-tenant/profile provisioning access denied.")

        if not idempotency_key or len(idempotency_key.strip()) < 8:
            raise ValueError("idempotency_key is required (min 8 chars).")
        normalized_key = idempotency_key.strip()

        try:
            req, created = ProvisioningRequest.objects.get_or_create(
                profile=profile,
                idempotency_key=normalized_key,
                defaults={"status": "pending"},
            )
        except IntegrityError:
            req = ProvisioningRequest.objects.get(profile=profile, idempotency_key=normalized_key)
            created = False

        if not created and req.status == "success" and req.store_id:
            return ProvisionResultDTO(store_id=req.store_id, next_url=reverse("tenants:dashboard_home"))

        decision = OnboardingDecision.objects.select_related("recommended_plan").get(profile=profile)

        store = profile.store
        if not store:
            store = self._run_action(
                profile=profile,
                idempotency_key=normalized_key,
                action="create_store",
                payload={"business_type": profile.business_type},
                handler=lambda: self._create_store_for_profile(profile, actor_user),
            )
            profile.store = store
            profile.save(update_fields=["store"])

        self._run_action(
            profile=profile,
            idempotency_key=normalized_key,
            action="assign_plan",
            payload={"recommended_plan_code": decision.recommended_plan_code},
            handler=lambda: self._assign_plan(store=store, decision=decision),
        )

        self._run_action(
            profile=profile,
            idempotency_key=normalized_key,
            action="apply_theme",
            payload={"recommended_theme": decision.recommended_theme},
            handler=lambda: self._apply_theme(store=store, decision=decision),
        )

        self._run_action(
            profile=profile,
            idempotency_key=normalized_key,
            action="create_categories",
            payload={"categories": decision.recommended_categories},
            handler=lambda: self._create_categories(store=store, categories=decision.recommended_categories),
        )

        self._run_action(
            profile=profile,
            idempotency_key=normalized_key,
            action="enable_variants",
            payload={"needs_variants": decision.needs_variants},
            handler=lambda: self._enable_variants(store=store, decision=decision),
        )

        self._run_action(
            profile=profile,
            idempotency_key=normalized_key,
            action="configure_shipping",
            payload={"shipping_profile": decision.shipping_profile},
            handler=lambda: self._configure_shipping(store=store, shipping_profile=decision.shipping_profile),
        )

        self._run_action(
            profile=profile,
            idempotency_key=normalized_key,
            action="dashboard_tips",
            payload={"business_type": profile.business_type},
            handler=lambda: self._write_dashboard_tips(store=store, decision=decision),
        )

        req.store = store
        req.status = "success"
        req.error = ""
        req.save(update_fields=["store", "status", "error", "updated_at"])

        tenant = store.tenant
        if tenant:
            StoreProfile.objects.update_or_create(
                tenant=tenant,
                owner=actor_user,
                defaults={"store_info_completed": True, "setup_step": 4, "is_setup_complete": True},
            )
            tenant.setup_completed = True
            tenant.setup_step = 4
            tenant.setup_completed_at = timezone.now()
            tenant.save(update_fields=["setup_completed", "setup_step", "setup_completed_at", "updated_at"])

        return ProvisionResultDTO(store_id=store.id, next_url=reverse("tenants:dashboard_home"))

    @staticmethod
    def _run_action(*, profile: OnboardingProfile, idempotency_key: str, action: str, payload: dict, handler):
        if profile.store_id and ProvisioningActionLog.objects.filter(
            store_id=profile.store_id,
            profile=profile,
            idempotency_key=idempotency_key,
            action=action,
            status=ProvisioningActionLog.STATUS_SUCCESS,
        ).exists():
            return profile.store

        try:
            result = handler()
            store_for_log = result if isinstance(result, Store) else profile.store
            if store_for_log:
                ProvisioningActionLog.objects.create(
                    store=store_for_log,
                    profile=profile,
                    idempotency_key=idempotency_key,
                    action=action,
                    payload=payload,
                    status=ProvisioningActionLog.STATUS_SUCCESS,
                )
            return result
        except Exception as exc:
            if profile.store_id:
                ProvisioningActionLog.objects.create(
                    store_id=profile.store_id,
                    profile=profile,
                    idempotency_key=idempotency_key,
                    action=action,
                    payload=payload,
                    status=ProvisioningActionLog.STATUS_FAILED,
                    error=str(exc),
                )
            raise

    @staticmethod
    def _create_store_for_profile(profile: OnboardingProfile, actor_user) -> Store:
        desired_name = f"{actor_user.first_name or actor_user.username} Store".strip()
        desired_slug = slugify(f"{actor_user.username}-{profile.business_type}")[:40] or slugify(actor_user.username) or "store"

        result = CreateStoreUseCase.execute(
            CreateStoreCommand(
                user=actor_user,
                name=desired_name,
                slug=desired_slug,
                currency="SAR",
                language=profile.language or "ar",
            )
        )

        existing_store = Store.objects.filter(tenant=result.tenant).order_by("id").first()
        if existing_store:
            return existing_store

        return Store.objects.create(
            owner=actor_user,
            tenant=result.tenant,
            name=desired_name,
            slug=result.tenant.slug,
            subdomain=result.tenant.slug,
            status=Store.STATUS_ACTIVE,
            category=profile.business_type,
            country=profile.country,
        )

    @staticmethod
    def _assign_plan(*, store: Store, decision: OnboardingDecision) -> None:
        if not store.tenant_id:
            return
        if decision.recommended_plan_id:
            cycle_days = 365 if decision.recommended_plan.billing_cycle == "yearly" else 30
            now_date = timezone.now().date()
            StoreSubscription.objects.update_or_create(
                store_id=store.tenant_id,
                defaults={
                    "plan": decision.recommended_plan,
                    "status": "active",
                    "start_date": now_date,
                    "end_date": now_date + datetime.timedelta(days=cycle_days),
                },
            )

        legacy_map = {"BASIC": "Basic", "PRO": "Pro", "ADVANCED": "Advanced"}
        legacy_name = legacy_map.get(decision.recommended_plan_code, "Basic")
        legacy_plan = Plan.objects.filter(name__iexact=legacy_name).first() or Plan.objects.order_by("price_monthly").first()
        if legacy_plan and store.plan_id != legacy_plan.id:
            store.plan = legacy_plan
            store.save(update_fields=["plan", "updated_at"])

    @staticmethod
    def _apply_theme(*, store: Store, decision: OnboardingDecision) -> None:
        if store.theme_name != decision.recommended_theme:
            store.theme_name = decision.recommended_theme
            store.save(update_fields=["theme_name", "updated_at"])
        StoreBranding.objects.update_or_create(
            store_id=store.id,
            defaults={"theme_code": decision.recommended_theme},
        )

    @staticmethod
    def _create_categories(*, store: Store, categories: list[str]) -> None:
        if not store.tenant_id:
            return
        for name in categories:
            normalized = (name or "").strip()
            if normalized:
                Category.objects.get_or_create(store_id=store.tenant_id, name=normalized)

    @staticmethod
    def _enable_variants(*, store: Store, decision: OnboardingDecision) -> None:
        settings_obj, _ = StoreSettings.objects.get_or_create(store=store)
        metadata = dict(settings_obj.metadata_json or {})
        metadata["variants_enabled"] = bool(decision.needs_variants)
        metadata.setdefault("features", [])
        if decision.needs_variants and "variants" not in metadata["features"]:
            metadata["features"].append("variants")
        settings_obj.metadata_json = metadata
        settings_obj.save(update_fields=["metadata_json", "updated_at"])

    @staticmethod
    def _configure_shipping(*, store: Store, shipping_profile: dict) -> None:
        if not store.tenant_id:
            return
        mode = shipping_profile.get("mode", "standard")
        if mode == "express":
            fulfillment = StoreShippingSettings.MODE_MANUAL_DELIVERY
            flat_fee = 22
            threshold = 199
        elif mode == "insured":
            fulfillment = StoreShippingSettings.MODE_CARRIER
            flat_fee = 25
            threshold = 399
        elif mode == "none":
            fulfillment = StoreShippingSettings.MODE_PICKUP
            flat_fee = 0
            threshold = None
         else:
            fulfillment = StoreShippingSettings.MODE_MANUAL_DELIVERY
            flat_fee = 18
            threshold = 299
 
         StoreShippingSettings.objects.update_or_create(
             tenant_id=store.tenant_id,
             defaults={
                 "fulfillment_mode": fulfillment,
                 "origin_city": "Riyadh",
                 "delivery_fee_flat": flat_fee,
                 "free_shipping_threshold": threshold,
                 "is_enabled": True,
             },
         )

    @staticmethod
    def _write_dashboard_tips(*, store: Store, decision: OnboardingDecision) -> None:
        settings_obj, _ = StoreSettings.objects.get_or_create(store=store)
        metadata = dict(settings_obj.metadata_json or {})
        metadata["dashboard_tips"] = [
            "أضف أول 10 منتجات لتحسين العرض تلقائيًا",
            "فعّل صور عالية الجودة لزيادة التحويل",
            f"الخطة الحالية المقترحة: {decision.recommended_plan_code}",
        ]
        settings_obj.metadata_json = metadata
        settings_obj.save(update_fields=["metadata_json", "updated_at"])
