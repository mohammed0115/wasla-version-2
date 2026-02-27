from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Optional

try:
    from celery import shared_task
except Exception:  # pragma: no cover
    def shared_task(*_args, **_kwargs):
        def _decorator(func):
            func.delay = func
            return func
        return _decorator

from django.utils import timezone

from apps.tenants.models import StoreDomain
from .models import DomainAlert, DomainHealth
from .services.domain_checker import DomainChecker
from .services.ssl_renewal import SslRenewalService

logger = logging.getLogger("domain_monitoring")


def _log(action: str, payload: dict, *, level: str = "info") -> None:
    message = json.dumps({"action": action, **payload, "timestamp": timezone.now().isoformat()})
    getattr(logger, level)(message)


def classify_domain_status(*, dns_resolves: bool, http_reachable: bool, ssl_valid: bool, days_until_expiry: int | None) -> str:
    if not dns_resolves or not http_reachable or not ssl_valid:
        return DomainHealth.STATUS_ERROR
    if days_until_expiry is not None and days_until_expiry < 30:
        return DomainHealth.STATUS_WARNING
    return DomainHealth.STATUS_HEALTHY


@shared_task(bind=True, max_retries=3)
def check_domain_health(self, domain_id: Optional[int] = None) -> dict:
    try:
        query = StoreDomain.objects.filter(
            status__in=[
                StoreDomain.STATUS_ACTIVE,
                StoreDomain.STATUS_SSL_ACTIVE,
                StoreDomain.STATUS_VERIFIED,
            ]
        ).select_related("tenant")

        if domain_id:
            query = query.filter(id=domain_id)

        checked = 0
        errors = 0
        alerts_created = 0

        for store_domain in query.iterator():
            try:
                result = _check_single_domain(store_domain)
                checked += 1
                if result.get("alert_created"):
                    alerts_created += 1
            except Exception as exc:
                errors += 1
                _log(
                    "domain_health_check_error",
                    {
                        "domain": store_domain.domain,
                        "store_id": store_domain.tenant_id,
                        "error": str(exc),
                    },
                    level="error",
                )

        summary = {"checked": checked, "errors": errors, "alerts_created": alerts_created}
        _log("domain_health_check_complete", summary)
        return summary
    except Exception as exc:
        logger.exception("Unexpected error in check_domain_health")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


def _check_single_domain(store_domain: StoreDomain) -> dict:
    checker = DomainChecker(store_domain.domain)
    now = timezone.now()

    dns_resolves = checker.check_dns()
    http_reachable = checker.check_http()
    ssl_info = checker.check_ssl()

    ssl_valid = ssl_info.get("valid", False)
    ssl_expires_at = ssl_info.get("expires_at")
    days_until_expiry = (ssl_expires_at - now).days if ssl_expires_at else None
    status = classify_domain_status(
        dns_resolves=dns_resolves,
        http_reachable=http_reachable,
        ssl_valid=ssl_valid,
        days_until_expiry=days_until_expiry,
    )

    previous_status = (
        DomainHealth.objects.filter(store_domain=store_domain)
        .values_list("status", flat=True)
        .first()
    )

    health, _ = DomainHealth.objects.update_or_create(
        store_domain=store_domain,
        defaults={
            "tenant": store_domain.tenant,
            "dns_resolves": dns_resolves,
            "http_reachable": http_reachable,
            "ssl_valid": ssl_valid,
            "ssl_expires_at": ssl_expires_at,
            "status": status,
            "last_error": ssl_info.get("error") or "; ".join(checker.errors) or None,
            "last_checked_at": now,
        },
    )

    _log(
        "domain_health_check",
        {
            "store_id": store_domain.tenant_id,
            "domain": store_domain.domain,
            "dns_resolves": dns_resolves,
            "http_reachable": http_reachable,
            "ssl_valid": ssl_valid,
            "days_until_expiry": health.days_until_expiry,
            "status": health.status,
        },
    )

    alert_created = _create_transition_alert_if_needed(
        health=health,
        previous_status=previous_status,
        dns_resolves=dns_resolves,
        http_reachable=http_reachable,
    )

    return {"domain": store_domain.domain, "status": health.status, "alert_created": alert_created}


