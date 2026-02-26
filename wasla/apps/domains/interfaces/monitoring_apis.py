from __future__ import annotations

import json
import logging

from django.http import Http404
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.views import APIView

from apps.cart.interfaces.api.responses import api_response
from apps.tenants.guards import require_tenant
from apps.tenants.models import StoreDomain

from ..models import DomainAlert, DomainHealth
from ..tasks import check_domain_health, renew_expiring_ssl

logger = logging.getLogger("domain_monitoring")


def _serialize_health(health: DomainHealth | None) -> dict | None:
	if not health:
		return None
	return {
		"store_id": health.tenant_id,
		"domain_id": health.store_domain_id,
		"domain": health.store_domain.domain,
		"dns_resolves": health.dns_resolves,
		"http_reachable": health.http_reachable,
		"ssl_valid": health.ssl_valid,
		"ssl_expires_at": health.ssl_expires_at.isoformat() if health.ssl_expires_at else None,
		"days_until_expiry": health.days_until_expiry,
		"status": health.status,
		"last_error": health.last_error,
		"last_checked_at": health.last_checked_at.isoformat() if health.last_checked_at else None,
	}


def _serialize_alert(alert: DomainAlert) -> dict:
	return {
		"id": alert.id,
		"severity": alert.severity,
		"message": alert.message,
		"resolved": alert.resolved,
		"created_at": alert.created_at.isoformat() if alert.created_at else None,
	}


def _log_api(action: str, payload: dict):
	logger.info(json.dumps({"action": action, **payload}))


class AdminDomainListAPI(APIView):
	permission_classes = [IsAdminUser]

	def get(self, request):
		status_filter = (request.query_params.get("status") or "").strip().upper()
		domains = StoreDomain.objects.select_related("tenant", "health_status").all().order_by("domain")

		rows = []
		for domain in domains:
			health = getattr(domain, "health_status", None)
			effective_status = health.status if health else DomainHealth.STATUS_ERROR

			if status_filter == "EXPIRING_SOON":
				if not health or not health.is_expiring_soon:
					continue
			elif status_filter and status_filter in {"HEALTHY", "WARNING", "ERROR"}:
				if effective_status != status_filter:
					continue

			rows.append(
				{
					"id": domain.id,
					"store_id": domain.tenant_id,
					"store": domain.tenant.name,
					"domain": domain.domain,
					"status": effective_status,
					"days_until_expiry": health.days_until_expiry if health else None,
					"last_checked": health.last_checked_at.isoformat() if health and health.last_checked_at else None,
					"last_error": health.last_error if health else "Health has not been checked yet",
				}
			)

		_log_api("api_admin_domains_list", {"count": len(rows), "status_filter": status_filter})
		return api_response(success=True, data={"domains": rows})


class AdminDomainHealthDetailAPI(APIView):
	permission_classes = [IsAdminUser]

	def get(self, request, domain_id: int):
		domain = StoreDomain.objects.select_related("tenant").filter(id=domain_id).first()
		if not domain:
			return api_response(success=False, errors=["domain_not_found"], status_code=404)

		latest = DomainHealth.objects.filter(store_domain=domain).select_related("store_domain").first()
		history = list(
			DomainHealth.objects.filter(store_domain=domain)
			.select_related("store_domain")
			.order_by("-last_checked_at")[:30]
		)
		alerts = list(DomainAlert.objects.filter(store_domain=domain).order_by("-created_at")[:50])

		_log_api("api_admin_domain_health_detail", {"domain_id": domain_id, "store_id": domain.tenant_id})
		return api_response(
			success=True,
			data={
				"domain": {"id": domain.id, "name": domain.domain, "store_id": domain.tenant_id, "store": domain.tenant.name},
				"latest": _serialize_health(latest),
				"history": [_serialize_health(item) for item in history],
				"alerts": [_serialize_alert(item) for item in alerts],
			},
		)


class AdminDomainCheckAPI(APIView):
	permission_classes = [IsAdminUser]

	def post(self, request, domain_id: int):
		domain = StoreDomain.objects.filter(id=domain_id).first()
		if not domain:
			return api_response(success=False, errors=["domain_not_found"], status_code=404)

		check_domain_health.delay(domain_id=domain_id)
		_log_api("api_admin_domain_check_triggered", {"domain_id": domain_id, "store_id": domain.tenant_id})
		return api_response(success=True, data={"queued": True, "domain_id": domain_id})


class AdminDomainRenewAPI(APIView):
	permission_classes = [IsAdminUser]

	def post(self, request, domain_id: int):
		domain = StoreDomain.objects.filter(id=domain_id).first()
		if not domain:
			return api_response(success=False, errors=["domain_not_found"], status_code=404)

		renew_expiring_ssl.delay(domain_id=domain_id)
		_log_api("api_admin_domain_renew_triggered", {"domain_id": domain_id, "store_id": domain.tenant_id})
		return api_response(success=True, data={"queued": True, "domain_id": domain_id})


class MerchantDomainStatusAPI(APIView):
	permission_classes = [IsAuthenticated]

	def get(self, request):
		tenant = require_tenant(request)
		domain = StoreDomain.objects.filter(tenant=tenant).order_by("-created_at").first()
		if not domain:
			return api_response(success=True, data={"domain": None})

		health = DomainHealth.objects.filter(store_domain=domain).select_related("store_domain").first()
		warnings = []
		if health and health.status == DomainHealth.STATUS_WARNING and health.days_until_expiry is not None:
			warnings.append(f"Your SSL expires in {health.days_until_expiry} days")

		_log_api("api_merchant_domain_status", {"store_id": tenant.id, "domain_id": domain.id})
		return api_response(
			success=True,
			data={
				"domain": {
					"id": domain.id,
					"name": domain.domain,
					"status": health.status if health else DomainHealth.STATUS_ERROR,
					"ssl_valid": health.ssl_valid if health else False,
					"days_until_expiry": health.days_until_expiry if health else None,
					"last_checked": health.last_checked_at.isoformat() if health and health.last_checked_at else None,
					"warning_messages": warnings,
				}
			},
		)
