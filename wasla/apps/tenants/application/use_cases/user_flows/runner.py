from __future__ import annotations

from django.test import Client

from .admin_flow import AdminFlowValidator
from .buyer_flow import BuyerFlowValidator
from .merchant_flow import MerchantFlowValidator
from .base import FlowReport


def run_all_flows(*, tenant_slug: str, client: Client | None = None) -> list[FlowReport]:
    resolved_client = client or Client()
    validators = [
        BuyerFlowValidator(),
        MerchantFlowValidator(),
        AdminFlowValidator(),
    ]
    return [validator.run(client=resolved_client, tenant_slug=tenant_slug) for validator in validators]

