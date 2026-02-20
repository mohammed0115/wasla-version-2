from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from apps.admin_portal.models import (
    AdminAuditLog,
    AdminPermission,
    AdminRole,
    AdminRolePermission,
    AdminUserRole,
)
from apps.settlements.models import Invoice
from apps.stores.models import Store
from apps.tenants.models import Tenant


class AdminPortalPhaseE2Tests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.User = get_user_model()

        self.owner = self.User.objects.create_user(
            username="owner",
            email="owner@test.local",
            password="pass1234",
        )

        self.tenant = Tenant.objects.create(name="Tenant A", slug="tenant-a", is_active=True)
        self.store = Store.objects.create(
            owner=self.owner,
            tenant=self.tenant,
            name="Store A",
            slug="store-a",
            subdomain="store-a",
            status=Store.STATUS_ACTIVE,
        )
        self.invoice = Invoice.objects.create(
            tenant=self.tenant,
            year=2026,
            month=2,
            total_operations=3,
            total_wasla_fee=15,
            status=Invoice.STATUS_DRAFT,
        )

        self._ensure_default_rbac()

    def _ensure_default_rbac(self):
        roles = {
            "SuperAdmin": "Full access",
            "Finance": "Finance role",
            "Support": "Support role",
            "Ops": "Ops role",
        }
        for name, description in roles.items():
            AdminRole.objects.get_or_create(name=name, defaults={"description": description})

        permissions = {
            "TENANTS_VIEW": "",
            "TENANTS_EDIT": "",
            "STORES_VIEW": "",
            "STORES_EDIT": "",
            "FINANCE_VIEW": "",
            "FINANCE_MARK_INVOICE_PAID": "",
            "WEBHOOKS_VIEW": "",
        }
        for code, description in permissions.items():
            AdminPermission.objects.get_or_create(code=code, defaults={"description": description})

        mapping = {
            "SuperAdmin": list(permissions.keys()),
            "Finance": ["FINANCE_VIEW", "FINANCE_MARK_INVOICE_PAID"],
            "Support": ["TENANTS_VIEW", "STORES_VIEW", "FINANCE_VIEW"],
            "Ops": ["STORES_VIEW", "WEBHOOKS_VIEW"],
        }

        for role_name, codes in mapping.items():
            role = AdminRole.objects.get(name=role_name)
            for code in codes:
                perm = AdminPermission.objects.get(code=code)
                AdminRolePermission.objects.get_or_create(role=role, permission=perm)

    def _login_with_role(self, username: str, role_name: str):
        user = self.User.objects.create_user(
            username=username,
            email=f"{username}@test.local",
            password="pass1234",
            is_staff=True,
        )
        role = AdminRole.objects.get(name=role_name)
        AdminUserRole.objects.create(user=user, role=role)
        self.client.login(username=username, password="pass1234")
        return user

    def test_rbac_finance_cannot_edit_tenant(self):
        self._login_with_role("finance_user", "Finance")

        response = self.client.post(
            reverse("admin_portal:tenant_set_active", args=[self.tenant.id]),
            {"active": "0"},
        )

        self.assertEqual(response.status_code, 403)

    def test_rbac_support_cannot_mark_invoice_paid(self):
        self._login_with_role("support_user", "Support")

        response = self.client.post(
            reverse("admin_portal:invoice_mark_paid", args=[self.invoice.id]),
        )

        self.assertEqual(response.status_code, 403)

    def test_audit_log_created_for_tenant_action(self):
        actor = self._login_with_role("super_user", "SuperAdmin")

        response = self.client.post(
            reverse("admin_portal:tenant_set_active", args=[self.tenant.id]),
            {"active": "0"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            AdminAuditLog.objects.filter(
                actor=actor,
                action="TENANT_DEACTIVATE",
                object_type="Tenant",
                object_id=str(self.tenant.id),
            ).exists()
        )

    def test_security_headers_on_portal_response(self):
        response = self.client.get(reverse("admin_portal:login"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(response["Referrer-Policy"], "same-origin")
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

    def test_login_throttle_blocks_after_five_failures(self):
        for _ in range(5):
            response = self.client.post(
                reverse("admin_portal:login"),
                {"username": "nope", "password": "bad"},
            )
            self.assertIn(response.status_code, [200, 429])

        blocked = self.client.post(
            reverse("admin_portal:login"),
            {"username": "nope", "password": "bad"},
        )

        self.assertEqual(blocked.status_code, 429)
        self.assertIn("تم", blocked.content.decode("utf-8"))

    def test_dashboard_loads_for_super_admin(self):
        self._login_with_role("dash_admin", "SuperAdmin")

        response = self.client.get(reverse("admin_portal:dashboard"))

        self.assertEqual(response.status_code, 200)

    def test_stores_page_loads_for_super_admin(self):
        self._login_with_role("stores_admin", "SuperAdmin")

        response = self.client.get(reverse("admin_portal:stores"))

        self.assertEqual(response.status_code, 200)