def _create_transition_alert_if_needed(
    *,
    health: DomainHealth,
    previous_status: str | None,
    dns_resolves: bool,
    http_reachable: bool,
) -> bool:
    if previous_status == health.status:
        return False

    domain = health.store_domain.domain
    if health.status == DomainHealth.STATUS_ERROR:
        if not dns_resolves:
            message = f"Domain {domain} DNS resolution failed"
            resolution = "Check DNS records and nameservers."
        elif not http_reachable:
            message = f"Domain {domain} HTTP endpoint unreachable"
            resolution = "Verify origin service and reverse proxy health."
        else:
            message = f"Domain {domain} SSL certificate invalid"
            resolution = health.last_error or "Validate certificate chain and renewal job logs."

        DomainAlert.create_from_health(
            health,
            DomainAlert.SEVERITY_CRITICAL,
            message,
            resolution,
        )
        return True

    if health.status == DomainHealth.STATUS_WARNING and health.is_expiring_soon:
        DomainAlert.create_from_health(
            health,
            DomainAlert.SEVERITY_WARNING,
            f"SSL certificate for {domain} expires in {health.days_until_expiry} days",
            "Automatic renewal is scheduled daily. Monitor renewal logs.",
        )
        return True

    return False


@shared_task(bind=True, max_retries=3)
def renew_expiring_ssl(self, domain_id: Optional[int] = None) -> dict:
    try:
        query = DomainHealth.objects.filter(
            ssl_valid=True,
            days_until_expiry__isnull=False,
            days_until_expiry__lt=30,
            days_until_expiry__gte=0,
        ).select_related("store_domain__tenant")

        if domain_id:
            query = query.filter(store_domain_id=domain_id)

        renewed = 0
        skipped = 0
        errors = 0

        for health in query.iterator():
            result = _renew_single_domain_ssl(health)
            if result.get("skipped"):
                skipped += 1
            elif result.get("success"):
                renewed += 1
            else:
                errors += 1

        summary = {"renewed": renewed, "skipped": skipped, "errors": errors}
        _log("ssl_renewal_complete", summary)
        return summary
    except Exception as exc:
        logger.exception("Unexpected error in renew_expiring_ssl")
        raise self.retry(exc=exc, countdown=300 * (2 ** self.request.retries))


def _renew_single_domain_ssl(health: DomainHealth) -> dict:
    store_domain = health.store_domain
    domain = store_domain.domain
    start_time = timezone.now()

    renewal_service = SslRenewalService(store_domain)
    if renewal_service.is_recently_renewed():
        _log("ssl_renewal_skipped", {"store_id": store_domain.tenant_id, "domain": domain, "success": True})
        return {"success": True, "skipped": True}

    result = renewal_service.renew()
    duration_ms = result.get("duration_ms") or int((timezone.now() - start_time).total_seconds() * 1000)
    success = bool(result.get("success"))

    if success:
        store_domain.ssl_cert_path = result.get("cert_path") or store_domain.ssl_cert_path
        store_domain.ssl_key_path = result.get("key_path") or store_domain.ssl_key_path
        store_domain.status = StoreDomain.STATUS_SSL_ACTIVE
        store_domain.save(update_fields=["ssl_cert_path", "ssl_key_path", "status"])

        latest = _check_single_domain(store_domain)
        latest_health = DomainHealth.objects.filter(store_domain=store_domain).first()
        expiry_text = "unknown"
        if latest_health and latest_health.ssl_expires_at:
            expiry_text = latest_health.ssl_expires_at.strftime("%Y-%m-%d")

        DomainAlert.create_for_domain(
            store_domain=store_domain,
            tenant=store_domain.tenant,
            severity=DomainAlert.SEVERITY_INFO,
            message=f"SSL certificate renewed for {domain}",
            resolution_text=f"New certificate valid until {expiry_text}",
        )

        _log(
            "ssl_renewal",
            {
                "store_id": store_domain.tenant_id,
                "domain": domain,
                "success": True,
                "duration_ms": duration_ms,
                "status": latest.get("status"),
            },
        )
        return {"success": True, "duration_ms": duration_ms}

    error_text = result.get("error") or "Unknown renewal error"
    DomainAlert.create_for_domain(
        store_domain=store_domain,
        tenant=store_domain.tenant,
        severity=DomainAlert.SEVERITY_CRITICAL,
        message=f"Automatic SSL renewal failed for {domain}",
        resolution_text=error_text,
    )

    _log(
        "ssl_renewal",
        {
            "store_id": store_domain.tenant_id,
            "domain": domain,
            "success": False,
            "duration_ms": duration_ms,
            "error": error_text,
        },
        level="error",
    )
    return {"success": False, "error": error_text, "duration_ms": duration_ms}
