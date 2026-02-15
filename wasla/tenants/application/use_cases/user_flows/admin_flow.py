from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from tenants.models import Tenant, TenantAuditLog

from .base import FlowReport, FlowStepResult


class AdminFlowValidator:
    name = "admin_flow"

    def run(self, *, client: Client, tenant_slug: str) -> FlowReport:
        steps: list[FlowStepResult] = []

        login_step = self._login_superuser(client)
        steps.append(login_step)
        if not login_step.ok:
            return FlowReport.from_steps(name=self.name, tenant_slug=tenant_slug, steps=steps)

        create_step = self._create_tenant_via_admin(client)
        steps.append(create_step)

        deactivate_step = self._deactivate_tenant_via_admin(client)
        steps.append(deactivate_step)

        audit_step = self._audit_actions()
        steps.append(audit_step)

        return FlowReport.from_steps(name=self.name, tenant_slug=tenant_slug, steps=steps)

    @staticmethod
    def _login_superuser(client: Client) -> FlowStepResult:
        User = get_user_model()
        admin, _ = User.objects.get_or_create(
            username="admin_flow_user",
            defaults={"is_staff": True, "is_superuser": True, "is_active": True},
        )
        admin.set_password("admin12345")
        admin.save(update_fields=["password"])
        if client.login(username="admin_flow_user", password="admin12345"):
            return FlowStepResult("admin_login", True)
        return FlowStepResult("admin_login", False, "Failed to login to admin.")

    @staticmethod
    def _create_tenant_via_admin(client: Client) -> FlowStepResult:
        add_url = reverse("admin:tenants_tenant_add")
        response = client.get(add_url)
        if response.status_code != 200:
            return FlowStepResult(
                "admin_add_tenant_page",
                False,
                f"Admin add tenant page not accessible (status {response.status_code}).",
            )

        payload = {
            "slug": "flow-admin-tenant",
            "name": "Flow Admin Tenant",
            "is_active": "on",
            "domain": "",
            "subdomain": "",
            "currency": "SAR",
            "language": "ar",
        }
        response = client.post(add_url, data=payload, follow=True)
        if response.status_code not in (200, 302):
            return FlowStepResult(
                "admin_add_tenant_submit",
                False,
                f"Admin tenant create failed (status {response.status_code}).",
            )

        if Tenant.objects.filter(slug="flow-admin-tenant").exists():
            return FlowStepResult("admin_add_tenant_submit", True)
        return FlowStepResult("admin_add_tenant_submit", False, "Tenant record not created.")

    @staticmethod
    def _deactivate_tenant_via_admin(client: Client) -> FlowStepResult:
        tenant = Tenant.objects.filter(slug="flow-admin-tenant").first()
        if not tenant:
            return FlowStepResult(
                "admin_deactivate_tenant",
                False,
                "Cannot deactivate tenant because it does not exist.",
            )

        change_url = reverse("admin:tenants_tenant_change", args=[tenant.id])
        response = client.get(change_url)
        if response.status_code != 200:
            return FlowStepResult(
                "admin_deactivate_tenant_page",
                False,
                f"Admin tenant change page not accessible (status {response.status_code}).",
            )

        payload = {
            "slug": tenant.slug,
            "name": tenant.name,
            "is_active": "",
            "domain": tenant.domain,
            "subdomain": tenant.subdomain,
            "currency": tenant.currency,
            "language": tenant.language,
        }
        response = client.post(change_url, data=payload, follow=True)
        if response.status_code not in (200, 302):
            return FlowStepResult(
                "admin_deactivate_tenant",
                False,
                f"Admin tenant deactivate failed (status {response.status_code}).",
            )

        tenant.refresh_from_db()
        if not tenant.is_active:
            return FlowStepResult("admin_deactivate_tenant", True)
        return FlowStepResult("admin_deactivate_tenant", False, "Tenant is still active.")

    @staticmethod
    def _audit_actions() -> FlowStepResult:
        logs = TenantAuditLog.objects.filter(
            tenant__slug="flow-admin-tenant",
            action__in=["tenant_created", "tenant_deactivated"],
        ).values_list("action", flat=True)
        actions = set(logs)
        missing = {"tenant_created", "tenant_deactivated"} - actions
        if not missing:
            return FlowStepResult("audit_actions", True)
        return FlowStepResult(
            "audit_actions",
            False,
            f"Missing audit actions: {', '.join(sorted(missing))}.",
        )
