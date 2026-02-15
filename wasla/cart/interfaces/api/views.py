from __future__ import annotations

from rest_framework import status
from rest_framework.views import APIView

from cart.application.use_cases.add_to_cart import AddToCartCommand, AddToCartUseCase
from cart.application.use_cases.get_cart import GetCartUseCase
from cart.application.use_cases.remove_cart_item import RemoveCartItemCommand, RemoveCartItemUseCase
from cart.application.use_cases.update_cart_item import UpdateCartItemCommand, UpdateCartItemUseCase
from cart.domain.errors import CartError
from cart.interfaces.api.responses import api_response
from cart.interfaces.api.serializers import (
    AddToCartSerializer,
    RemoveCartItemSerializer,
    UpdateCartItemSerializer,
)
from tenants.domain.tenant_context import TenantContext


def _build_tenant_context(request) -> TenantContext:
    tenant = getattr(request, "tenant", None)
    tenant_id = getattr(tenant, "id", None)
    currency = getattr(tenant, "currency", "SAR")
    if not tenant_id:
        raise CartError("Tenant context is required.")
    if not request.session.session_key:
        request.session.save()
    session_key = request.session.session_key
    user_id = request.user.id if request.user.is_authenticated else None
    return TenantContext(tenant_id=tenant_id, currency=currency, user_id=user_id, session_key=session_key)


class CartDetailAPI(APIView):
    def get(self, request):
        tenant_ctx = _build_tenant_context(request)
        cart = GetCartUseCase.execute(tenant_ctx)
        data = {
            "cart_id": cart.cart_id,
            "currency": cart.currency,
            "subtotal": str(cart.subtotal),
            "total": str(cart.total),
            "items": [
                {
                    "id": item.id,
                    "product_id": item.product_id,
                    "name": item.name,
                    "quantity": item.quantity,
                    "unit_price": str(item.unit_price),
                    "line_total": str(item.line_total),
                }
                for item in cart.items
            ],
        }
        return api_response(success=True, data=data)


class CartAddAPI(APIView):
    def post(self, request):
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant_ctx = _build_tenant_context(request)
        try:
            cart = AddToCartUseCase.execute(
                AddToCartCommand(
                    tenant_ctx=tenant_ctx,
                    product_id=serializer.validated_data["product_id"],
                    quantity=serializer.validated_data["quantity"],
                )
            )
        except CartError as exc:
            return api_response(success=False, errors=[str(exc)], status_code=status.HTTP_400_BAD_REQUEST)
        return api_response(success=True, data={"cart_id": cart.cart_id})


class CartUpdateAPI(APIView):
    def post(self, request):
        serializer = UpdateCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant_ctx = _build_tenant_context(request)
        try:
            cart = UpdateCartItemUseCase.execute(
                UpdateCartItemCommand(
                    tenant_ctx=tenant_ctx,
                    item_id=serializer.validated_data["item_id"],
                    quantity=serializer.validated_data["quantity"],
                )
            )
        except CartError as exc:
            return api_response(success=False, errors=[str(exc)], status_code=status.HTTP_400_BAD_REQUEST)
        return api_response(success=True, data={"cart_id": cart.cart_id})


class CartRemoveAPI(APIView):
    def post(self, request):
        serializer = RemoveCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant_ctx = _build_tenant_context(request)
        try:
            cart = RemoveCartItemUseCase.execute(
                RemoveCartItemCommand(
                    tenant_ctx=tenant_ctx,
                    item_id=serializer.validated_data["item_id"],
                )
            )
        except CartError as exc:
            return api_response(success=False, errors=[str(exc)], status_code=status.HTTP_400_BAD_REQUEST)
        return api_response(success=True, data={"cart_id": cart.cart_id})
