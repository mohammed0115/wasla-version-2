from __future__ import annotations

import os

from django.conf import settings

from tenants.models import StoreDomain

from tenants.application.use_cases.refresh_ssl_certificate import (
    RefreshSSLCertificateCommand,
    RefreshSSLCertificateUseCase,
)
from tenants.application.use_cases.verify_domain_ownership import (
    VerifyDomainOwnershipCommand,
    VerifyDomainOwnershipUseCase,
)


def _verify_domain_now(*, domain_id: int) -> None:
    try:
        VerifyDomainOwnershipUseCase.execute(
            VerifyDomainOwnershipCommand(
                actor=None,
                domain_id=domain_id,
                activate_on_success=True,
                skip_ownership_check=True,
            )
        )
    except Exception:
        # best-effort background task; failures are reflected on domain status
        return


def enqueue_verify_domain(*, domain_id: int) -> None:
    provisioning_mode = (getattr(settings, "DOMAIN_PROVISIONING_MODE", "manual") or "manual").lower()
    if provisioning_mode == "manual":
        StoreDomain.objects.filter(id=domain_id).update(status=StoreDomain.STATUS_PENDING_VERIFICATION)
        return
    eager = (
        getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False)
        or os.getenv("CELERY_TASK_ALWAYS_EAGER", "").strip().lower() in ("1", "true", "yes")
    )
    broker_url = (getattr(settings, "CELERY_BROKER_URL", "") or os.getenv("CELERY_BROKER_URL", "")).strip()
    try:
        from celery import shared_task  # noqa: F401
    except Exception:
        _verify_domain_now(domain_id=domain_id)
        return

    if eager or not broker_url:
        _verify_domain_now(domain_id=domain_id)
        return

    try:
        verify_domain_task.delay(domain_id=domain_id)
    except Exception:
        _verify_domain_now(domain_id=domain_id)


def _refresh_ssl_now(*, domain_id: int) -> None:
    try:
        RefreshSSLCertificateUseCase.execute(
            RefreshSSLCertificateCommand(
                actor=None,
                domain_id=domain_id,
                skip_ownership_check=True,
            )
        )
    except Exception:
        return


def enqueue_refresh_ssl(*, domain_id: int) -> None:
    provisioning_mode = (getattr(settings, "DOMAIN_PROVISIONING_MODE", "manual") or "manual").lower()
    if provisioning_mode == "manual":
        StoreDomain.objects.filter(id=domain_id).update(status=StoreDomain.STATUS_SSL_PENDING)
        return
    eager = (
        getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False)
        or os.getenv("CELERY_TASK_ALWAYS_EAGER", "").strip().lower() in ("1", "true", "yes")
    )
    broker_url = (getattr(settings, "CELERY_BROKER_URL", "") or os.getenv("CELERY_BROKER_URL", "")).strip()
    try:
        from celery import shared_task  # noqa: F401
    except Exception:
        _refresh_ssl_now(domain_id=domain_id)
        return

    if eager or not broker_url:
        _refresh_ssl_now(domain_id=domain_id)
        return

    try:
        refresh_ssl_task.delay(domain_id=domain_id)
    except Exception:
        _refresh_ssl_now(domain_id=domain_id)


try:
    from celery import shared_task
except Exception:  # pragma: no cover
    shared_task = None


if shared_task:

    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_backoff=True,
        retry_backoff_max=300,
        retry_jitter=True,
        retry_kwargs={"max_retries": 5},
    )
    def verify_domain_task(self, *, domain_id: int):
        _verify_domain_now(domain_id=domain_id)

    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_backoff=True,
        retry_backoff_max=300,
        retry_jitter=True,
        retry_kwargs={"max_retries": 5},
    )
    def refresh_ssl_task(self, *, domain_id: int):
        _refresh_ssl_now(domain_id=domain_id)
