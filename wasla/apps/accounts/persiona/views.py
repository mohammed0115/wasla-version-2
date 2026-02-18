
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, redirect
from django.utils import timezone
import datetime
from django.views.decorators.http import require_http_methods

from apps.stores.models import Plan
from apps.tenants.models import Tenant, TenantMembership, StoreProfile
from apps.tenants.application.use_cases.store_setup_wizard import StoreSetupWizardUseCase
from apps.subscriptions.models import SubscriptionPlan, StoreSubscription

# ---------
# Helpers
# ---------
def ensure_default_plans() -> list[Plan]:
    """Create default plans (Salla-like) if DB is empty."""
    if Plan.objects.exists():
        return list(Plan.objects.all().order_by("price_monthly"))

    plans = [
        Plan(name="وصلة بيسك", price_monthly=0, price_yearly=0, is_free=True, is_popular=False),
        Plan(name="وصلة بلس", price_monthly=99, price_yearly=99*12*0.84, is_free=False, is_popular=True),
        Plan(name="وصلة برو", price_monthly=299, price_yearly=299*12*0.84, is_free=False, is_popular=False),
    ]
    Plan.objects.bulk_create(plans)
    return list(Plan.objects.all().order_by("price_monthly"))


def ensure_subscription_plan(plan: Plan, billing_cycle: str) -> SubscriptionPlan:
    """Mirror Plan into subscriptions.SubscriptionPlan (MVP)."""
    name = f"{plan.name} ({billing_cycle})"
    price = plan.price_monthly if billing_cycle == "monthly" else plan.price_yearly
    sub_plan, _ = SubscriptionPlan.objects.get_or_create(
        name=name,
        defaults={
            "price": price,
            "billing_cycle": billing_cycle,
            "features": [],
            "is_active": True,
        },
    )
    return sub_plan


def ensure_tenant_for_user(user) -> Tenant:
    """Create tenant + owner membership if user has none."""
    existing = TenantMembership.objects.filter(user=user, is_active=True).select_related("tenant").first()
    if existing:
        return existing.tenant

    # slug from user (safe)
    base_slug = (user.username or user.email.split("@")[0] or "store").lower()
    base_slug = "".join([c for c in base_slug if c.isalnum() or c in "-_ "]).strip().replace(" ", "-")[:30] or "store"
    slug = base_slug
    i = 1
    while Tenant.objects.filter(slug=slug).exists():
        i += 1
        slug = f"{base_slug}-{i}"

    tenant = Tenant.objects.create(
        slug=slug,
        name=getattr(user, "first_name", "") or slug,
        subdomain=slug,
        domain="",
        setup_step=1,
        setup_completed=False,
        is_active=True,
        is_published=False,
    )
    TenantMembership.objects.create(tenant=tenant, user=user, role=TenantMembership.ROLE_OWNER, is_active=True)
    # Ensure StoreProfile exists for wizard/progress
    StoreProfile.objects.get_or_create(
        tenant=tenant,
        defaults={
            'owner': user,
            'store_info_completed': False,
            'setup_step': StoreSetupWizardUseCase.STEP_STORE_INFO,
            'is_setup_complete': False,
        },
    )
    return tenant


