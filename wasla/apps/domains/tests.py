from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.domains.models import DomainAlert, DomainHealth
from apps.domains.tasks import _check_single_domain, check_domain_health, classify_domain_status, renew_expiring_ssl
from apps.subscriptions.models import StoreSubscription, SubscriptionPlan
from apps.tenants.models import StoreDomain, StoreProfile, Tenant


class DomainMonitoringUnitTests(TestCase):
	def setUp(self):
		User = get_user_model()
		self.user = User.objects.create_user(username="merchant", password="pass123")
		self.tenant = Tenant.objects.create(name="Store A", slug="store-a", is_active=True)
		self.domain = StoreDomain.objects.create(
			tenant=self.tenant,
			domain="shop.example.com",
			status=StoreDomain.STATUS_SSL_ACTIVE,
		)

	def test_ssl_expiry_days_calculation(self):
		expires_at = timezone.now() + timedelta(days=10)
		health = DomainHealth.objects.create(
			store_domain=self.domain,
			tenant=self.tenant,
			dns_resolves=True,
			http_reachable=True,
			ssl_valid=True,
			ssl_expires_at=expires_at,
			status=DomainHealth.STATUS_WARNING,
		)
		self.assertIsNotNone(health.days_until_expiry)
		self.assertGreaterEqual(health.days_until_expiry, 9)
		self.assertLessEqual(health.days_until_expiry, 10)

	def test_status_classification_logic(self):
		self.assertEqual(
			classify_domain_status(dns_resolves=True, http_reachable=True, ssl_valid=True, days_until_expiry=45),
			DomainHealth.STATUS_HEALTHY,
		)
		self.assertEqual(
			classify_domain_status(dns_resolves=True, http_reachable=True, ssl_valid=True, days_until_expiry=10),
			DomainHealth.STATUS_WARNING,
		)
		self.assertEqual(
			classify_domain_status(dns_resolves=False, http_reachable=True, ssl_valid=True, days_until_expiry=10),
			DomainHealth.STATUS_ERROR,
		)

	@patch("apps.domains.tasks.DomainChecker.check_dns", return_value=True)
	@patch("apps.domains.tasks.DomainChecker.check_http", return_value=True)
	@patch("apps.domains.tasks.DomainChecker.check_ssl")
	def test_alert_creation_only_on_transition(self, mock_ssl, _mock_http, _mock_dns):
		mock_ssl.return_value = {
			"valid": True,
			"expires_at": timezone.now() + timedelta(days=20),
			"error": "",
		}

		_check_single_domain(self.domain)
		first_count = DomainAlert.objects.count()
		self.assertEqual(first_count, 1)

		_check_single_domain(self.domain)
		second_count = DomainAlert.objects.count()
		self.assertEqual(second_count, 1)


class DomainMonitoringIntegrationTests(TestCase):
	def setUp(self):
		self.tenant = Tenant.objects.create(name="Store B", slug="store-b", is_active=True)
		self.domain = StoreDomain.objects.create(
			tenant=self.tenant,
			domain="renew.example.com",
			status=StoreDomain.STATUS_SSL_ACTIVE,
			ssl_cert_path="/tmp/old-cert.pem",
			ssl_key_path="/tmp/old-key.pem",
		)
		self.health = DomainHealth.objects.create(
			store_domain=self.domain,
			tenant=self.tenant,
			dns_resolves=True,
			http_reachable=True,
			ssl_valid=True,
			ssl_expires_at=timezone.now() + timedelta(days=5),
			status=DomainHealth.STATUS_WARNING,
		)

	@patch("apps.domains.tasks._check_single_domain")
	@patch("apps.domains.tasks.SslRenewalService.renew")
	@patch("apps.domains.tasks.SslRenewalService.is_recently_renewed", return_value=False)
	def test_renewal_updates_health_and_avoids_duplicate_info_alerts(self, _recent, mock_renew, mock_recheck):
		mock_renew.return_value = {
			"success": True,
			"cert_path": "/tmp/new-cert.pem",
			"key_path": "/tmp/new-key.pem",
			"duration_ms": 120,
		}
		mock_recheck.return_value = {"domain": self.domain.domain, "status": DomainHealth.STATUS_HEALTHY}

		first = renew_expiring_ssl(domain_id=self.domain.id)
		self.assertEqual(first["errors"], 0)
		self.assertEqual(first["renewed"], 1)

		self.domain.refresh_from_db()
		self.assertEqual(self.domain.ssl_cert_path, "/tmp/new-cert.pem")
		self.assertEqual(self.domain.ssl_key_path, "/tmp/new-key.pem")

		second = renew_expiring_ssl(domain_id=self.domain.id)
		self.assertEqual(second["errors"], 0)

		info_alerts = DomainAlert.objects.filter(
			store_domain=self.domain,
			severity=DomainAlert.SEVERITY_INFO,
			message=f"SSL certificate renewed for {self.domain.domain}",
		)
		self.assertEqual(info_alerts.count(), 1)


