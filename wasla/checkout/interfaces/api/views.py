from __future__ import annotations

from rest_framework import status
from rest_framework.views import APIView

from cart.interfaces.api.responses import api_response
from checkout.application.use_cases.create_order_from_checkout import (
    CreateOrderFromCheckoutCommand,
    CreateOrderFromCheckoutUseCase,
)
from checkout.application.use_cases.save_shipping_address import (
    SaveShippingAddressCommand,
    SaveShippingAddressUseCase,
)
from checkout.application.use_cases.select_shipping_method import (
    SelectShippingMethodCommand,
    SelectShippingMethodUseCase,
)
from checkout.application.use_cases.start_checkout import StartCheckoutCommand, StartCheckoutUseCase
from checkout.domain.errors import CheckoutError, InvalidCheckoutStateError
from checkout.interfaces.api.serializers import (
    CheckoutAddressSerializer,
    CheckoutOrderSerializer,
    CheckoutShippingSerializer,
)
from tenants.domain.tenant_context import TenantContext


def _build_tenant_context(request) -> TenantContext:
    tenant = getattr(request, "tenant", None)
    tenant_id = getattr(tenant, "id", None)
    currency = getattr(tenant, "currency", "SAR")
    if not tenant_id:
        raise CheckoutError("Tenant context is required.")
    if not request.session.session_key:
        request.session.save()
    session_key = request.session.session_key
    user_id = request.user.id if request.user.is_authenticated else None
    return TenantContext(tenant_id=tenant_id, currency=currency, user_id=user_id, session_key=session_key)


class CheckoutStartAPI(APIView):
    def post(self, request):
        tenant_ctx = _build_tenant_context(request)
        try:
            session = StartCheckoutUseCase.execute(StartCheckoutCommand(tenant_ctx=tenant_ctx))
        except CheckoutError as exc:
            return api_response(success=False, errors=[str(exc)], status_code=status.HTTP_409_CONFLICT)
        return api_response(success=True, data={"session_id": session.id, "current_step": session.status})


class CheckoutAddressAPI(APIView):
    def post(self, request):
        serializer = CheckoutAddressSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant_ctx = _build_tenant_context(request)
        try:
            session = SaveShippingAddressUseCase.execute(
                SaveShippingAddressCommand(
                    tenant_ctx=tenant_ctx,
                    session_id=serializer.validated_data["session_id"],
                    address={
                        "full_name": serializer.validated_data["full_name"],
                        "email": serializer.validated_data["email"],
                        "phone": serializer.validated_data["phone"],
                        "line1": serializer.validated_data["line1"],
                        "city": serializer.validated_data["city"],
                        "country": serializer.validated_data["country"],
                    },
                )
            )
        except InvalidCheckoutStateError as exc:
            return api_response(success=False, errors=[str(exc)], status_code=status.HTTP_409_CONFLICT)
        return api_response(success=True, data={"session_id": session.id, "current_step": session.status})


class CheckoutShippingAPI(APIView):
    def post(self, request):
        serializer = CheckoutShippingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant_ctx = _build_tenant_context(request)
        try:
            session = SelectShippingMethodUseCase.execute(
                SelectShippingMethodCommand(
                    tenant_ctx=tenant_ctx,
                    session_id=serializer.validated_data["session_id"],
                    method_code=serializer.validated_data["method_code"],
                )
            )
        except InvalidCheckoutStateError as exc:
            return api_response(success=False, errors=[str(exc)], status_code=status.HTTP_409_CONFLICT)
        return api_response(
            success=True,
            data={
                "session_id": session.id,
                "current_step": session.status,
                "totals": session.totals_json,
            },
        )


class CheckoutOrderAPI(APIView):
    def post(self, request):
        serializer = CheckoutOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant_ctx = _build_tenant_context(request)
        try:
            order = CreateOrderFromCheckoutUseCase.execute(
                CreateOrderFromCheckoutCommand(
                    tenant_ctx=tenant_ctx, session_id=serializer.validated_data["session_id"]
                )
            )
        except InvalidCheckoutStateError as exc:
            return api_response(success=False, errors=[str(exc)], status_code=status.HTTP_409_CONFLICT)
        return api_response(
            success=True,
            data={"order_id": order.id, "order_number": order.order_number, "current_step": "CONFIRMED"},
        )
