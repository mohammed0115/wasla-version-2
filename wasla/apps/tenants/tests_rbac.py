from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from django.test.utils import override_settings

from apps.security.rbac import has_permission
from apps.tenants.models import Permission, RolePermission, Tenant, TenantMembership


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", ".localhost"])
class RBACPermissionTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="rbac-user", password="pass12345")
        self.tenant = Tenant.objects.create(slug="rbac-tenant", name="RBAC Tenant", is_active=True)
        TenantMembership.objects.create(
            tenant=self.tenant,
            user=self.user,
            role=TenantMembership.ROLE_STAFF,
            is_active=True,
        )

        self.permission = Permission.objects.create(
            code="plugins.view_plugins",
            module="plugins",
            description="View plugin list",
        )
        RolePermission.objects.create(role=TenantMembership.ROLE_STAFF, permission=self.permission)

    def test_permission_resolver_uses_request_cache(self):
        request = RequestFactory().get("/api/plugins/")
        request.user = self.user
        request.tenant = self.tenant

        self.assertTrue(has_permission(request, "plugins.view_plugins"))

        RolePermission.objects.filter(role=TenantMembership.ROLE_STAFF, permission=self.permission).delete()

        self.assertTrue(has_permission(request, "plugins.view_plugins"))

    def test_plugin_list_denied_without_permission(self):
        RolePermission.objects.filter(role=TenantMembership.ROLE_STAFF, permission=self.permission).delete()

        self.client.force_login(self.user)
        session = self.client.session
        session["store_id"] = self.tenant.id
        session.save()

        response = self.client.get("/plugins/", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 403)

    def test_plugin_list_allowed_with_permission(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["store_id"] = self.tenant.id
        session.save()

        response = self.client.get("/plugins/", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)


class SeedPermissionsCommandTests(TestCase):
    def test_seed_permissions_creates_records(self):
        call_command("seed_permissions")

        self.assertTrue(Permission.objects.filter(code="catalog.create_product").exists())
        self.assertTrue(
            RolePermission.objects.filter(
                role=TenantMembership.ROLE_ADMIN,
                permission__code="catalog.create_product",
            ).exists()
        )
