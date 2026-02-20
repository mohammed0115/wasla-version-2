from __future__ import annotations

from rest_framework import status
from rest_framework.views import APIView

from apps.cart.interfaces.api.responses import api_response
from apps.payments.application.use_cases.handle_webhook_event import (
    HandleWebhookEventCommand,
    HandleWebhookEventUseCase,
)
from apps.payments.application.use_cases.initiate_payment import (
    InitiatePaymentCommand,
    InitiatePaymentUseCase,
)
from apps.payments.interfaces.api.serializers import PaymentInitiateSerializer
from apps.tenants.domain.tenant_context import TenantContext
from apps.tenants.guards import require_store, require_tenant, require_merchant


def _build_tenant_context(request) -> TenantContext:
    store = require_store(request)
    tenant = require_tenant(request)
    tenant_id = tenant.id
    store_id = store.id
    currency = getattr(tenant, "currency", "SAR")
    if not request.session.session_key:
        request.session.save()
    session_key = request.session.session_key
    user_id = request.user.id if request.user.is_authenticated else None
    return TenantContext(
        tenant_id=tenant_id,
        store_id=store_id,
        currency=currency,
        user_id=user_id,
        session_key=session_key,
    )


def validate_signature(request) -> bool:
    """TODO: implement provider-specific signature verification for webhooks."""
    return True


class PaymentInitiateAPI(APIView):
    def post(self, request):
        require_store(request)
        require_merchant(request)
        serializer = PaymentInitiateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant_ctx = _build_tenant_context(request)
        try:
            result = InitiatePaymentUseCase.execute(
                InitiatePaymentCommand(
                    tenant_ctx=tenant_ctx,
                    order_id=serializer.validated_data["order_id"],
                    provider_code=serializer.validated_data["provider_code"],
                    return_url=serializer.validated_data["return_url"],
                )
            )
        except ValueError as exc:
            return api_response(success=False, errors=[str(exc)], status_code=status.HTTP_400_BAD_REQUEST)
        return api_response(
            success=True,
            data={
                "redirect_url": result.redirect_url,
                "client_secret": result.client_secret,
            },
            status_code=status.HTTP_201_CREATED,
        )


class PaymentWebhookAPI(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, provider_code: str):
        if not validate_signature(request):
            return api_response(
                success=False,
                errors=["invalid_signature"],
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        raw_body = request.body.decode("utf-8", errors="ignore") if request.body else ""
        payload = request.data if isinstance(request.data, dict) else {}
        headers = {str(k): str(v) for k, v in request.headers.items()}

        try:
            event = HandleWebhookEventUseCase.execute(
                HandleWebhookEventCommand(
                    provider_code=provider_code,
                    headers=headers,
                    payload=payload,
                    raw_body=raw_body,
                )
            )
        except ValueError as exc:
            return api_response(
                success=False,
                errors=[str(exc)],
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return api_response(
            success=True,
            data={
                "provider_code": event.provider_code,
                "event_id": event.event_id,
                "processing_status": event.processing_status,
            },
            status_code=status.HTTP_200_OK,
        )
