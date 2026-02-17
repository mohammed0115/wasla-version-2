from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from accounts.application.usecases.resolve_onboarding_state import resolve_onboarding_state

from tenants.application.policies.ownership import EnsureTenantOwnershipPolicy
from tenants.application.use_cases.create_store import CreateStoreCommand, CreateStoreUseCase
from tenants.application.use_cases.activate_store import (
    ActivateStoreCommand,
    ActivateStoreUseCase,
    DeactivateStoreCommand,
    DeactivateStoreUseCase,
)
from tenants.application.use_cases.add_custom_domain import (
    AddCustomDomainCommand,
    AddCustomDomainUseCase,
)
from tenants.application.use_cases.disable_domain import (
    DisableDomainCommand,
    DisableDomainUseCase,
)
from tenants.application.use_cases.get_store_readiness import (
    GetStoreReadinessCommand,
    GetStoreReadinessUseCase,
)
from tenants.application.use_cases.get_setup_progress import (
    GetSetupProgressCommand,
    GetSetupProgressUseCase,
)
from tenants.application.use_cases.store_setup_wizard import StoreSetupWizardUseCase
from tenants.application.use_cases.update_payment_settings import (
    UpdatePaymentSettingsCommand,
    UpdatePaymentSettingsUseCase,
)
from tenants.application.use_cases.update_shipping_settings import (
    UpdateShippingSettingsCommand,
    UpdateShippingSettingsUseCase,
)
from tenants.application.use_cases.update_store_settings import (
    UpdateStoreSettingsCommand,
    UpdateStoreSettingsUseCase,
)
from tenants.application.dto.merchant_dashboard_metrics import GetMerchantDashboardMetricsQuery
from tenants.application.use_cases.get_merchant_dashboard_metrics import (
    GetMerchantDashboardMetricsUseCase,
)
from tenants.domain.errors import (
    StoreAccessDeniedError,
    StoreDomainError,
    StoreInactiveError,
    StoreNotReadyError,
    StoreSlugAlreadyTakenError,
)
from tenants.interfaces.web.decorators import resolve_tenant_for_request, tenant_access_required
from tenants.models import StoreDomain, StorePaymentSettings, StoreProfile, StoreShippingSettings
from tenants.tasks import enqueue_verify_domain
from tenants.domain.tenant_context import TenantContext

from .forms import (
    CustomDomainForm,
    PaymentSettingsForm,
    ShippingSettingsForm,
    StoreInfoSetupForm,
    StoreSettingsForm,
)


