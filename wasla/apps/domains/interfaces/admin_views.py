from __future__ import annotations

import json
import logging

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.tenants.models import StoreDomain

from ..models import DomainAlert, DomainHealth
from ..tasks import check_domain_health, renew_expiring_ssl

logger = logging.getLogger("domain_monitoring")


@staff_member_required
@require_POST
def mark_domain_pending(request: HttpRequest, domain_id: int) -> HttpResponse:
    domain = StoreDomain.objects.filter(id=domain_id).first()
    if not domain:
        messages.error(request, "Domain not found.")
        return redirect("/admin/")
    domain.status = StoreDomain.STATUS_PENDING_VERIFICATION
    domain.save(update_fields=["status"])
    messages.success(request, "Domain marked for provisioning. Run provision_domains.")
    return redirect("/admin/")


@staff_member_required
@require_GET
def monitoring_dashboard(request: HttpRequest) -> HttpResponse:
    filter_key = (request.GET.get("filter") or "").strip().lower()
    domains = StoreDomain.objects.select_related("tenant", "health_status").order_by("domain")

    rows = []
    for item in domains:
        health = getattr(item, "health_status", None)
        status = health.status if health else DomainHealth.STATUS_ERROR
        is_expiring = bool(health and health.is_expiring_soon)

        if filter_key == "healthy" and status != DomainHealth.STATUS_HEALTHY:
            continue
        if filter_key == "expiring" and not is_expiring:
            continue
        if filter_key == "failing" and status != DomainHealth.STATUS_ERROR:
            continue

        rows.append({"domain": item, "health": health, "status": status})

    return render(
        request,
        "admin_portal/domains/dashboard.html",
        {"rows": rows, "filter_key": filter_key},
    )


@staff_member_required
@require_GET
def monitoring_detail(request: HttpRequest, domain_id: int) -> HttpResponse:
    domain = StoreDomain.objects.select_related("tenant").filter(id=domain_id).first()
    if not domain:
        messages.error(request, "Domain not found.")
        return redirect("domains_admin_dashboard")

    latest = DomainHealth.objects.filter(store_domain=domain).first()
    history = []
    if latest:
        history = [latest]
    alerts = DomainAlert.objects.filter(store_domain=domain).order_by("-created_at")[:50]

    return render(
        request,
        "admin_portal/domains/detail.html",
        {
            "domain": domain,
            "latest": latest,
            "history": history,
            "alerts": alerts,
        },
    )


@staff_member_required
@require_POST
def rerun_health_check(request: HttpRequest, domain_id: int) -> HttpResponse:
    domain = StoreDomain.objects.filter(id=domain_id).first()
    if not domain:
        messages.error(request, "Domain not found.")
        return redirect("domains_admin_dashboard")

    check_domain_health.delay(domain_id=domain_id)
    logger.info(json.dumps({"action": "admin_rerun_health", "store_id": domain.tenant_id, "domain": domain.domain}))
    messages.success(request, "Health check queued.")
    return redirect("domains_admin_detail", domain_id=domain_id)


@staff_member_required
@require_POST
def force_renew_ssl(request: HttpRequest, domain_id: int) -> HttpResponse:
    domain = StoreDomain.objects.filter(id=domain_id).first()
    if not domain:
        messages.error(request, "Domain not found.")
        return redirect("domains_admin_dashboard")

    renew_expiring_ssl.delay(domain_id=domain_id)
    logger.info(json.dumps({"action": "admin_force_renew_ssl", "store_id": domain.tenant_id, "domain": domain.domain}))
    messages.success(request, "SSL renewal queued.")
    return redirect("domains_admin_detail", domain_id=domain_id)
