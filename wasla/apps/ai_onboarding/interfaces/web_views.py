from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from apps.ai_onboarding.domain.analyzer import AnalyzeInput, BusinessAnalyzer
from apps.ai_onboarding.domain.provisioner import ProvisioningEngine


@login_required
@require_POST
def wizard_analyze_step(request):
    business_type = (request.POST.get("business_type") or "general").strip()
    expected_products = request.POST.get("expected_products") or None
    expected_orders_per_day = request.POST.get("expected_orders_per_day") or None

    analyzer = BusinessAnalyzer()
    decision = analyzer.analyze(
        AnalyzeInput(
            user=request.user,
            country=(request.POST.get("country") or "SA").strip(),
            language=(request.POST.get("language") or "ar").strip(),
            device_type=(request.POST.get("device_type") or "web").strip(),
            business_type=business_type,
            expected_products=int(expected_products) if expected_products else None,
            expected_orders_per_day=int(expected_orders_per_day) if expected_orders_per_day else None,
        )
    )
    request.session["ai_onboarding_profile_id"] = decision.profile_id
    return redirect("accounts:ai_onboarding_wizard")


@login_required
@require_POST
def wizard_finish_provision(request):
    profile_id = int(request.POST.get("profile_id") or request.session.get("ai_onboarding_profile_id") or 0)
    idempotency_key = (request.POST.get("idempotency_key") or f"wizard-finish-{profile_id}").strip()
    result = ProvisioningEngine().provision(profile_id=profile_id, idempotency_key=idempotency_key, actor_user=request.user)
    return redirect(result.next_url)
