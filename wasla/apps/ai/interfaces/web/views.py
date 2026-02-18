from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.ai.application.use_cases.apply_category import ApplyCategoryCommand, ApplyCategoryUseCase
from apps.ai.application.use_cases.categorize_product import (
    CategorizeProductCommand,
    CategorizeProductUseCase,
)
from apps.ai.application.use_cases.generate_description import (
    GenerateProductDescriptionCommand,
    GenerateProductDescriptionUseCase,
)
from apps.ai.application.use_cases.save_description import (
    SaveProductDescriptionCommand,
    SaveProductDescriptionUseCase,
)
from apps.ai.application.use_cases.visual_search import VisualSearchCommand, VisualSearchUseCase
from apps.catalog.models import Product
from apps.subscriptions.application.services.feature_gate import FeatureGateService
from apps.tenants.domain.tenant_context import TenantContext
from apps.tenants.interfaces.web.decorators import tenant_access_required


AI_WEB_RATE_LIMIT = 10
AI_WEB_RATE_PERIOD_SECONDS = 60


def _build_tenant_context(request: HttpRequest) -> TenantContext:
    tenant = getattr(request, "tenant", None)
    tenant_id = getattr(tenant, "id", None)
    currency = getattr(tenant, "currency", "SAR")
    if not tenant_id:
        raise ValueError("Tenant context is required.")
    if not request.session.session_key:
        request.session.save()
    session_key = request.session.session_key
    user_id = request.user.id if request.user.is_authenticated else None
    return TenantContext(tenant_id=tenant_id, currency=currency, user_id=user_id, session_key=session_key)


def _allow_ai_request(store_id: int, feature: str) -> bool:
    key = f"ai:rl:{store_id}:{feature}"
    count = cache.get(key)
    if count is None:
        cache.set(key, 1, timeout=AI_WEB_RATE_PERIOD_SECONDS)
        return True
    if count >= AI_WEB_RATE_LIMIT:
        return False
    cache.set(key, count + 1, timeout=AI_WEB_RATE_PERIOD_SECONDS)
    return True


def _render_upgrade_required(request: HttpRequest, feature_name: str) -> HttpResponse:
    return render(
        request,
        "dashboard/upgrade_required.html",
        {
            "feature_name": feature_name,
            "tenant": getattr(request, "tenant", None),
        },
        status=403,
    )


def _require_feature_or_upgrade(request: HttpRequest, tenant_id: int, feature_key: str, label: str) -> HttpResponse | None:
    if FeatureGateService.can_use_feature(tenant_id, feature_key):
        return None
    messages.error(request, _("Your current subscription does not include this feature."))
    return _render_upgrade_required(request, label)


@login_required
@tenant_access_required
@require_GET
def ai_tools(request: HttpRequest) -> HttpResponse:
    tenant_ctx = _build_tenant_context(request)
    gate_response = _require_feature_or_upgrade(
        request,
        tenant_ctx.tenant_id,
        FeatureGateService.AI_TOOLS,
        _("AI tools"),
    )
    if gate_response is not None:
        return gate_response

    products = Product.objects.filter(store_id=tenant_ctx.tenant_id).order_by("-id")[:50]
    return render(request, "dashboard/ai/tools.html", {"products": products, "tenant": getattr(request, "tenant", None)})


@login_required
@tenant_access_required
@require_POST
def ai_generate_description(request: HttpRequest, product_id: int) -> HttpResponse:
    tenant_ctx = _build_tenant_context(request)
    gate_response = _require_feature_or_upgrade(
        request,
        tenant_ctx.tenant_id,
        FeatureGateService.AI_TOOLS,
        _("AI tools"),
    )
    if gate_response is not None:
        return gate_response

    if not _allow_ai_request(tenant_ctx.tenant_id, "description"):
        messages.error(request, _("AI rate limit exceeded. Please try again shortly."))
        return redirect("ai_web:dashboard_ai_tools")

    action = (request.POST.get("action") or "generate").strip().lower()
    language = (request.POST.get("language") or "ar").strip().lower() or "ar"
    product = Product.objects.filter(id=product_id, store_id=tenant_ctx.tenant_id).first()
    if not product:
        messages.error(request, _("Product not found."))
        return redirect("ai_web:dashboard_ai_tools")

    if action == "save":
        description = request.POST.get("description") or ""
        force = (request.POST.get("force") or "").strip() in ("1", "true", "yes", "on")
        result = SaveProductDescriptionUseCase.execute(
            SaveProductDescriptionCommand(
                tenant_ctx=tenant_ctx,
                actor_id=request.user.id if request.user.is_authenticated else None,
                product_id=product_id,
                language=language,
                description=description,
                force=force,
            )
        )
        if not result.product:
            messages.error(request, _("Product not found."))
        elif not result.saved:
            messages.warning(request, _("Existing description found. Enable overwrite to replace it."))
        else:
            messages.success(request, _("Description saved."))
        return redirect("ai_web:dashboard_ai_tools")

    result = GenerateProductDescriptionUseCase.execute(
        GenerateProductDescriptionCommand(
            tenant_ctx=tenant_ctx,
            actor_id=request.user.id if request.user.is_authenticated else None,
            product_id=product_id,
            language=language,
        )
    )
    if result.fallback_reason == "content_blocked":
        messages.error(request, _("Content blocked by safety rules."))
        return redirect("ai_web:dashboard_ai_tools")

    existing_description = product.description_en if language == "en" else product.description_ar
    return render(
        request,
        "dashboard/ai/description_preview.html",
        {
            "product": product,
            "result": result,
            "language": language,
            "has_existing_description": bool(existing_description),
        },
    )


