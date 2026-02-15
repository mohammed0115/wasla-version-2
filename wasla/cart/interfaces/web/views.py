from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.http import Http404
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from cart.application.use_cases.add_to_cart import AddToCartCommand, AddToCartUseCase
from cart.application.use_cases.get_cart import GetCartUseCase
from cart.application.use_cases.get_product import GetProductCommand, GetProductUseCase
from cart.application.use_cases.remove_cart_item import RemoveCartItemCommand, RemoveCartItemUseCase
from cart.application.use_cases.update_cart_item import UpdateCartItemCommand, UpdateCartItemUseCase
from cart.domain.errors import CartError
from tenants.domain.tenant_context import TenantContext


def _build_tenant_context(request: HttpRequest) -> TenantContext:
    tenant = getattr(request, "tenant", None)
    tenant_id = getattr(tenant, "id", None)
    currency = getattr(tenant, "currency", "SAR")
    if not tenant_id:
        raise CartError("Tenant context is required.")
    if not request.session.session_key:
        request.session.save()
    session_key = request.session.session_key
    user_id = request.user.id if getattr(request, "user", None) and request.user.is_authenticated else None
    return TenantContext(tenant_id=tenant_id, currency=currency, user_id=user_id, session_key=session_key)


@require_GET
def product_detail(request: HttpRequest, store_slug: str, product_id: int) -> HttpResponse:
    tenant_ctx = _build_tenant_context(request)
    tenant = getattr(request, "tenant", None)
    if tenant and tenant.slug != store_slug:
        return redirect("tenants:storefront_home")
    try:
        product = GetProductUseCase.execute(GetProductCommand(tenant_ctx=tenant_ctx, product_id=product_id))
    except ValueError:
        raise Http404
    return render(request, "store/product_detail.html", {"product": product})


@require_GET
def cart_view(request: HttpRequest) -> HttpResponse:
    tenant_ctx = _build_tenant_context(request)
    cart = GetCartUseCase.execute(tenant_ctx)
    return render(request, "store/cart.html", {"cart": cart})


@require_POST
def cart_add(request: HttpRequest) -> HttpResponse:
    tenant_ctx = _build_tenant_context(request)
    try:
        product_id = int(request.POST.get("product_id") or 0)
    except (TypeError, ValueError):
        product_id = 0
    try:
        quantity = int(request.POST.get("quantity") or 1)
    except (TypeError, ValueError):
        quantity = 1
    AddToCartUseCase.execute(AddToCartCommand(tenant_ctx=tenant_ctx, product_id=product_id, quantity=quantity))
    return redirect("cart_web:cart_view")


@require_http_methods(["POST"])
def cart_update(request: HttpRequest) -> HttpResponse:
    tenant_ctx = _build_tenant_context(request)
    try:
        item_id = int(request.POST.get("item_id") or 0)
    except (TypeError, ValueError):
        item_id = 0
    try:
        quantity = int(request.POST.get("quantity") or 1)
    except (TypeError, ValueError):
        quantity = 1
    UpdateCartItemUseCase.execute(
        UpdateCartItemCommand(tenant_ctx=tenant_ctx, item_id=item_id, quantity=quantity)
    )
    return redirect("cart_web:cart_view")


@require_http_methods(["POST"])
def cart_remove(request: HttpRequest) -> HttpResponse:
    tenant_ctx = _build_tenant_context(request)
    try:
        item_id = int(request.POST.get("item_id") or 0)
    except (TypeError, ValueError):
        item_id = 0
    RemoveCartItemUseCase.execute(RemoveCartItemCommand(tenant_ctx=tenant_ctx, item_id=item_id))
    return redirect("cart_web:cart_view")
