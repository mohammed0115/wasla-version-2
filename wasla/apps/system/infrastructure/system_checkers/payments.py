from __future__ import annotations

from apps.payments.application.facade import PaymentGatewayFacade
from apps.payments.models import PaymentProviderSettings
from apps.system.domain.go_live_checks.types import GoLiveCheckItem, LEVEL_P0, LEVEL_P1
from apps.tenants.models import StorePaymentSettings


class PaymentsReadinessChecker:
    category_key = "payments"
    category_label = "Payments readiness"

    def run(self) -> list[GoLiveCheckItem]:
        items: list[GoLiveCheckItem] = []

        providers = PaymentGatewayFacade.available_providers()
        items.append(
            GoLiveCheckItem(
                key="payments.gateway_registry",
                label="Payment gateway registry loaded",
                ok=bool(providers),
                level=LEVEL_P1,
                message="" if providers else "No payment gateway adapters are registered.",
                category=self.category_key,
            )
        )

        gateway_settings = StorePaymentSettings.objects.filter(
            is_enabled=True,
            mode=StorePaymentSettings.MODE_GATEWAY,
        )
        active_gateway_ok = PaymentProviderSettings.objects.filter(is_enabled=True).exists()
        items.append(
            GoLiveCheckItem(
                key="payments.active_gateway",
                label="At least one active payment gateway configured",
                ok=active_gateway_ok,
                level=LEVEL_P0,
                message=""
                if active_gateway_ok
                else "Configure at least one enabled gateway provider in payment settings.",
                category=self.category_key,
            )
        )

        webhook_ok = PaymentProviderSettings.objects.filter(is_enabled=True).exclude(webhook_secret="").exists()
        items.append(
            GoLiveCheckItem(
                key="payments.webhook_secret",
                label="Payment webhook secret configured",
                ok=webhook_ok,
                level=LEVEL_P1,
                message=""
                if webhook_ok
                else "Set webhook secret for at least one enabled gateway to verify callbacks.",
                category=self.category_key,
            )
        )

        return items
