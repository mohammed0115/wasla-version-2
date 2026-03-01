
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
import datetime
from django.views.decorators.http import require_http_methods

from apps.stores.models import Plan
from apps.tenants.models import Tenant, TenantMembership, StoreProfile
from apps.tenants.application.use_cases.store_setup_wizard import StoreSetupWizardUseCase
from apps.tenants.services.provisioning import provision_store_after_payment
from apps.subscriptions.models import SubscriptionPlan, StoreSubscription
from apps.catalog.services.category_service import ensure_global_categories, get_global_categories


def _infer_country_from_request(request) -> str:
    country = (getattr(request.user.profile, "country", "") or "").upper().strip()
    if country in {"SA", "AE", "EG", "KW", "QA", "BH", "OM", "JO", "LB", "MA"}:
        return country

    language = (getattr(request, "LANGUAGE_CODE", "") or "").lower()
    accept_language = (request.META.get("HTTP_ACCEPT_LANGUAGE") or "").lower()
    if "ar-sa" in accept_language:
        return "SA"
    if "ar-eg" in accept_language:
        return "EG"
    if language.startswith("ar"):
        return "SA"
    return "US"


def _infer_device_from_request(request) -> str:
    user_agent = (request.META.get("HTTP_USER_AGENT") or "").lower()
    mobile_hints = ["mobile", "android", "iphone", "ipad", "ipod"]
    return "mobile" if any(hint in user_agent for hint in mobile_hints) else "desktop"

# ---------
# Helpers
# ---------
def ensure_default_subscription_plans() -> list[SubscriptionPlan]:
    """Create default subscription plans only if table is empty."""
    if SubscriptionPlan.objects.exists():
        return list(
            SubscriptionPlan.objects.filter(is_active=True).order_by("price", "name", "billing_cycle")
        )

    defaults = [
        {
            "name": "Basic",
            "price": 0,
            "billing_cycle": "monthly",
            "features": [],
            "is_active": True,
        },
        {
            "name": "Plus",
            "price": 99,
            "billing_cycle": "monthly",
            "features": ["custom_domain", "tap", "stripe"],
            "is_active": True,
        },
        {
            "name": "Pro",
            "price": 299,
            "billing_cycle": "monthly",
            "features": ["custom_domain", "ai_tools", "ai_visual_search", "tap", "stripe", "stc_pay"],
            "is_active": True,
        },
    ]
    SubscriptionPlan.objects.bulk_create([SubscriptionPlan(**row) for row in defaults])
    return list(
        SubscriptionPlan.objects.filter(is_active=True).order_by("price", "name", "billing_cycle")
    )


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
    plans = ensure_default_subscription_plans()
    if not plans:
        plans = list(
            SubscriptionPlan.objects.filter(is_active=True).order_by("price", "name", "billing_cycle")
        )

    if request.method == "POST":
        plan_id = (request.POST.get("plan_id") or "").strip()
        chosen = SubscriptionPlan.objects.filter(id=plan_id, is_active=True).first()
        if not chosen:
            chosen = (
                SubscriptionPlan.objects.filter(is_active=True)
                .order_by("price", "id")
                .first()
            )
        if not chosen:
            return redirect("accounts:persona_plans")

        with transaction.atomic():
            # save on profile (best-effort mapping to legacy Plan)
            base_name = (chosen.name or "").split("(")[0].strip()
            legacy_plan = Plan.objects.filter(name__iexact=base_name).first()
            if legacy_plan:
                request.user.profile.plan = legacy_plan
            request.user.profile.persona_completed = True
            request.user.profile.save(update_fields=["plan", "persona_completed"])

            # ensure tenant + membership
            tenant = ensure_tenant_for_user(request.user)
            request.session["store_id"] = tenant.id
            request.session.modified = True
            request.tenant = tenant

            # subscription (MVP)
            is_free = float(getattr(chosen, "price", 0) or 0) <= 0
            StoreSubscription.objects.update_or_create(
                store_id=tenant.id,
                defaults={
                    "plan": chosen,
                    "status": "active" if is_free else "pending",
                    "start_date": timezone.now().date(),
                    "end_date": (
                        timezone.now().date()
                        + datetime.timedelta(days=30 if chosen.billing_cycle == "monthly" else 365)
                    ),
                },
            )

            request.session["persona_billing_cycle"] = chosen.billing_cycle
            request.session["persona_plan_id"] = chosen.id

        if is_free:
            provision_store_after_payment(merchant=request.user, plan=chosen)
            return redirect("tenants:dashboard_home")

        # Option C flow: do not auto-activate subscriptions or stores.
        # Merchant must submit/complete manual payment then wait for admin approval.
        return redirect("tenants:billing_payment_required")

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

    categories = get_global_categories()
    if not categories:
        categories = ensure_global_categories()
    choices = [category.name for category in categories]

    if request.method == "POST":
        selected = (request.POST.get("business_category") or "").strip()
        if selected not in choices:
            selected = choices[0] if choices else ""

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


