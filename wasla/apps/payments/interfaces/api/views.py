from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.cart.interfaces.api.responses import api_response
from apps.payments.application.use_cases.initiate_payment import (
    InitiatePaymentCommand,
    InitiatePaymentUseCase,
)
from apps.payments.infrastructure.orchestrator import PaymentOrchestrator
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
    permission_classes = [AllowAny]

    def post(self, request, provider: str):
        if not PaymentOrchestrator.validate_webhook(provider=provider, request=request):
            return api_response(
                success=False,
                errors=["invalid_or_missing_webhook_secret"],
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = PaymentOrchestrator.process_webhook(provider=provider, request=request)
        except ValueError as exc:
            return api_response(
                success=False,
                errors=[str(exc)],
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return api_response(
            success=True,
            data=result,
            status_code=status.HTTP_200_OK,
        )