# -------------
# Views
# -------------
@login_required
@require_http_methods(["GET", "POST"])
def persona_plans(request):
    """
    Salla-like Plans:
    - choose billing cycle (monthly/yearly)
    - choose plan (basic/plus/pro)
    - persist into DB:
        * Profile.plan (stores.Plan)
        * Tenant + TenantMembership (owner)
        * StoreSubscription (subscriptions app) linked by store_id=tenant.id
    """
    plans = ensure_default_plans()

    if request.method == "POST":
        plan_id = (request.POST.get("plan_id") or "").strip()
        billing_cycle = (request.POST.get("billing_cycle") or "monthly").strip()
        if billing_cycle not in ("monthly", "yearly"):
            billing_cycle = "monthly"

        chosen = next((p for p in plans if str(p.id) == str(plan_id)), None)
        if not chosen:
            # Safer default for onboarding monetization flow: paid popular plan first.
            chosen = next((p for p in plans if p.is_popular and not p.is_free), None)
        if not chosen:
            chosen = next((p for p in plans if not p.is_free), None)
        if not chosen:
            chosen = plans[0]

        with transaction.atomic():
            # save on profile
            request.user.profile.plan = chosen
            request.user.profile.persona_completed = True
            request.user.profile.save(update_fields=["plan", "persona_completed"])

            # ensure tenant + membership
            tenant = ensure_tenant_for_user(request.user)

            # subscription (MVP)
            sub_plan = ensure_subscription_plan(chosen, billing_cycle)
            StoreSubscription.objects.update_or_create(
                store_id=tenant.id,
                defaults={
                    "plan": sub_plan,
                    "status": "active",
                    "start_date": timezone.now().date(),
                    "end_date": (timezone.now().date() + datetime.timedelta(days=30 if billing_cycle=="monthly" else 365)),
                },
            )

            request.session["persona_billing_cycle"] = billing_cycle
            request.session["persona_plan_id"] = chosen.id

        # Next step after choosing plan:
        # - Free plan: go مباشرة إلى لوحة التحكم
        # - Paid plan: go to payment setup first
        if chosen.is_free:
            return redirect("tenants:dashboard_home")
        return redirect("tenants:dashboard_setup_payment")

    # GET
    selected_plan_id = request.session.get("persona_plan_id")
    billing_cycle = request.session.get("persona_billing_cycle", "monthly")
    if billing_cycle not in ("monthly", "yearly"):
        billing_cycle = "monthly"

    
    compare_features = [
        {"name": "عدد لا محدود من المنتجات", "basic": True, "plus": True, "pro": True},
        {"name": "عدد لا محدود من العملاء", "basic": True, "plus": True, "pro": True},
        {"name": "كوبونات التخفيض", "basic": True, "plus": True, "pro": True},
        {"name": "شركات الشحن", "basic": True, "plus": True, "pro": True},
        {"name": "إضافة كل أنواع المنتجات", "basic": False, "plus": True, "pro": True},
        {"name": "حجز اسم دومين (رابط) مخصص", "basic": False, "plus": True, "pro": True},
        {"name": "تفعيل خدمات SEO", "basic": False, "plus": False, "pro": True},
        {"name": "الربط مع Google Tag Manager", "basic": False, "plus": False, "pro": True},
        {"name": "إضافة حسابات الموظفين", "basic": False, "plus": False, "pro": True},
    ]

    context = {
        "plans": plans,
        "selected_plan_id": selected_plan_id,
        "billing_cycle": billing_cycle,
    }
    return render(request, "plans.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def persona_business(request):
    """Business activity step (simple MVP).

    Stores the selected business category in session and (best-effort) in the
    user's profile (category_sub) to keep data without adding new DB fields.
    """

    choices = [
        "ملابس وإكسسوارات",
        "عطور وتجميل",
        "إلكترونيات",
        "مأكولات ومشروبات",
        "منتجات رقمية",
        "خدمات",
        "أخرى",
    ]

    if request.method == "POST":
        selected = (request.POST.get("business_category") or "").strip()
        if selected not in choices:
            selected = "أخرى" if selected else choices[0]

        request.session["persona_business_category"] = selected

        # Best-effort persistence without schema changes
        try:
            profile = request.user.profile
            if not getattr(profile, "category_sub", ""):
                profile.category_sub = selected
                profile.save(update_fields=["category_sub"])
        except Exception:
            pass

        return redirect("tenants:store_setup_start")

    selected = request.session.get("persona_business_category") or getattr(request.user.profile, "category_sub", "")
    if selected not in choices:
        selected = choices[0]

    return render(
        request,
        "persona_business.html",
        {
            "choices": choices,
            "selected": selected,
        },
    )
