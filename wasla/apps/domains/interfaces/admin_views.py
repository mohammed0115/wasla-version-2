from __future__ import annotations

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from apps.tenants.models import StoreDomain


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
