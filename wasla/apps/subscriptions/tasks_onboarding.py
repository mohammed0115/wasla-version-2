"""
Async tasks for onboarding-related notifications.
"""

from __future__ import annotations

from celery import shared_task


@shared_task(bind=True, max_retries=3)
def send_store_welcome_email_task(self, store_id: int, to_email: str) -> bool:
    from apps.subscriptions.services.onboarding_utils import _send_store_welcome_email

    _send_store_welcome_email(store_id, to_email)
    return True

