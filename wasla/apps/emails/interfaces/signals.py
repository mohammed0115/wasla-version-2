from __future__ import annotations

import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.customers.models import Customer
from apps.orders.models import Order

from apps.emails.application.use_cases.send_order_confirmation_email import (
    SendOrderConfirmationEmailCommand,
    SendOrderConfirmationEmailUseCase,
)
from apps.emails.application.use_cases.send_welcome_email import SendWelcomeEmailCommand, SendWelcomeEmailUseCase
from apps.emails.application.services.provider_resolver import EmailProviderNotConfigured

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Customer)
def _send_welcome_email_on_customer_created(sender, instance: Customer, created: bool, **kwargs):
    if not created:
        return
    try:
        SendWelcomeEmailUseCase.execute(
            SendWelcomeEmailCommand(
                tenant_id=instance.store_id,
                to_email=instance.email,
                full_name=getattr(instance, "full_name", "") or "",
            )
        )
    except EmailProviderNotConfigured as exc:
        logger.warning("Email not sent (welcome): %s", exc)


@receiver(pre_save, sender=Order)
def _order_pre_save(sender, instance: Order, **kwargs):
    if instance.pk:
        instance._pre_save_status = Order.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
    else:
        instance._pre_save_status = None


@receiver(post_save, sender=Order)
def _send_order_confirmation_on_paid(sender, instance: Order, created: bool, **kwargs):
    old_status = getattr(instance, "_pre_save_status", None)
    if old_status == instance.status:
        return
    if instance.status != "paid":
        return

    customer = instance.customer
    try:
        SendOrderConfirmationEmailUseCase.execute(
            SendOrderConfirmationEmailCommand(
                tenant_id=instance.store_id,
                to_email=customer.email,
                order_number=instance.order_number,
                total_amount=str(instance.total_amount),
            )
        )
    except EmailProviderNotConfigured as exc:
        logger.warning("Email not sent (order confirmation): %s", exc)