@login_required
@tenant_access_required
@require_POST
def ai_categorize_product(request: HttpRequest, product_id: int) -> HttpResponse:
    tenant_ctx = _build_tenant_context(request)
    gate_response = _require_feature_or_upgrade(
        request,
        tenant_ctx.tenant_id,
        FeatureGateService.AI_TOOLS,
        _("AI tools"),
    )
    if gate_response is not None:
        return gate_response

    if not _allow_ai_request(tenant_ctx.tenant_id, "category"):
        messages.error(request, _("AI rate limit exceeded. Please try again shortly."))
        return redirect("ai_web:dashboard_ai_tools")

    action = (request.POST.get("action") or "suggest").strip().lower()
    product = Product.objects.filter(id=product_id, store_id=tenant_ctx.tenant_id).first()
    if not product:
        messages.error(request, _("Product not found."))
        return redirect("ai_web:dashboard_ai_tools")

    if action == "apply":
        category_id = int(request.POST.get("category_id") or 0)
        ok = ApplyCategoryUseCase.execute(
            ApplyCategoryCommand(
                tenant_ctx=tenant_ctx,
                actor_id=request.user.id if request.user.is_authenticated else None,
                product_id=product_id,
                category_id=category_id,
            )
        )
        if ok:
            messages.success(request, _("Category applied."))
        else:
            messages.error(request, _("Unable to apply category."))
        return redirect("ai_web:dashboard_ai_tools")

    result = CategorizeProductUseCase.execute(
        CategorizeProductCommand(
            tenant_ctx=tenant_ctx,
            actor_id=request.user.id if request.user.is_authenticated else None,
            product_id=product_id,
        )
    )
    if result.fallback_reason == "no_categories":
        messages.warning(request, _("No categories available yet."))
        return redirect("ai_web:dashboard_ai_tools")
    if result.fallback_reason == "content_blocked":
        messages.error(request, _("Content blocked by safety rules."))
        return redirect("ai_web:dashboard_ai_tools")

    products = Product.objects.filter(store_id=tenant_ctx.tenant_id).order_by("-id")[:50]
    return render(
        request,
        "dashboard/ai/tools.html",
        {
            "products": products,
            "selected_product": product,
            "category_result": result,
        },
    )


@login_required
@tenant_access_required
@require_http_methods(["GET", "POST"])
def ai_visual_search(request: HttpRequest) -> HttpResponse:
    tenant_ctx = _build_tenant_context(request)
    gate_response = _require_feature_or_upgrade(
        request,
        tenant_ctx.tenant_id,
        FeatureGateService.AI_VISUAL_SEARCH,
        _("AI visual search"),
    )
    if gate_response is not None:
        return gate_response

    if request.method == "POST":
        if not _allow_ai_request(tenant_ctx.tenant_id, "search"):
            messages.error(request, _("AI rate limit exceeded. Please try again shortly."))
            return redirect("ai_web:dashboard_ai_tools")

        image_file = request.FILES.get("image")
        result = VisualSearchUseCase.execute(
            VisualSearchCommand(
                tenant_ctx=tenant_ctx,
                image_file=image_file,
                top_n=5,
            )
        )
        return render(request, "dashboard/ai/visual_search.html", {"result": result, "tenant": getattr(request, "tenant", None)})

    return render(request, "dashboard/ai/visual_search.html", {"result": None, "tenant": getattr(request, "tenant", None)})
