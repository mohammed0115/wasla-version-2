from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import AccountProfile
from subscriptions.models import SubscriptionPlan
from subscriptions.services.subscription_service import SubscriptionService
from catalog.services.product_service import ProductService
from tenants.models import (
    StorePaymentSettings,
    StoreProfile,
    StoreShippingSettings,
    Tenant,
    TenantAuditLog,
    TenantMembership,
)


class MerchantStoreCreationScenarioTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client = Client()
        SubscriptionPlan.objects.get_or_create(
            name="Basic",
            defaults={
                "price": Decimal("0.00"),
                "billing_cycle": "monthly",
                "features": ["wallet", "reviews"],
                "max_products": 50,
                "max_orders_monthly": 500,
                "max_staff_users": 3,
                "is_active": True,
            },
        )

    def _signup_and_login(self, username: str = "m1") -> tuple[str, str]:
        suffix = "".join(ch for ch in username if ch.isdigit()) or str(len(username))
        suffix = suffix[-7:].zfill(7)
        phone = f"050{suffix}"
        email = f"{username}@example.com"
        response = self.client.post(
            reverse("signup"),
            data={
                "full_name": f"{username} Merchant",
                "phone": phone,
                "email": email,
                "password": "StrongPass12345!",
                "accept_terms": "on",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        country = self.client.post(reverse("onboarding:country"), data={"country": "SA"}, follow=True)
        self.assertEqual(country.status_code, 200)

        business_types = self.client.post(
            reverse("onboarding:business"),
            data={"business_types": ["fashion"]},
            follow=True,
        )
        self.assertEqual(business_types.status_code, 200)
        return phone, email

    def test_signup_then_create_store_then_complete_wizard(self):
        phone, _email = self._signup_and_login("merchant1")

        response = self.client.get(reverse("web:dashboard_setup_store"))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("web:dashboard_setup_store"),
            data={"name": "My Store", "slug": "myshop", "currency": "SAR", "language": "ar"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        tenant = Tenant.objects.get(slug="myshop")
        self.assertEqual(tenant.currency, "SAR")
        self.assertEqual(tenant.language, "ar")

        profile = StoreProfile.objects.get(tenant=tenant)
        self.assertEqual(profile.setup_step, 2)
        self.assertFalse(profile.is_setup_complete)

        self.assertTrue(
            TenantMembership.objects.filter(
                tenant=tenant,
                user__username=phone,
                role=TenantMembership.ROLE_OWNER,
                is_active=True,
            ).exists()
        )

        self.assertIsNotNone(SubscriptionService.get_active_subscription(tenant.id))

        actions = set(TenantAuditLog.objects.filter(tenant=tenant).values_list("action", flat=True))
        self.assertIn("tenant_created", actions)
        self.assertIn("store_created", actions)

        shipping_redirect = self.client.get(reverse("web:dashboard_setup_shipping"))
        self.assertEqual(shipping_redirect.status_code, 302)

        response = self.client.post(
            reverse("web:dashboard_setup_payment"),
            data={"payment_mode": "manual", "is_enabled": "on"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(StorePaymentSettings.objects.filter(tenant=tenant).exists())

        profile.refresh_from_db()
        self.assertEqual(profile.setup_step, 3)

        response = self.client.post(
            reverse("web:dashboard_setup_shipping"),
            data={"fulfillment_mode": "pickup", "is_enabled": "on"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(StoreShippingSettings.objects.filter(tenant=tenant).exists())

        profile.refresh_from_db()
        self.assertEqual(profile.setup_step, 4)
        self.assertFalse(profile.is_setup_complete)

    def test_reserved_slug_rejected(self):
        self._signup_and_login("merchant2")
        response = self.client.post(
            reverse("web:dashboard_setup_store"),
            data={"name": "My Store", "slug": "admin", "currency": "SAR", "language": "ar"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Tenant.objects.filter(slug="admin").exists())
        self.assertIn("form", response.context)
        self.assertIn("slug", response.context["form"].errors)

    def test_duplicate_slug_rejected(self):
        Tenant.objects.create(slug="taken", name="Taken", is_active=True)
        self._signup_and_login("merchant3")
        response = self.client.post(
            reverse("web:dashboard_setup_store"),
            data={"name": "My Store", "slug": "taken", "currency": "SAR", "language": "ar"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Tenant.objects.filter(slug="taken").count(), 1)

    def test_create_store_is_idempotent_per_user(self):
        self._signup_and_login("merchant4")

        starting_count = Tenant.objects.count()
        self.client.post(
            reverse("web:dashboard_setup_store"),
            data={"name": "My Store", "slug": "shop1", "currency": "SAR", "language": "ar"},
            follow=True,
        )
        self.assertEqual(Tenant.objects.count(), starting_count + 1)

        response = self.client.get(reverse("web:dashboard_setup_store"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Tenant.objects.count(), starting_count + 1)

    def test_cannot_access_other_tenant_web(self):
        User = get_user_model()
        u1 = User.objects.create_user(username="u1", email="u1@example.com", password="pass12345")
        u2 = User.objects.create_user(username="u2", password="pass12345")
        t1 = Tenant.objects.create(slug="t1", name="T1", is_active=True)
        t2 = Tenant.objects.create(slug="t2", name="T2", is_active=True)
        TenantMembership.objects.create(tenant=t1, user=u1, role=TenantMembership.ROLE_OWNER)
        TenantMembership.objects.create(tenant=t2, user=u2, role=TenantMembership.ROLE_OWNER)

        AccountProfile.objects.create(
            user=u1,
            full_name="U1 Merchant",
            phone="0501111111",
            country="SA",
            business_types=["fashion"],
            accepted_terms_at=timezone.now(),
        )

        self.assertTrue(self.client.login(username="u1", password="pass12345"))

        response = self.client.get(reverse("web:product_list"), HTTP_X_TENANT="t2")
        self.assertEqual(response.status_code, 403)

    def test_api_store_id_mismatch_denied(self):
        User = get_user_model()
        u1 = User.objects.create_user(username="u1a", password="pass12345")
        u2 = User.objects.create_user(username="u2a", password="pass12345")
        t1 = Tenant.objects.create(slug="ta1", name="TA1", is_active=True)
        t2 = Tenant.objects.create(slug="ta2", name="TA2", is_active=True)
        TenantMembership.objects.create(tenant=t1, user=u1, role=TenantMembership.ROLE_OWNER)
        TenantMembership.objects.create(tenant=t2, user=u2, role=TenantMembership.ROLE_OWNER)

        self.assertTrue(self.client.login(username="u1a", password="pass12345"))

        ok = self.client.get(f"/api/stores/{t1.id}/wallet/", HTTP_X_TENANT=t1.slug)
        self.assertEqual(ok.status_code, 200)

        mismatch = self.client.get(f"/api/stores/{t2.id}/wallet/", HTTP_X_TENANT=t1.slug)
        self.assertEqual(mismatch.status_code, 403)

    def test_activate_and_deactivate_store_with_public_visibility(self):
        self._signup_and_login("merchant5")

        self.client.post(
            reverse("web:dashboard_setup_store"),
            data={"name": "My Store", "slug": "actshop", "currency": "SAR", "language": "ar"},
            follow=True,
        )
        tenant = Tenant.objects.get(slug="actshop")

        self.client.post(
            reverse("web:dashboard_setup_payment"),
            data={"payment_mode": "manual", "is_enabled": "on"},
            follow=True,
        )
        self.client.post(
            reverse("web:dashboard_setup_shipping"),
            data={"fulfillment_mode": "pickup", "is_enabled": "on"},
            follow=True,
        )

        activation_fail = self.client.post(
            reverse("web:dashboard_setup_activate"),
            data={"action": "activate"},
            follow=True,
        )
        self.assertEqual(activation_fail.status_code, 200)
        tenant.refresh_from_db()
        self.assertFalse(tenant.is_published)

        public_client = Client()
        coming_soon = public_client.get("/store/", HTTP_X_TENANT=tenant.slug)
        self.assertEqual(coming_soon.status_code, 200)
        self.assertContains(coming_soon, "قريباً")

        ProductService.create_product(
            store_id=tenant.id,
            sku="FIRSTSKU",
            name="First Product",
            price=Decimal("10.00"),
            quantity=5,
        )

        activation_ok = self.client.post(
            reverse("web:dashboard_setup_activate"),
            data={"action": "activate"},
            follow=True,
        )
        self.assertEqual(activation_ok.status_code, 200)

        tenant.refresh_from_db()
        self.assertTrue(tenant.is_published)
        self.assertIsNotNone(tenant.activated_at)
        self.assertIsNone(tenant.deactivated_at)

        profile = StoreProfile.objects.get(tenant=tenant)
        self.assertTrue(profile.is_setup_complete)

        live = public_client.get("/store/", HTTP_X_TENANT=tenant.slug)
        self.assertEqual(live.status_code, 200)
        self.assertContains(live, "First Product")

        deactivation_ok = self.client.post(
            reverse("web:dashboard_setup_activate"),
            data={"action": "deactivate", "reason": "test"},
            follow=True,
        )
        self.assertEqual(deactivation_ok.status_code, 200)

        tenant.refresh_from_db()
        self.assertFalse(tenant.is_published)
        self.assertIsNotNone(tenant.deactivated_at)

        maintenance = public_client.get("/store/", HTTP_X_TENANT=tenant.slug)
        self.assertEqual(maintenance.status_code, 200)
        self.assertContains(maintenance, "صيانة")
