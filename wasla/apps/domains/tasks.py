"""
Domain monitoring and SSL renewal tasks for Celery.

Tasks:
- check_domain_health: Check DNS, HTTP, and SSL status for all active domains
- renew_expiring_ssl: Automatically renew SSL certificates expiring within 30 days
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from celery import shared_task
from django.utils import timezone

from apps.tenants.models import StoreDomain, Tenant
from .models import DomainAlert, DomainHealth
from .services.domain_checker import DomainChecker
from .services.ssl_renewal import SslRenewalService

logger = logging.getLogger("domain_monitoring")


@shared_task(bind=True, max_retries=3)
def check_domain_health(self, domain_id: Optional[int] = None) -> dict:
    """
    Check health status of domains (DNS, HTTP, SSL).

    Args:
        domain_id: If provided, check only this domain. Otherwise check all active domains.

    Returns:
        dict: Summary of checks performed
    """
    try:
        # Determine which domains to check
        query = StoreDomain.objects.filter(status__in=[
            StoreDomain.STATUS_ACTIVE,
            StoreDomain.STATUS_SSL_ACTIVE,
            StoreDomain.STATUS_VERIFIED,
        ])

        if domain_id:
            query = query.filter(id=domain_id)

        domains = list(query.select_related("tenant"))

        if not domains:
            return {"checked": 0, "errors": 0, "message": "No active domains to check"}

        checked_count = 0
        error_count = 0
        alerts_created = 0

        for store_domain in domains:
            try:
                result = _check_single_domain(store_domain)
                checked_count += 1

                if result.get("alert_created"):
                    alerts_created += 1

            except Exception as e:
                logger.exception(f"Error checking domain {store_domain.domain}: {str(e)}")
                error_count += 1

                # Log structured error
                logger.error(json.dumps({
                    "action": "domain_health_check_error",
                    "domain": store_domain.domain,
                    "store_id": store_domain.tenant_id,
                    "error": str(e),
                    "timestamp": timezone.now().isoformat(),
                }))

        summary = {
            "checked": checked_count,
            "errors": error_count,
            "alerts_created": alerts_created,
            "timestamp": timezone.now().isoformat(),
        }

        logger.info(json.dumps({
            "action": "domain_health_check_complete",
            **summary
        }))

        return summary

    except Exception as exc:
        logger.exception(f"Unexpected error in check_domain_health: {str(exc)}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


def _check_single_domain(store_domain: StoreDomain) -> dict:
    """
    Check a single domain's health.

    Returns:
        dict: Result with health data and alert creation status
    """
    tenant = store_domain.tenant
    domain = store_domain.domain

    checker = DomainChecker(domain)

    # Perform health checks
    dns_resolves = checker.check_dns()
    http_reachable = checker.check_http()
    ssl_info = checker.check_ssl()

    ssl_valid = ssl_info.get("valid", False)
    ssl_expires_at = ssl_info.get("expires_at")
    last_error = ssl_info.get("error", "")

    # Determine status
    if not dns_resolves or not http_reachable:
        status = DomainHealth.STATUS_ERROR
    elif not ssl_valid:
        status = DomainHealth.STATUS_ERROR
    elif ssl_expires_at and (ssl_expires_at - timezone.now()).days <= 30:
        status = DomainHealth.STATUS_WARNING
    else:
        status = DomainHealth.STATUS_HEALTHY

    # Get or create health record
    health, created = DomainHealth.objects.update_or_create(
        store_domain=store_domain,
        defaults={
            "tenant": tenant,
            "dns_resolves": dns_resolves,
            "http_reachable": http_reachable,
            "ssl_valid": ssl_valid,
            "ssl_expires_at": ssl_expires_at,
            "status": status,
            "last_error": last_error,
            "last_checked_at": timezone.now(),
        }
    )

    # Log health check
    logger.info(json.dumps({
        "action": "domain_health_check",
        "domain": domain,
        "store_id": tenant.id,
        "dns_resolves": dns_resolves,
        "http_reachable": http_reachable,
        "ssl_valid": ssl_valid,
        "days_until_expiry": health.days_until_expiry,
        "status": status,
        "timestamp": timezone.now().isoformat(),
    }))

    alert_created = False

    # Create alerts if needed
    if status == DomainHealth.STATUS_ERROR:
        if not dns_resolves:
            message = f"Domain {domain} DNS resolution failed"
            resolution = "Check DNS configuration and ensure nameservers point to correct IP"
        elif not http_reachable:
            message = f"Domain {domain} HTTP endpoint unreachable"
            resolution = "Verify the domain resolves and web server is running"
        else:
            message = f"Domain {domain} SSL certificate is invalid"
            resolution = f"Error: {last_error}. Check certificate and renewal status."

        DomainAlert.create_from_health(
            health,
            DomainAlert.SEVERITY_CRITICAL,
            message,
            resolution,
        )
        alert_created = True

    elif status == DomainHealth.STATUS_WARNING and health.is_expiring_soon:
        message = f"SSL certificate for {domain} expires in {health.days_until_expiry} days"
        resolution = "Automatic renewal should happen within 7 days. Monitor for renewal."
        DomainAlert.create_from_health(
            health,
            DomainAlert.SEVERITY_WARNING,
            message,
            resolution,
        )
        alert_created = True

    return {
        "domain": domain,
        "status": status,
        "alert_created": alert_created,
    }


@shared_task(bind=True, max_retries=3)
def renew_expiring_ssl(self) -> dict:
    """
    Automatically renew SSL certificates expiring within 30 days.

    Returns:
        dict: Summary of renewal operations
    """
    try:
        # Find domains with expiring SSL certificates
        expiring_domains = DomainHealth.objects.filter(
            status__in=[DomainHealth.STATUS_WARNING, DomainHealth.STATUS_HEALTHY],
            ssl_valid=True,
        ).filter(
            ssl_expires_at__lte=timezone.now() + timedelta(days=30),
            ssl_expires_at__gt=timezone.now(),
        ).select_related("store_domain__tenant")

        if not expiring_domains.exists():
            logger.info("No domains with expiring SSL certificates found")
            return {"renewed": 0, "errors": 0, "message": "No domains need renewal"}

        renewed_count = 0
        error_count = 0

        for health in expiring_domains:
            try:
                result = _renew_single_domain_ssl(health)
                if result.get("success"):
                    renewed_count += 1
                else:
                    error_count += 1

            except Exception as e:
                logger.exception(f"Error renewing SSL for {health.store_domain.domain}: {str(e)}")
                error_count += 1

                # Create critical alert
                DomainAlert.create_from_health(
                    health,
                    DomainAlert.SEVERITY_CRITICAL,
                    f"Automatic SSL renewal failed for {health.store_domain.domain}",
                    f"Manual intervention required. Error: {str(e)}",
                )

        summary = {
            "renewed": renewed_count,
            "errors": error_count,
            "timestamp": timezone.now().isoformat(),
        }

        logger.info(json.dumps({
            "action": "ssl_renewal_complete",
            **summary
        }))

        return summary

    except Exception as exc:
        logger.exception(f"Unexpected error in renew_expiring_ssl: {str(exc)}")
        raise self.retry(exc=exc, countdown=300 * (2 ** self.request.retries))


def _renew_single_domain_ssl(health: DomainHealth) -> dict:
    """
    Renew SSL certificate for a single domain.

    Returns:
        dict: Result with success status and details
    """
    store_domain = health.store_domain
    domain = store_domain.domain
    tenant = store_domain.tenant

    start_time = timezone.now()

    try:
        # Initialize renewal service
        renewal_service = SslRenewalService(store_domain)

        # Check if already renewed recently (idempotency)
        if renewal_service.is_recently_renewed():
            logger.info(f"SSL renewal skipped for {domain} (already renewed within 24 hours)")
            return {"success": True, "message": "Already recently renewed"}

        # Perform renewal
        renewal_result = renewal_service.renew()

        if not renewal_result.get("success"):
            logger.error(f"SSL renewal failed for {domain}: {renewal_result.get('error')}")
            return {"success": False, "error": renewal_result.get("error")}

        # Update domain with new certificate paths
        store_domain.ssl_cert_path = renewal_result.get("cert_path", "")
        store_domain.ssl_key_path = renewal_result.get("key_path", "")
        store_domain.status = StoreDomain.STATUS_SSL_ACTIVE
        store_domain.save()

        # Re-check health
        new_health = _check_single_domain(store_domain)

        duration_ms = int((timezone.now() - start_time).total_seconds() * 1000)

        # Create info alert about successful renewal
        DomainAlert.create_from_health(
            health,
            DomainAlert.SEVERITY_INFO,
            f"SSL certificate renewed for {domain}",
            f"New certificate valid until {health.ssl_expires_at.strftime('%Y-%m-%d')}",
        )

        logger.info(json.dumps({
            "action": "ssl_renewal_success",
            "domain": domain,
            "store_id": tenant.id,
            "duration_ms": duration_ms,
            "new_expiry": health.ssl_expires_at.isoformat() if health.ssl_expires_at else None,
            "timestamp": timezone.now().isoformat(),
        }))

        return {"success": True, "duration_ms": duration_ms}

    except Exception as e:
        duration_ms = int((timezone.now() - start_time).total_seconds() * 1000)

        logger.error(json.dumps({
            "action": "ssl_renewal_error",
            "domain": domain,
            "store_id": tenant.id,
            "error": str(e),
            "duration_ms": duration_ms,
            "timestamp": timezone.now().isoformat(),
        }))

        return {"success": False, "error": str(e), "duration_ms": duration_ms}