@login_required
@require_http_methods(["GET"])
def ai_onboarding_wizard(request):
    profile = request.user.profile
    registration_time = timezone.localtime(getattr(profile, "created_at", timezone.now()))
    market = _infer_country_from_request(request)
    language = (getattr(request, "LANGUAGE_CODE", "ar") or "ar").lower()
    device = _infer_device_from_request(request)
    business = (
        request.session.get("persona_business_category")
        or getattr(profile, "category_sub", "")
        or getattr(profile, "category_main", "")
        or "ملابس"
    )

    onboarding_seed = {
        "registration": {
            "fullName": request.user.get_full_name() or request.user.username,
            "email": request.user.email,
            "phoneCountry": getattr(profile, "phone_country", "+966"),
            "phoneNumber": getattr(profile, "phone_number", ""),
            "market": market,
            "language": language,
            "registrationTime": registration_time.strftime("%Y-%m-%d %H:%M"),
            "device": device,
        },
        "business": business,
    }

    return render(
        request,
        "accounts/ai_onboarding_wizard.html",
        {
            "onboarding_seed": onboarding_seed,
            "registration_time_display": registration_time.strftime("%Y-%m-%d %H:%M"),
        },
    )


@login_required
@require_http_methods(["GET"])
def ai_onboarding_suggestions(request):
    business = (request.GET.get("business") or "").strip() or "ملابس"

    suggestions_by_business = {
        "ملابس": [
            "ابدأ بإضافة 10 منتجات أساسية مع المقاسات الأكثر طلبًا.",
            "فعّل المتغيرات (S/M/L/XL) قبل رفع أول دفعة منتجات.",
            "استخدم وصفًا عربيًا قصيرًا + نقاط مميزات لتحسين التحويل.",
        ],
        "إلكترونيات": [
            "أضف المواصفات الفنية كحقول ثابتة لكل منتج.",
            "فعّل الشحن المتقدم وتتبع الطلبات من أول يوم.",
            "أظهر سياسة الضمان في وصف المنتج بشكل واضح.",
        ],
        "تجميل": [
            "أنشئ تصنيفات بحسب نوع البشرة والاستخدام.",
            "استخدم صورًا متناسقة المقاس لخلاصة منتجات أوضح.",
            "ابدأ بحملة عرض ترحيبي لأول طلب لتحفيز التحويل.",
        ],
        "أثاث": [
            "أضف الأبعاد والوزن في كل منتج قبل النشر.",
            "فعّل مناطق الشحن حسب المدن لتسعير أدق.",
            "استخدم صورًا متعددة لكل منتج (واجهة/تفاصيل/قياس).",
        ],
        "أغذية": [
            "نظّم المنتجات حسب النوع وتاريخ الصلاحية.",
            "ابدأ بخيارات توصيل سريعة للمدن الأساسية.",
            "أضف عبوات متعددة السعر لرفع متوسط السلة.",
        ],
        "خدمات": [
            "حوّل كل خدمة إلى باقة واضحة السعر والمدة.",
            "أضف أسئلة متكررة لشرح خطوات تنفيذ الخدمة.",
            "فعّل نماذج الطلب السريعة مع حقول مختصرة.",
        ],
    }

    default_suggestions = [
        "ابدأ بالمنتجات الأعلى طلبًا في نشاطك.",
        "حافظ على صور موحدة ووصف واضح لكل منتج.",
        "تابع أول 20 طلبًا واضبط الشحن بناءً على النتائج.",
    ]

    return JsonResponse(
        {
            "business": business,
            "suggestions": suggestions_by_business.get(business, default_suggestions),
        }
    )
