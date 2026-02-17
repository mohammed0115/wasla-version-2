from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from cart.application.use_cases.get_cart import GetCartUseCase
from checkout.application.use_cases.create_order_from_checkout import (
    CreateOrderFromCheckoutCommand,
    CreateOrderFromCheckoutUseCase,
)
from checkout.application.use_cases.get_checkout import GetCheckoutCommand, GetCheckoutUseCase
from checkout.application.use_cases.save_shipping_address import (
    SaveShippingAddressCommand,
    SaveShippingAddressUseCase,
)
from checkout.application.use_cases.select_shipping_method import (
    SelectShippingMethodCommand,
    SelectShippingMethodUseCase,
)
from checkout.application.use_cases.start_checkout import StartCheckoutCommand, StartCheckoutUseCase
from checkout.domain.errors import CheckoutError
from orders.models import Order
from payments.application.use_cases.initiate_payment import (
    InitiatePaymentCommand,
    InitiatePaymentUseCase,
)
from payments.application.facade import PaymentGatewayFacade
from tenants.domain.tenant_context import TenantContext


def _build_tenant_context(request: HttpRequest) -> TenantContext:
    tenant = getattr(request, "tenant", None)
    tenant_id = getattr(tenant, "id", None)
    currency = getattr(tenant, "currency", "SAR")
    if not tenant_id:
        raise CheckoutError("Tenant context is required.")
    if not request.session.session_key:
        request.session.save()
    session_key = request.session.session_key
    user_id = request.user.id if getattr(request, "user", None) and request.user.is_authenticated else None
    return TenantContext(tenant_id=tenant_id, currency=currency, user_id=user_id, session_key=session_key)


def _store_session_id(request: HttpRequest, session_id: int) -> None:
    request.session["checkout_session_id"] = session_id


def _get_session_id(request: HttpRequest) -> int | None:
    try:
        return int(request.session.get("checkout_session_id") or 0) or None
    except (TypeError, ValueError):
        return None


@require_http_methods(["GET", "POST"])
def checkout_address(request: HttpRequest) -> HttpResponse:
    tenant_ctx = _build_tenant_context(request)
    try:
        session = StartCheckoutUseCase.execute(StartCheckoutCommand(tenant_ctx=tenant_ctx))
    except CheckoutError:
        return redirect("cart_web:cart_view")
    _store_session_id(request, session.id)

    if request.method == "POST":
        address = {
            "full_name": request.POST.get("full_name"),
            "email": request.POST.get("email"),
            "phone": request.POST.get("phone"),
            "line1": request.POST.get("line1"),
            "city": request.POST.get("city"),
            "country": request.POST.get("country"),
        }
        SaveShippingAddressUseCase.execute(
            SaveShippingAddressCommand(tenant_ctx=tenant_ctx, session_id=session.id, address=address)
        )
        return redirect("checkout_web:checkout_shipping")

    cart = GetCartUseCase.execute(tenant_ctx)
    return render(
        request,
        "store/checkout_address.html",
        {"cart": cart, "address": session.shipping_address_json or {}},
    )


@require_http_methods(["GET", "POST"])
def checkout_shipping(request: HttpRequest) -> HttpResponse:
    tenant_ctx = _build_tenant_context(request)
    session_id = _get_session_id(request)
    if not session_id:
        return redirect("checkout_web:checkout_address")

    if request.method == "POST":
        method_code = request.POST.get("method_code") or ""
        try:
            SelectShippingMethodUseCase.execute(
                SelectShippingMethodCommand(
                    tenant_ctx=tenant_ctx, session_id=session_id, method_code=method_code
                )
            )
        except CheckoutError:
            return redirect("checkout_web:checkout_address")
        return redirect("checkout_web:checkout_payment")

    try:
        checkout = GetCheckoutUseCase.execute(GetCheckoutCommand(tenant_ctx=tenant_ctx, session_id=session_id))
    except CheckoutError:
        return redirect("checkout_web:checkout_address")
    return render(
        request,
        "store/checkout_shipping.html",
        {"checkout": checkout, "methods": checkout.shipping_methods},
    )


@require_http_methods(["GET", "POST"])
def checkout_payment(request: HttpRequest) -> HttpResponse:
    tenant_ctx = _build_tenant_context(request)
    session_id = _get_session_id(request)
    if not session_id:
        return redirect("checkout_web:checkout_address")

    if request.method == "POST":
        provider_code = request.POST.get("provider_code") or "dummy"
        try:
            order = CreateOrderFromCheckoutUseCase.execute(
                CreateOrderFromCheckoutCommand(tenant_ctx=tenant_ctx, session_id=session_id)
            )
        except CheckoutError:
            return redirect("checkout_web:checkout_address")
        try:
            result = InitiatePaymentUseCase.execute(
                InitiatePaymentCommand(
                    tenant_ctx=tenant_ctx,
                    order_id=order.id,
                    provider_code=provider_code,
                    return_url=request.build_absolute_uri(
                        f"/order/confirmation/{order.order_number}"
                    ),
                )
            )
        except ValueError as exc:
            messages.error(request, str(exc))
            providers = PaymentGatewayFacade.available_providers(tenant_id=tenant_ctx.tenant_id)
            return render(request, "store/checkout_payment.html", {"providers": providers})
        if result.redirect_url:
            return redirect(result.redirect_url)
        return redirect("checkout_web:order_confirmation", order_number=order.order_number)

    providers = PaymentGatewayFacade.available_providers(tenant_id=tenant_ctx.tenant_id)
    if not providers:
        messages.error(request, "No payment methods are available for this store.")
    return render(request, "store/checkout_payment.html", {"providers": providers})


@require_GET
def order_confirmation(request: HttpRequest, order_number: str) -> HttpResponse:
    tenant_ctx = _build_tenant_context(request)
    order = Order.objects.filter(
        store_id=tenant_ctx.tenant_id, order_number=order_number
    ).first()
    return render(
        request,
        "store/order_confirmation.html",
        {"order": order, "tracking_url": f"/order/track/{order_number}"},
    )


@require_GET
def order_tracking(request: HttpRequest, order_number: str) -> HttpResponse:
    tenant_ctx = _build_tenant_context(request)
    order = Order.objects.filter(store_id=tenant_ctx.tenant_id, order_number=order_number).first()
    shipment = order.shipments.order_by("-created_at").first() if order else None

    status_to_step = {
        "pending": 1,
        "paid": 2,
        "processing": 2,
        "shipped": 3,
        "delivered": 5,
        "completed": 5,
        "cancelled": 0,
    }
    current_step = status_to_step.get(getattr(order, "status", "pending"), 1)
    timeline = [
        {"step": 1, "label": "Order Received", "done": current_step >= 1},
        {"step": 2, "label": "Processing", "done": current_step >= 2},
        {"step": 3, "label": "Shipped", "done": current_step >= 3},
        {"step": 4, "label": "In Transit", "done": current_step >= 4},
        {"step": 5, "label": "Delivered", "done": current_step >= 5},
    ]

    return render(
        request,
        "store/order_tracking.html",
        {
            "order": order,
            "shipment": shipment,
            "timeline": timeline,
            "current_step": current_step,
        },
    )
