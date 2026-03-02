"""
Shared onboarding helpers for store URL building, domain mapping, and welcome emails.
"""

from __future__ import annotations

import importlib.util
import logging
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string

from apps.stores.models import Store
from apps.tenants.models import StoreDomain

logger = logging.getLogger(__name__)


def get_base_domain() -> str:
    return (getattr(settings, "WASSLA_BASE_DOMAIN", "w-sala.com") or "w-sala.com").strip().lower()


def build_store_host(subdomain: str) -> str:
    normalized = (subdomain or "").strip().lower()
    if not normalized:
        return ""
    return f"{normalized}.{get_base_domain()}"


def build_store_dashboard_url(subdomain: str) -> str:
    host = build_store_host(subdomain)
    if not host:
        return ""
    return f"https://{host}/dashboard/"


def ensure_store_domain_mapping(store: Store) -> StoreDomain | None:
    if not store or not store.subdomain:
        return None

    host = build_store_host(store.subdomain)
    if not host:
        return None

    status_active = getattr(StoreDomain, "STATUS_ACTIVE", "active")
    status_pending = getattr(StoreDomain, "STATUS_PENDING_VERIFICATION", "pending_verification")
    desired_status = status_active if store.status == Store.STATUS_ACTIVE else status_pending

    try:
        domain, created = StoreDomain.objects.get_or_create(
            domain=host,
            defaults={
                "tenant": store.tenant,
                "store": store,
                "status": desired_status,
                "is_primary": True,
                "verification_token": StoreDomain.generate_verification_token(),
            },
        )
        if not created:
            updates: dict[str, object] = {}
            if domain.store_id is None:
                updates["store_id"] = store.id
            if domain.tenant_id is None and store.tenant_id:
                updates["tenant_id"] = store.tenant_id
            if not domain.verification_token:
                updates["verification_token"] = StoreDomain.generate_verification_token()
            if store.status == Store.STATUS_ACTIVE and domain.status != status_active:
                updates["status"] = status_active
            if domain.is_primary is False:
                updates["is_primary"] = True
            if updates:
                StoreDomain.objects.filter(id=domain.id).update(**updates)
        return domain
    except Exception as exc:
        logger.exception("Failed to ensure store domain mapping for store %s", store.id, exc_info=exc)
        return None


def send_store_welcome_email(*, store: Store, to_email: str) -> None:
    if not store or not to_email:
        return

    support_email = (getattr(settings, "WASSLA_SUPPORT_EMAIL", "info@w-sala.com") or "info@w-sala.com").strip()
    dashboard_url = build_store_dashboard_url(store.subdomain)

    context = {
        "store_name": store.name,
        "dashboard_url": dashboard_url,
        "support_email": support_email,
    }

    try:
        subject = render_to_string("emails/store_welcome.subject.txt", context).strip()
        text_body = render_to_string("emails/store_welcome.txt", context)
        html_body = render_to_string("emails/store_welcome.html", context)

        from_email = (
            getattr(settings, "DEFAULT_FROM_EMAIL", "")
            or getattr(settings, "SERVER_EMAIL", "")
            or support_email
        )

        message = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=from_email,
            to=[to_email],
        )
        if html_body:
            message.attach_alternative(html_body, "text/html")
        message.send(fail_silently=False)
    except Exception as exc:
        logger.exception("Failed to send store welcome email for store %s", store.id, exc_info=exc)


def _send_store_welcome_email(store_id: int, to_email: str) -> None:
    store = Store.objects.filter(id=store_id).first()
    if not store:
        logger.warning("Store %s not found for welcome email", store_id)
        return
    send_store_welcome_email(store=store, to_email=to_email)


def _celery_available() -> bool:
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        return True
    broker_url = (getattr(settings, "CELERY_BROKER_URL", "") or "").strip()
    if not broker_url:
        return False
    return importlib.util.find_spec("celery") is not None


def enqueue_store_welcome_email(*, store: Store, to_email: str) -> None:
    if not store or not to_email:
        return

    def _dispatch() -> None:
        try:
            if not getattr(settings, "WASSLA_EMAIL_ASYNC_ENABLED", True):
                _send_store_welcome_email(store.id, to_email)
                return

            if _celery_available():
                try:
                    from apps.subscriptions.tasks_onboarding import send_store_welcome_email_task

                    send_store_welcome_email_task.delay(store.id, to_email)
                    return
                except Exception as exc:
                    logger.exception("Celery enqueue failed for welcome email", exc_info=exc)

            thread = threading.Thread(
                target=_send_store_welcome_email,
                args=(store.id, to_email),
                daemon=True,
            )
            thread.start()
        except Exception as exc:
            logger.exception("Failed to dispatch welcome email", exc_info=exc)

    transaction.on_commit(_dispatch)

