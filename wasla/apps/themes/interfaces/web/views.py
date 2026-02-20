from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.tenants.domain.tenant_context import TenantContext
from apps.tenants.guards import require_store, require_tenant
from apps.tenants.interfaces.web.decorators import tenant_access_required
from apps.themes.application.use_cases.list_themes import ListThemesUseCase
from apps.themes.application.use_cases.update_branding import (
    UpdateBrandingCommand,
    UpdateBrandingUseCase,
)
from apps.themes.interfaces.web.forms import BrandingForm
from apps.themes.models import StoreBranding


def _build_tenant_context(request: HttpRequest) -> TenantContext:
    store = require_store(request)
    tenant = require_tenant(request)
    tenant_id = tenant.id
    store_id = store.id
    currency = getattr(tenant, "currency", "SAR")
    if not request.session.session_key:
        request.session.save()
    session_key = request.session.session_key
    user_id = request.user.id if request.user.is_authenticated else None
    return TenantContext(
        tenant_id=tenant_id,
        store_id=store_id,
        currency=currency,
        user_id=user_id,
        session_key=session_key,
    )


@login_required
@tenant_access_required
@require_http_methods(["GET", "POST"])
def themes_list(request: HttpRequest) -> HttpResponse:
    tenant_ctx = _build_tenant_context(request)
    themes = ListThemesUseCase.execute()
    branding = StoreBranding.objects.for_tenant(tenant_ctx.store_id).first()

    if request.method == "POST":
        theme_code = (request.POST.get("theme_code") or "").strip()
        try:
            UpdateBrandingUseCase.execute(
                UpdateBrandingCommand(
                    tenant_ctx=tenant_ctx,
                    actor_id=request.user.id if request.user.is_authenticated else None,
                    theme_code=theme_code,
                )
            )
            messages.success(request, "Theme updated.")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("themes_web:dashboard_themes")

    return render(
        request,
        "dashboard/themes/list.html",
        {"themes": themes, "branding": branding},
    )


@login_required
@tenant_access_required
@require_http_methods(["GET", "POST"])
def branding_edit(request: HttpRequest) -> HttpResponse:
    tenant_ctx = _build_tenant_context(request)
    branding = StoreBranding.objects.for_tenant(tenant_ctx.store_id).first()
    initial = {
        "theme_code": getattr(branding, "theme_code", ""),
        "primary_color": getattr(branding, "primary_color", ""),
        "secondary_color": getattr(branding, "secondary_color", ""),
        "accent_color": getattr(branding, "accent_color", ""),
        "font_family": getattr(branding, "font_family", ""),
    }
    form = BrandingForm(request.POST or None, request.FILES or None, initial=initial)

    if request.method == "POST" and form.is_valid():
        try:
            UpdateBrandingUseCase.execute(
                UpdateBrandingCommand(
                    tenant_ctx=tenant_ctx,
                    actor_id=request.user.id if request.user.is_authenticated else None,
                    theme_code=form.cleaned_data.get("theme_code") or "",
                    logo_file=form.cleaned_data.get("logo_file"),
                    primary_color=form.cleaned_data.get("primary_color") or "",
                    secondary_color=form.cleaned_data.get("secondary_color") or "",
                    accent_color=form.cleaned_data.get("accent_color") or "",
                    font_family=form.cleaned_data.get("font_family") or "",
                )
            )
            messages.success(request, "Branding updated.")
            return redirect("themes_web:dashboard_branding")
        except ValueError as exc:
            messages.error(request, str(exc))

    return render(request, "dashboard/branding/edit.html", {"form": form, "branding": branding})
