from django.test import TestCase

from apps.payments.application.facade import PaymentGatewayFacade
from apps.payments.models import PaymentProviderSettings
from apps.tenants.models import StorePaymentSettings, Tenant


class ManualGatewayFacadeTests(TestCase):
    def test_manual_gateway_resolves_when_store_in_manual_mode(self):
        tenant = Tenant.objects.create(slug="manual-tenant", name="Manual Tenant", is_active=True)
        StorePaymentSettings.objects.create(
            tenant=tenant,
            mode=StorePaymentSettings.MODE_MANUAL,
            is_enabled=True,
        )
        PaymentProviderSettings.objects.create(
            tenant=tenant,
            provider_code="manual",
            is_enabled=True,
        )

        gateway = PaymentGatewayFacade.get("manual", tenant_id=tenant.id)
        self.assertEqual(gateway.code, "manual")
