from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from apps.tenants.models import Tenant, TenantMembership


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", ".localhost"])
class UsersRolesSettingsTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="tenant-owner",
            email="owner@store.test",
            password="pass12345",
        )
        self.admin = user_model.objects.create_user(
            username="tenant-admin",
            email="admin@store.test",
            password="pass12345",
        )
        self.staff = user_model.objects.create_user(
            username="tenant-staff",
            email="staff@store.test",
            password="pass12345",
        )

        self.tenant = Tenant.objects.create(slug="settings-tenant", name="Settings Tenant", is_active=True)
        TenantMembership.objects.create(
            tenant=self.tenant,
            user=self.owner,
            role=TenantMembership.ROLE_OWNER,
            is_active=True,
        )
        TenantMembership.objects.create(
            tenant=self.tenant,
            user=self.admin,
            role=TenantMembership.ROLE_ADMIN,
            is_active=True,
        )

    def _set_store_session(self):
        session = self.client.session
        session["store_id"] = self.tenant.id
        session.save()

    def test_owner_can_view_users_roles_page(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("tenants:dashboard_users_roles"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Users & Roles")

    def test_owner_can_add_member_and_update_role_and_deactivate(self):
        self.client.force_login(self.owner)

        add_response = self.client.post(
            reverse("tenants:dashboard_users_roles"),
            data={"email": self.staff.email, "role": TenantMembership.ROLE_STAFF},
            follow=True,
        )
        self.assertEqual(add_response.status_code, 200)
        membership = TenantMembership.objects.get(tenant=self.tenant, user=self.staff)
        self.assertEqual(membership.role, TenantMembership.ROLE_STAFF)
        self.assertTrue(membership.is_active)

        update_response = self.client.post(
            reverse("tenants:dashboard_member_update_role", args=[membership.id]),
            data={"role": TenantMembership.ROLE_READ_ONLY},
            follow=True,
        )
        self.assertEqual(update_response.status_code, 200)
        membership.refresh_from_db()
        self.assertEqual(membership.role, TenantMembership.ROLE_READ_ONLY)

        deactivate_response = self.client.post(
            reverse("tenants:dashboard_member_deactivate", args=[membership.id]),
            follow=True,
        )
        self.assertEqual(deactivate_response.status_code, 200)
        membership.refresh_from_db()
        self.assertFalse(membership.is_active)

    def test_non_owner_cannot_manage_users_roles(self):
        self.client.force_login(self.admin)
        self._set_store_session()

        response = self.client.get(reverse("tenants:dashboard_users_roles"))
        self.assertEqual(response.status_code, 403)