class DomainMonitoringWebTests(TestCase):
	def setUp(self):
		User = get_user_model()
		self.admin = User.objects.create_user(username="admin", password="pass123", is_staff=True)
		self.merchant = User.objects.create_user(username="merchant-web", password="pass123")

		self.tenant = Tenant.objects.create(name="Store C", slug="store-c", is_active=True, is_published=True)
		self.domain = StoreDomain.objects.create(
			tenant=self.tenant,
			domain="web.example.com",
			status=StoreDomain.STATUS_SSL_ACTIVE,
		)
		DomainHealth.objects.create(
			store_domain=self.domain,
			tenant=self.tenant,
			dns_resolves=True,
			http_reachable=True,
			ssl_valid=True,
			ssl_expires_at=timezone.now() + timedelta(days=7),
			status=DomainHealth.STATUS_WARNING,
		)

		StoreProfile.objects.create(tenant=self.tenant, owner=self.merchant)
		plan = SubscriptionPlan.objects.create(name="Pro Plan", price=99)
		StoreSubscription.objects.create(
			store_id=self.tenant.id,
			plan=plan,
			start_date=timezone.now().date(),
			end_date=(timezone.now() + timedelta(days=30)).date(),
			status="active",
		)

	def test_admin_dashboard_renders_domain_status(self):
		self.client.force_login(self.admin)
		response = self.client.get(reverse("domains_web:domains_admin_dashboard"))
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "web.example.com")
		self.assertContains(response, "Warning")

	@patch("apps.tenants.interfaces.web.views.FeatureGateService.can_use_feature", return_value=True)
	def test_merchant_dashboard_shows_ssl_warning_banner(self, _feature_gate):
		self.client.force_login(self.merchant)
		response = self.client.get(reverse("tenants:dashboard_domains"))
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Your SSL expires in")

	@patch("apps.domains.tasks.DomainChecker.check_dns", return_value=True)
	@patch("apps.domains.tasks.DomainChecker.check_http", return_value=True)
	@patch("apps.domains.tasks.DomainChecker.check_ssl")
	def test_check_task_creates_no_duplicate_warning_alerts(self, mock_ssl, _http, _dns):
		DomainHealth.objects.filter(store_domain=self.domain).update(
			ssl_expires_at=timezone.now() + timedelta(days=45),
			status=DomainHealth.STATUS_HEALTHY,
			ssl_valid=True,
		)
		mock_ssl.return_value = {
			"valid": True,
			"expires_at": timezone.now() + timedelta(days=3),
			"error": "",
		}
		check_domain_health(domain_id=self.domain.id)
		check_domain_health(domain_id=self.domain.id)

		warning_alerts = DomainAlert.objects.filter(
			store_domain=self.domain,
			severity=DomainAlert.SEVERITY_WARNING,
			message__contains="expires in",
		)
		self.assertEqual(warning_alerts.count(), 1)
