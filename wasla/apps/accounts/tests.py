from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.accounts.application.usecases.resolve_onboarding_state import resolve_onboarding_state
from apps.subscriptions.models import StoreSubscription, SubscriptionPlan
from apps.tenants.models import StoreProfile, Tenant, TenantMembership


class ResolveOnboardingStateTests(TestCase):
	def setUp(self) -> None:
		super().setUp()
		self.factory = RequestFactory()
		self.user_model = get_user_model()

	def _request(self, path: str, user):
		request = self.factory.get(path)
		request.user = user
		middleware = SessionMiddleware(lambda req: None)
		middleware.process_request(request)
		request.session.save()
		return request

	def test_anonymous_goes_to_login_with_next(self):
		request = self._request("/dashboard/", AnonymousUser())
		target = resolve_onboarding_state(request)
		self.assertTrue(target.startswith("/auth/"))
		self.assertNotIn("next=", target)

	def test_persona_incomplete_goes_to_first_persona_step(self):
		user = self.user_model.objects.create_user(username="u1", password="pass12345")
		user.profile.persona_completed = False
		user.profile.save(update_fields=["persona_completed"])

		request = self._request("/dashboard/", user)
		target = resolve_onboarding_state(request)
		self.assertEqual(target, reverse("accounts:persona_welcome"))

	def test_persona_complete_without_tenant_goes_to_store_create(self):
		user = self.user_model.objects.create_user(username="u2", password="pass12345")
		user.profile.persona_completed = True
		user.profile.save(update_fields=["persona_completed"])

		request = self._request("/dashboard/", user)
		target = resolve_onboarding_state(request)
		self.assertEqual(target, reverse("tenants:store_create"))

	def test_with_tenant_without_plan_goes_to_plan_selection(self):
		user = self.user_model.objects.create_user(username="u-plan", password="pass12345")
		user.profile.persona_completed = True
		user.profile.save(update_fields=["persona_completed"])

		tenant = Tenant.objects.create(slug="u-plan-shop", name="Plan Shop", is_active=True)
		TenantMembership.objects.create(tenant=tenant, user=user, role=TenantMembership.ROLE_OWNER, is_active=True)
		StoreProfile.objects.create(tenant=tenant, owner=user, setup_step=1, is_setup_complete=False)

		request = self._request("/dashboard/", user)
		target = resolve_onboarding_state(request)
		self.assertEqual(target, reverse("accounts:persona_plans"))

	def test_incomplete_wizard_routes_to_payment(self):
		user = self.user_model.objects.create_user(username="u3", password="pass12345")
		user.profile.persona_completed = True
		user.profile.save(update_fields=["persona_completed"])

		tenant = Tenant.objects.create(slug="u3-shop", name="U3 Shop", is_active=True)
		TenantMembership.objects.create(tenant=tenant, user=user, role=TenantMembership.ROLE_OWNER, is_active=True)
		StoreProfile.objects.create(
			tenant=tenant,
			owner=user,
			store_info_completed=True,
			setup_step=2,
			is_setup_complete=False,
		)
		plan = SubscriptionPlan.objects.create(name="Basic", price=10, billing_cycle="monthly", is_active=True)
		StoreSubscription.objects.create(
			store_id=tenant.id,
			plan=plan,
			start_date=date.today() - timedelta(days=1),
			end_date=date.today() + timedelta(days=30),
			status="active",
		)

		request = self._request("/dashboard/", user)
		target = resolve_onboarding_state(request)
		self.assertEqual(target, reverse("tenants:dashboard_setup_payment"))

	def test_completed_flow_routes_to_dashboard(self):
		user = self.user_model.objects.create_user(username="u4", password="pass12345")
		user.profile.persona_completed = True
		user.profile.save(update_fields=["persona_completed"])

		tenant = Tenant.objects.create(slug="u4-shop", name="U4 Shop", is_active=True)
		TenantMembership.objects.create(tenant=tenant, user=user, role=TenantMembership.ROLE_OWNER, is_active=True)
		StoreProfile.objects.create(
			tenant=tenant,
			owner=user,
			store_info_completed=True,
			setup_step=4,
			is_setup_complete=True,
		)
		plan = SubscriptionPlan.objects.create(name="Pro", price=20, billing_cycle="monthly", is_active=True)
		StoreSubscription.objects.create(
			store_id=tenant.id,
			plan=plan,
			start_date=date.today() - timedelta(days=1),
			end_date=date.today() + timedelta(days=30),
			status="active",
		)

		request = self._request("/dashboard/", user)
		target = resolve_onboarding_state(request)
		self.assertEqual(target, "/dashboard/")
