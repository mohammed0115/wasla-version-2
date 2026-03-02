import uuid

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.customers.models import Customer
from apps.orders.models import Order
from apps.stores.models import Store
from apps.subscriptions.forms_onboarding import SubdomainSelectForm
from apps.subscriptions.models import SubscriptionPlan
from apps.tenants.models import Tenant


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    WASSLA_EMAIL_ASYNC_ENABLED=False,
    WASSLA_BASE_DOMAIN="example.com",
)
class OnboardingFlowEmailTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="merchant",
            email="merchant@example.com",
            password="testpass123",
        )
        self.plan = SubscriptionPlan.objects.create(
            name=f"Free-{uuid.uuid4().hex[:6]}",
            price=0,
            billing_cycle="monthly",
            is_active=True,
            is_public=True,
        )

    def test_free_plan_store_creation_sends_welcome_email(self):
        self.client.force_login(self.user)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("subscriptions_web:onboarding_plan"),
                {"plan_id": self.plan.id},
            )
            response = self.client.post(
                reverse("subscriptions_web:onboarding_subdomain"),
                {"subdomain": "mystore"},
            )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Store.objects.filter(owner=self.user, subdomain="mystore").exists())
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn("https://mystore.example.com/dashboard/", email.body)
        self.assertTrue(any("mystore.example.com/dashboard" in alt[0] for alt in email.alternatives))


@override_settings(WASSLA_BASE_DOMAIN="example.com")
class OnboardingPaymentCallbackTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="merchant2",
            email="merchant2@example.com",
            password="testpass123",
        )
        self.tenant = Tenant.objects.create(
            slug=f"tenant-{uuid.uuid4().hex[:6]}",
            name="Tenant Store",
            is_active=True,
            is_published=True,
        )
        self.store = Store.objects.create(
            owner=self.user,
            tenant=self.tenant,
            name="Demo Store",
            slug="demo-store",
            subdomain="demo-store",
            status=Store.STATUS_ACTIVE,
        )
        customer = Customer.objects.create(
            store_id=self.store.id,
            email="buyer@example.com",
            full_name="Buyer",
        )
        self.order = Order.objects.create(
            store_id=self.store.id,
            tenant_id=self.tenant.id,
            order_number=f"ORD-{uuid.uuid4().hex[:8]}",
            customer=customer,
            status=Order.STATUS_PENDING,
            payment_status="pending",
            total_amount=0,
        )

    def test_payment_callback_redirects_to_dashboard(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["payment_order_id"] = self.order.id
        session.save()

        response = self.client.get(reverse("subscriptions_web:onboarding_payment_callback"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://demo-store.example.com/dashboard/")


class SubdomainValidationTests(TestCase):
    def test_subdomain_rejects_invalid_characters(self):
        form = SubdomainSelectForm(data={"subdomain": "bad.email@example.com"})
        self.assertFalse(form.is_valid())
        self.assertIn("Use only letters, numbers, hyphen", form.errors["subdomain"][0])