@login_required
@require_http_methods(["GET", "POST"])
def dashboard_setup_store(request: HttpRequest) -> HttpResponse:
    existing = resolve_tenant_for_request(request)
    existing_profile = None
    allow_existing_setup_form = False
    if existing:
        existing_profile = StoreProfile.objects.filter(tenant=existing).first()
        if existing_profile:
            state = StoreSetupWizardUseCase.get_state(profile=existing_profile)
            if (
                not existing_profile.is_setup_complete
                and state.current_step <= StoreSetupWizardUseCase.STEP_STORE_INFO
            ):
                allow_existing_setup_form = True
            if (
                not existing_profile.is_setup_complete
                and state.current_step == StoreSetupWizardUseCase.STEP_PAYMENT
            ):
                return redirect("tenants:dashboard_setup_payment")
            if (
                not existing_profile.is_setup_complete
                and state.current_step == StoreSetupWizardUseCase.STEP_SHIPPING
            ):
                return redirect("tenants:dashboard_setup_shipping")
            if (
                not existing_profile.is_setup_complete
                and state.current_step == StoreSetupWizardUseCase.STEP_FIRST_PRODUCT
            ):
                return redirect("tenants:dashboard_setup_activate")
        if not allow_existing_setup_form:
            return redirect("tenants:dashboard_home")

    # If the merchant has not finished the persona/onboarding flow, send them there.
    # (The onboarding flow lives in the accounts app in this codebase.)
    try:
        if hasattr(request.user, "profile") and not request.user.profile.persona_completed:
            return redirect("accounts:persona_welcome")
    except Exception:
        # If anything goes wrong, fail safe by letting the user proceed to store setup.
        pass

    initial = None
    if allow_existing_setup_form and existing is not None:
        initial = {
            "name": getattr(existing, "name", ""),
            "slug": getattr(existing, "slug", ""),
            "currency": getattr(existing, "currency", "SAR") or "SAR",
            "language": getattr(existing, "language", "ar") or "ar",
        }

    form = StoreInfoSetupForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        if allow_existing_setup_form and existing is not None:
            try:
                UpdateStoreSettingsUseCase.execute(
                    UpdateStoreSettingsCommand(
                        user=request.user,
                        tenant=existing,
                        name=form.cleaned_data["name"],
                        slug=form.cleaned_data["slug"],
                        currency=form.cleaned_data.get("currency") or "SAR",
                        language=form.cleaned_data.get("language") or "ar",
                        logo_file=None,
                        primary_color=getattr(existing, "primary_color", "") or "",
                        secondary_color=getattr(existing, "secondary_color", "") or "",
                    )
                )
            except StoreSlugAlreadyTakenError as exc:
                form.add_error("slug", str(exc))
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                if existing_profile:
                    StoreSetupWizardUseCase.mark_step_done(
                        user=request.user,
                        profile=existing_profile,
                        step=StoreSetupWizardUseCase.STEP_STORE_INFO,
                    )
                messages.success(request, "Store info saved.")
                return redirect("tenants:dashboard_setup_payment")

        try:
            result = CreateStoreUseCase.execute(
                CreateStoreCommand(
                    user=request.user,
                    name=form.cleaned_data["name"],
                    slug=form.cleaned_data["slug"],
                    currency=form.cleaned_data.get("currency") or "SAR",
                    language=form.cleaned_data.get("language") or "ar",
                )
            )
        except StoreSlugAlreadyTakenError as exc:
            form.add_error("slug", str(exc))
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            request.session["store_id"] = result.tenant.id
            request.tenant = result.tenant
            if result.created:
                messages.success(request, "Store created successfully.")
            else:
                messages.info(request, "You already have a store. Redirected to your dashboard.")
            profile = StoreProfile.objects.filter(tenant=result.tenant).first()
            if profile:
                state = StoreSetupWizardUseCase.get_state(profile=profile)
                if not profile.is_setup_complete and state.current_step == StoreSetupWizardUseCase.STEP_PAYMENT:
                    return redirect("tenants:dashboard_setup_payment")
                if not profile.is_setup_complete and state.current_step == StoreSetupWizardUseCase.STEP_SHIPPING:
                    return redirect("tenants:dashboard_setup_shipping")
                if (
                    not profile.is_setup_complete
                    and state.current_step == StoreSetupWizardUseCase.STEP_FIRST_PRODUCT
                ):
                    return redirect("tenants:dashboard_setup_activate")
            return redirect("tenants:dashboard_setup_payment")

    return render(request, "web/store/store_info_setup.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def store_create(request: HttpRequest) -> HttpResponse:
    return dashboard_setup_store(request)


@login_required
@tenant_access_required
@require_GET
def store_setup_start(request: HttpRequest) -> HttpResponse:
    tenant = request.tenant
    profile = StoreProfile.objects.filter(tenant=tenant).first()
    if not profile:
        return redirect("tenants:dashboard_setup_store")

    state = StoreSetupWizardUseCase.get_state(profile=profile)
    if not profile.is_setup_complete and state.current_step == StoreSetupWizardUseCase.STEP_STORE_INFO:
        return redirect("tenants:dashboard_setup_store")
    if not profile.is_setup_complete and state.current_step == StoreSetupWizardUseCase.STEP_PAYMENT:
        return redirect("tenants:dashboard_setup_payment")
    if not profile.is_setup_complete and state.current_step == StoreSetupWizardUseCase.STEP_SHIPPING:
        return redirect("tenants:dashboard_setup_shipping")
    if not profile.is_setup_complete and state.current_step == StoreSetupWizardUseCase.STEP_FIRST_PRODUCT:
        return redirect("tenants:dashboard_setup_activate")
    return redirect("tenants:dashboard_home")


@login_required
@tenant_access_required
@require_http_methods(["GET", "POST"])
def dashboard_setup_payment(request: HttpRequest) -> HttpResponse:
    tenant = request.tenant
    try:
        EnsureTenantOwnershipPolicy.ensure_is_owner(user=request.user, tenant=tenant)
    except StoreAccessDeniedError as exc:
        raise PermissionDenied(str(exc)) from exc

    profile = StoreProfile.objects.filter(tenant=tenant).first()
    if not profile:
        return redirect("tenants:dashboard_setup_store")

    state = StoreSetupWizardUseCase.get_state(profile=profile)
    if not profile.is_setup_complete and state.current_step < StoreSetupWizardUseCase.STEP_PAYMENT:
        return redirect("tenants:dashboard_setup_store")

    existing = StorePaymentSettings.objects.filter(tenant=tenant).first()
    initial = None
    if existing:
        initial = {
            "payment_mode": existing.mode,
            "provider_name": existing.provider_name,
            "merchant_key": existing.merchant_key,
            "webhook_secret": existing.webhook_secret,
            "is_enabled": existing.is_enabled,
        }

    form = PaymentSettingsForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            UpdatePaymentSettingsUseCase.execute(
                UpdatePaymentSettingsCommand(
                    user=request.user,
                    tenant=tenant,
                    payment_mode=form.cleaned_data["payment_mode"],
                    provider_name=form.cleaned_data.get("provider_name") or "",
                    merchant_key=form.cleaned_data.get("merchant_key") or "",
                    webhook_secret=form.cleaned_data.get("webhook_secret") or "",
                    is_enabled=form.cleaned_data.get("is_enabled", False),
                )
            )
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Payment settings saved.")
            return redirect("tenants:dashboard_setup_shipping")

    return render(
        request,
        "web/store/setup_payment.html",
        {
            "form": form,
            "tenant": tenant,
            "step": 2,
            "state": state,
            "wizard_progress": GetSetupProgressUseCase.execute(
                GetSetupProgressCommand(
                    tenant_ctx=TenantContext(
                        tenant_id=tenant.id,
                        currency=tenant.currency,
                        user_id=request.user.id,
                        session_key=request.session.session_key or "",
                    ),
                    actor_id=request.user.id,
                )
            ),
        },
    )


@login_required
@tenant_access_required
@require_http_methods(["GET", "POST"])
def dashboard_setup_shipping(request: HttpRequest) -> HttpResponse:
    tenant = request.tenant
    try:
        EnsureTenantOwnershipPolicy.ensure_is_owner(user=request.user, tenant=tenant)
    except StoreAccessDeniedError as exc:
        raise PermissionDenied(str(exc)) from exc

    profile = StoreProfile.objects.filter(tenant=tenant).first()
    if not profile:
        return redirect("tenants:dashboard_setup_store")

    state = StoreSetupWizardUseCase.get_state(profile=profile)
    if not profile.is_setup_complete and state.current_step < StoreSetupWizardUseCase.STEP_SHIPPING:
        return redirect("tenants:dashboard_setup_payment")

    existing = StoreShippingSettings.objects.filter(tenant=tenant).first()
    initial = None
    if existing:
        initial = {
            "fulfillment_mode": existing.fulfillment_mode,
            "origin_city": existing.origin_city,
            "delivery_fee_flat": existing.delivery_fee_flat,
            "free_shipping_threshold": existing.free_shipping_threshold,
            "is_enabled": existing.is_enabled,
        }

    form = ShippingSettingsForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            UpdateShippingSettingsUseCase.execute(
                UpdateShippingSettingsCommand(
                    user=request.user,
                    tenant=tenant,
                    fulfillment_mode=form.cleaned_data["fulfillment_mode"],
                    origin_city=form.cleaned_data.get("origin_city") or "",
                    delivery_fee_flat=form.cleaned_data.get("delivery_fee_flat"),
                    free_shipping_threshold=form.cleaned_data.get("free_shipping_threshold"),
                    is_enabled=form.cleaned_data.get("is_enabled", False),
                )
            )
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("tenants:dashboard_setup_payment")
        else:
            messages.success(request, "Shipping settings saved. Next: activate your store.")
            return redirect("tenants:dashboard_setup_activate")

    return render(
        request,
        "web/store/setup_shipping.html",
        {
            "form": form,
            "tenant": tenant,
            "step": 3,
            "state": state,
            "wizard_progress": GetSetupProgressUseCase.execute(
                GetSetupProgressCommand(
                    tenant_ctx=TenantContext(
                        tenant_id=tenant.id,
                        currency=tenant.currency,
                        user_id=request.user.id,
                        session_key=request.session.session_key or "",
                    ),
                    actor_id=request.user.id,
                )
            ),
        },
    )


@login_required
@tenant_access_required
@require_http_methods(["GET", "POST"])
def dashboard_setup_activate(request: HttpRequest) -> HttpResponse:
    tenant = request.tenant
    try:
        EnsureTenantOwnershipPolicy.ensure_is_owner(user=request.user, tenant=tenant)
    except StoreAccessDeniedError as exc:
        raise PermissionDenied(str(exc)) from exc

    profile = StoreProfile.objects.filter(tenant=tenant).first()
    if not profile:
        return redirect("tenants:dashboard_setup_store")

    state = StoreSetupWizardUseCase.get_state(profile=profile)
    if not profile.is_setup_complete and state.current_step < StoreSetupWizardUseCase.STEP_FIRST_PRODUCT:
        if state.current_step == StoreSetupWizardUseCase.STEP_STORE_INFO:
            return redirect("tenants:dashboard_setup_store")
        if state.current_step == StoreSetupWizardUseCase.STEP_PAYMENT:
            return redirect("tenants:dashboard_setup_payment")
        if state.current_step == StoreSetupWizardUseCase.STEP_SHIPPING:
            return redirect("tenants:dashboard_setup_shipping")

    readiness = GetStoreReadinessUseCase.execute(
        GetStoreReadinessCommand(user=request.user, tenant=tenant)
    )

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip().lower()
        if action == "activate":
            try:
                ActivateStoreUseCase.execute(ActivateStoreCommand(user=request.user, tenant=tenant))
            except StoreNotReadyError as exc:
                reasons = exc.reasons or [str(exc)]
                for reason in reasons:
                    messages.error(request, reason)
            else:
                messages.success(request, "Store activated successfully. Your store is now live.")
                return redirect("tenants:dashboard_setup_activate")
        elif action == "deactivate":
            DeactivateStoreUseCase.execute(
                DeactivateStoreCommand(user=request.user, tenant=tenant, reason=request.POST.get("reason") or "")
            )
            messages.success(request, "Store deactivated. Visitors will see a maintenance page.")
            return redirect("tenants:dashboard_setup_activate")
        else:
            messages.error(request, "Invalid action.")
            return redirect("tenants:dashboard_setup_activate")

    public_domain = (tenant.domain or "").strip()
    if public_domain:
        public_url_hint = f"{public_domain}"
    else:
        public_url_hint = f"{tenant.slug}.<your-domain>"

    return render(
        request,
        "web/store/setup_activate.html",
        {
            "tenant": tenant,
            "profile": profile,
            "state": state,
            "step": 4,
            "readiness": readiness,
            "public_url_hint": public_url_hint,
            "storefront_path": "/store/",
            "wizard_progress": GetSetupProgressUseCase.execute(
                GetSetupProgressCommand(
                    tenant_ctx=TenantContext(
                        tenant_id=tenant.id,
                        currency=tenant.currency,
                        user_id=request.user.id,
                        session_key=request.session.session_key or "",
                    ),
                    actor_id=request.user.id,
                )
            ),
        },
    )


@login_required
@tenant_access_required
@require_http_methods(["GET", "POST"])
def store_setup_step1(request: HttpRequest) -> HttpResponse:
    tenant = request.tenant
    try:
        EnsureTenantOwnershipPolicy.ensure_is_owner(user=request.user, tenant=tenant)
    except StoreAccessDeniedError as exc:
        raise PermissionDenied(str(exc)) from exc

    initial = {
        "name": tenant.name,
        "slug": tenant.slug,
        "currency": tenant.currency,
        "language": tenant.language,
        "primary_color": tenant.primary_color,
        "secondary_color": tenant.secondary_color,
    }
    form = StoreSettingsForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            UpdateStoreSettingsUseCase.execute(
                UpdateStoreSettingsCommand(
                    user=request.user,
                    tenant=tenant,
                    name=form.cleaned_data["name"],
                    slug=form.cleaned_data["slug"],
                    currency=form.cleaned_data.get("currency") or "SAR",
                    language=form.cleaned_data.get("language") or "ar",
                    logo_file=form.cleaned_data.get("logo"),
                    primary_color=form.cleaned_data.get("primary_color") or "",
                    secondary_color=form.cleaned_data.get("secondary_color") or "",
                )
            )
        except StoreSlugAlreadyTakenError as exc:
            form.add_error("slug", str(exc))
        else:
            # Mark wizard step 1 done (store info)
            profile = StoreProfile.objects.filter(tenant=tenant).first()
            if profile:
                StoreSetupWizardUseCase.mark_step_done(user=request.user, profile=profile, step=1)
            messages.success(request, "Store info saved.")
            return redirect("tenants:store_setup_step2")

    context = {
        "form": form,
        "tenant": tenant,
        "step": 1,
        "wizard_progress": GetSetupProgressUseCase.execute(
            GetSetupProgressCommand(
                tenant_ctx=TenantContext(
                    tenant_id=tenant.id,
                    currency=tenant.currency,
                    user_id=request.user.id,
                    session_key=request.session.session_key or "",
                ),
                actor_id=request.user.id,
            )
        ),
    }
    return render(request, "web/store/setup_step1.html", context)


@login_required
@tenant_access_required
@require_http_methods(["GET", "POST"])
def store_setup_step2(request: HttpRequest) -> HttpResponse:
    # Wizard alias for payment setup
    return dashboard_setup_payment(request)


@login_required
@tenant_access_required
@require_http_methods(["GET", "POST"])
def store_setup_step3(request: HttpRequest) -> HttpResponse:
    # Wizard alias for shipping setup
    return dashboard_setup_shipping(request)


@login_required
@tenant_access_required
@require_http_methods(["GET", "POST"])
def store_setup_step4(request: HttpRequest) -> HttpResponse:
    # Wizard alias for activation
    return dashboard_setup_activate(request)


@login_required
@tenant_access_required
@require_http_methods(["GET", "POST"])
def store_settings_update(request: HttpRequest) -> HttpResponse:
    tenant = request.tenant
    try:
        EnsureTenantOwnershipPolicy.ensure_is_owner(user=request.user, tenant=tenant)
    except StoreAccessDeniedError as exc:
        raise PermissionDenied(str(exc)) from exc

    initial = {
        "name": tenant.name,
        "slug": tenant.slug,
        "currency": tenant.currency,
        "language": tenant.language,
        "primary_color": tenant.primary_color,
        "secondary_color": tenant.secondary_color,
    }
    form = StoreSettingsForm(request.POST or None, request.FILES or None, initial=initial)

    if request.method == "GET":
        context = {
            "form": form,
            "tenant": tenant,
            "step": 1,
            "wizard_progress": GetSetupProgressUseCase.execute(
                GetSetupProgressCommand(
                    tenant_ctx=TenantContext(
                        tenant_id=tenant.id,
                        currency=tenant.currency,
                        user_id=request.user.id,
                        session_key=request.session.session_key or "",
                    ),
                    actor_id=request.user.id,
                )
            ),
        }
        return render(request, "web/store/setup_step1.html", context)

    if not form.is_valid():
        messages.error(request, "Invalid store settings.")
        return redirect("tenants:store_settings_update")

    try:
        UpdateStoreSettingsUseCase.execute(
            UpdateStoreSettingsCommand(
                user=request.user,
                tenant=tenant,
                name=form.cleaned_data["name"],
                slug=form.cleaned_data["slug"],
                currency=form.cleaned_data.get("currency") or "SAR",
                language=form.cleaned_data.get("language") or "ar",
                logo_file=form.cleaned_data.get("logo"),
                primary_color=form.cleaned_data.get("primary_color") or "",
                secondary_color=form.cleaned_data.get("secondary_color") or "",
            )
        )
    except StoreSlugAlreadyTakenError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Store settings updated.")

    return redirect("tenants:store_settings_update")


@require_GET
def custom_domain_verification(request: HttpRequest, token: str) -> HttpResponse:
    host = (request.get_host() or "").split(":", 1)[0].strip().lower()
    domain = (
        StoreDomain.objects.filter(domain=host, verification_token=token)
        .exclude(status=StoreDomain.STATUS_DISABLED)
        .first()
    )
    if not domain:
        return HttpResponse("Not found", status=404, content_type="text/plain")
    return HttpResponse(token, content_type="text/plain")


@login_required
@tenant_access_required
@require_POST
def custom_domain_add(request: HttpRequest) -> HttpResponse:
    tenant = request.tenant
    form = CustomDomainForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Invalid domain.")
        return redirect("tenants:store_settings_update")

    try:
        AddCustomDomainUseCase.execute(
            AddCustomDomainCommand(
                user=request.user,
                tenant=tenant,
                domain=form.cleaned_data["domain"],
            )
        )
    except StoreDomainError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Domain added. Update DNS then verify.")

    return redirect("tenants:store_settings_update")


@login_required
@tenant_access_required
@require_POST
def custom_domain_verify(request: HttpRequest, domain_id: int) -> HttpResponse:
    tenant = request.tenant
    domain = StoreDomain.objects.filter(id=domain_id, tenant=tenant).first()
    if not domain:
        messages.error(request, "Domain not found.")
        return redirect("tenants:store_settings_update")

    try:
        EnsureTenantOwnershipPolicy.ensure_is_owner(user=request.user, tenant=tenant)
    except StoreAccessDeniedError as exc:
        raise PermissionDenied(str(exc)) from exc

    enqueue_verify_domain(domain_id=domain.id)
    messages.success(request, "Verification started. Please wait a moment.")
    return redirect("tenants:store_settings_update")


@login_required
@tenant_access_required
@require_POST
def custom_domain_disable(request: HttpRequest, domain_id: int) -> HttpResponse:
    tenant = request.tenant
    domain = StoreDomain.objects.filter(id=domain_id, tenant=tenant).first()
    if not domain:
        messages.error(request, "Domain not found.")
        return redirect("tenants:store_settings_update")

    try:
        DisableDomainUseCase.execute(
            DisableDomainCommand(
                actor=request.user,
                domain_id=domain.id,
                reason=request.POST.get("reason") or "",
            )
        )
    except StoreDomainError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Domain disabled.")

    return redirect("tenants:store_settings_update")


@login_required
@tenant_access_required
@require_GET
def dashboard_home(request: HttpRequest) -> HttpResponse:
    """Minimal dashboard landing page.

    - Requires login and tenant access
    - Keeps view thin; KPI widgets can be added later
    """
    destination = resolve_onboarding_state(request)
    if destination != request.path:
        return redirect(destination)

    tenant = getattr(request, "tenant", None)
    if tenant is None:
        return redirect("tenants:store_create")

    try:
        EnsureTenantOwnershipPolicy.ensure_can_access(user=request.user, tenant=tenant)
    except (StoreAccessDeniedError, StoreInactiveError) as exc:
        raise PermissionDenied(str(exc)) from exc

    use_case = GetMerchantDashboardMetricsUseCase()
    metrics = use_case.execute(
        GetMerchantDashboardMetricsQuery(
            actor_user_id=request.user.id,
            tenant_id=tenant.id,
            currency=getattr(tenant, "currency", "SAR") or "SAR",
            timezone=str(timezone.get_current_timezone()),
        )
    )

    return render(
        request,
        "dashboard/pages/overview.html",
        {
            "tenant": tenant,
            "metrics": metrics,
        },
    )


@login_required
@tenant_access_required
@require_GET
def dashboard_orders(request: HttpRequest) -> HttpResponse:
    """Merchant orders list (placeholder).

    The Orders domain in this repo is currently API-first.
    This screen provides the merchant-facing UI shell and can be wired to real
    order queries later via an application-level read use-case.
    """
    return render(request, "dashboard/orders.html", {"tenant": request.tenant})
