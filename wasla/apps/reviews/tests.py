from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from apps.catalog.models import Product
from apps.customers.models import Customer
from apps.reviews.models import Review
from apps.stores.models import Store
from apps.tenants.models import Tenant, TenantMembership


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", ".localhost"])
class ReviewsModerationApiTests(TestCase):
	def setUp(self) -> None:
		super().setUp()
		call_command("seed_permissions")

		user_model = get_user_model()
		self.owner = user_model.objects.create_user(
			username="reviews-owner",
			password="pass12345",
			email="owner@example.com",
		)
		self.manager = user_model.objects.create_user(
			username="reviews-manager",
			password="pass12345",
			email="manager@example.com",
		)
		self.read_only = user_model.objects.create_user(
			username="reviews-readonly",
			password="pass12345",
			email="readonly@example.com",
		)

		self.tenant = Tenant.objects.create(slug="reviews-tenant", name="Reviews Tenant", is_active=True)
		self.store = Store.objects.create(
			owner=self.owner,
			tenant=self.tenant,
			name="Reviews Store",
			slug="reviews-store",
			subdomain="reviews-store",
			status=Store.STATUS_ACTIVE,
			country="SA",
		)

		TenantMembership.objects.create(
			tenant=self.tenant,
			user=self.owner,
			role=TenantMembership.ROLE_OWNER,
			is_active=True,
		)
		TenantMembership.objects.create(
			tenant=self.tenant,
			user=self.manager,
			role=TenantMembership.ROLE_ADMIN,
			is_active=True,
		)
		TenantMembership.objects.create(
			tenant=self.tenant,
			user=self.read_only,
			role=TenantMembership.ROLE_READ_ONLY,
			is_active=True,
		)

		self.product = Product.objects.create(
			store_id=self.store.id,
			sku="REV-001",
			name="Review Product",
			price="10.00",
			is_active=True,
		)
		self.customer = Customer.objects.create(
			store_id=self.store.id,
			email="buyer@example.com",
			full_name="Buyer",
			group="retail",
			is_active=True,
		)

		self.pending_review = Review.objects.create(
			product=self.product,
			customer=self.customer,
			rating=5,
			comment="pending review",
			status="pending",
		)
		self.approved_review = Review.objects.create(
			product=self.product,
			customer=self.customer,
			rating=4,
			comment="approved review",
			status="approved",
		)

	def test_manager_can_list_pending_reviews(self):
		self.client.force_login(self.manager)
		response = self.client.get(
			"/api/reviews/moderation/pending/",
			HTTP_HOST="reviews-store.localhost",
		)
		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(len(payload), 1)
		self.assertEqual(payload[0]["id"], self.pending_review.id)

	def test_read_only_cannot_access_pending_reviews(self):
		self.client.force_login(self.read_only)
		response = self.client.get(
			"/api/reviews/moderation/pending/",
			HTTP_HOST="reviews-store.localhost",
		)
		self.assertEqual(response.status_code, 403)

	def test_manager_can_approve_review(self):
		self.client.force_login(self.manager)
		response = self.client.patch(
			f"/api/reviews/moderation/{self.pending_review.id}/",
			data={"status": "approved"},
			content_type="application/json",
			HTTP_HOST="reviews-store.localhost",
		)
		self.assertEqual(response.status_code, 200)
		self.pending_review.refresh_from_db()
		self.assertEqual(self.pending_review.status, "approved")

	def test_public_product_reviews_returns_only_approved(self):
		self.client.force_login(self.manager)
		response = self.client.get(
			f"/api/products/{self.product.id}/reviews/",
			HTTP_HOST="reviews-store.localhost",
		)
		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(len(payload), 1)
		self.assertEqual(payload[0]["id"], self.approved_review.id)
