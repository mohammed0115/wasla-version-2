from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from apps.admin_portal.decorators import admin_has_permission
from apps.admin_portal.models import AdminPermission, AdminRole, AdminRolePermission, AdminUserRole
from apps.settlements.models import Invoice
from apps.tenants.models import Tenant


class AdminPortalRbacSeedTests(TestCase):
    def test_seed_admin_portal_rbac_idempotent(self):
        call_command("seed_admin_portal_rbac", verbosity=0)

        roles_count = AdminRole.objects.count()
        permissions_count = AdminPermission.objects.count()
        links_count = AdminRolePermission.objects.count()

        call_command("seed_admin_portal_rbac", verbosity=0)

        self.assertEqual(AdminRole.objects.count(), roles_count)
        self.assertEqual(AdminPermission.objects.count(), permissions_count)
        self.assertEqual(AdminRolePermission.objects.count(), links_count)
        self.assertEqual(roles_count, 7)
        self.assertEqual(permissions_count, 15)
        self.assertEqual(links_count, 56)

    def test_superuser_gets_superadmin_role(self):
        User = get_user_model()
        superuser = User.objects.create_superuser(
            username="superadmin",
            email="superadmin@test.local",
            password="pass1234",
        )
        self.assertFalse(AdminUserRole.objects.filter(user=superuser).exists())

        call_command("seed_admin_portal_rbac", verbosity=0)

        superuser_role = AdminUserRole.objects.get(user=superuser)
        self.assertEqual(superuser_role.role.name, "SUPERADMIN")


class AdminPortalRbacAccessTests(TestCase):
    def setUp(self):
        call_command("seed_admin_portal_rbac", verbosity=0)
        self.client = Client()
        self.User = get_user_model()

        self.tenant = Tenant.objects.create(name="Tenant A", slug="tenant-a", is_active=True)
        self.invoice = Invoice.objects.create(
            tenant=self.tenant,
            year=2026,
            month=2,
            total_operations=3,
            total_wasla_fee=15,
            status=Invoice.STATUS_DRAFT,
        )

    def test_non_superuser_without_role_is_denied(self):
        user = self.User.objects.create_user(
            username="plain_user",
            email="plain_user@test.local",
            password="pass1234",
            is_staff=True,
        )
        self.client.login(username="plain_user", password="pass1234")

        response = self.client.get(reverse("admin_portal:dashboard"))

        self.assertEqual(response.status_code, 403)

    def test_readonly_role_access_and_restrictions(self):
        readonly_role = AdminRole.objects.get(name="READONLY")
        user = self.User.objects.create_user(
            username="readonly_user",
            email="readonly_user@test.local",
            password="pass1234",
            is_staff=True,
        )
        AdminUserRole.objects.create(user=user, role=readonly_role)
        self.client.login(username="readonly_user", password="pass1234")

        dashboard_response = self.client.get(reverse("admin_portal:dashboard"))
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertFalse(admin_has_permission(user, "portal.users.manage"))
        self.assertFalse(admin_has_permission(user, "portal.settlements.approve"))

        approve_response = self.client.post(
            reverse("admin_portal:invoice_mark_paid", args=[self.invoice.id]),
        )
        self.assertEqual(approve_response.status_code, 403)
