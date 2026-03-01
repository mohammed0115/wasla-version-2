"""Storefront views for customer-facing pages."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db.models import Q, Prefetch, F, DecimalField, Case, When, IntegerField, Min, Max
from django.db.models.functions import Coalesce
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_GET, require_http_methods
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from apps.catalog.models import Product, Category, ProductVariant
from apps.cart.application.use_cases.get_cart import GetCartUseCase
from apps.cart.domain.errors import CartError
from apps.customers.models import Customer, Address
from apps.orders.models import Order
from apps.stores.models import Store
from apps.tenants.domain.tenant_context import TenantContext
from apps.tenants.interfaces.web.decorators import resolve_tenant_for_request
from core.infrastructure.store_cache import StoreCacheService
from .models import ProductSEO, CategorySEO, StorefrontSettings, ProductSearch


def _build_tenant_context(request: HttpRequest) -> TenantContext:
    """Build tenant context from request."""
    store = getattr(request, "store", None)
    tenant = getattr(request, "tenant", None)
    if not tenant and store and getattr(store, "tenant", None):
        tenant = store.tenant
        request.tenant = tenant
    tenant_id = getattr(tenant, "id", None)
    store_id = getattr(store, "id", None)

    if not store_id and getattr(request, "user", None) and request.user.is_authenticated:
        resolved_tenant = resolve_tenant_for_request(request)
        tenant = resolved_tenant or tenant
        tenant_id = getattr(tenant, "id", None)

    currency = getattr(tenant, "currency", "SAR")
    if not tenant_id or not store_id:
        raise CartError("Tenant context is required.")
    if not request.session.session_key:
        request.session.save()
    session_key = request.session.session_key
    user_id = request.user.id if getattr(request, "user", None) and request.user.is_authenticated else None
    return TenantContext(
        tenant_id=tenant_id,
        store_id=store_id,
        currency=currency,
        user_id=user_id,
        session_key=session_key,
    )


def _get_storefront_context(request: HttpRequest, tenant_ctx: TenantContext) -> dict:
    """Get common storefront context."""
    try:
        cart = GetCartUseCase.execute(tenant_ctx)
        vat_rate = Decimal("0.15")
        vat_amount = (cart.subtotal * vat_rate).quantize(Decimal("0.01"))
    except CartError:
        cart = None
        vat_amount = Decimal("0.00")

    store = getattr(request, "store", None)
    settings = StorefrontSettings.objects.filter(store_id=tenant_ctx.store_id).first()
    if not settings:
        settings = StorefrontSettings.objects.create(store_id=tenant_ctx.store_id)

    return {
        "cart": cart,
        "vat_amount": vat_amount,
        "store": store,
        "settings": settings,
        "tenant_ctx": tenant_ctx,
    }


@require_GET
def storefront_home(request: HttpRequest) -> HttpResponse:
    """Store homepage with featured products."""
    try:
        tenant_ctx = _build_tenant_context(request)
    except CartError:
        return redirect("home")

    context = _get_storefront_context(request, tenant_ctx)

    # Get featured products (active, enabled visibility)
    products = Product.objects.filter(
        store_id=tenant_ctx.store_id,
        is_active=True,
        visibility=Product.VISIBILITY_ENABLED,
    ).prefetch_related(
        "images",
        "categories",
        "variants"
    ).order_by("-id")[:12]

    context.update({
        "page_title": request.store.name if request.store else "Store",
        "products": products,
        "categories": Category.objects.filter(store_id=tenant_ctx.store_id).all()[:8],
    })

    return render(request, "storefront/home.html", context)


def _filtered_product_queryset(*, tenant_ctx: TenantContext, query: str | None = None, category_id: int | None = None):
    qs = Product.objects.filter(
        store_id=tenant_ctx.store_id,
        is_active=True,
        visibility=Product.VISIBILITY_ENABLED,
    )
    if query:
        qs = qs.filter(
            Q(name__icontains=query) |
            Q(sku__icontains=query) |
            Q(description_en__icontains=query) |
            Q(description_ar__icontains=query)
        )
    if category_id:
        qs = qs.filter(categories__id=category_id)
    return qs


def _apply_price_filters(qs, min_price: str | None, max_price: str | None):
    if min_price:
        try:
            qs = qs.filter(price__gte=Decimal(min_price))
        except (ValueError, TypeError):
            pass
    if max_price:
        try:
            qs = qs.filter(price__lte=Decimal(max_price))
        except (ValueError, TypeError):
            pass
    return qs


@require_GET
def product_list(request: HttpRequest) -> HttpResponse:
    """Display full product listing with pagination, search, and filters."""
    try:
        tenant_ctx = _build_tenant_context(request)
    except CartError:
        return redirect("home")

    context = _get_storefront_context(request, tenant_ctx)
    query = request.GET.get("q", "").strip()
    category_id = request.GET.get("category")
    min_price = request.GET.get("min_price")
    max_price = request.GET.get("max_price")

    try:
        category_id_int = int(category_id) if category_id else None
    except (TypeError, ValueError):
        category_id_int = None

    sort_by = request.GET.get("sort", "-id")
    if sort_by not in ["-id", "id", "price", "-price", "name", "-name"]:
        sort_by = "-id"

    page = request.GET.get("page", 1)
    per_page = int(request.GET.get("per_page", context["settings"].product_per_page))

    def _load_product_ids():
        qs = _filtered_product_queryset(
            tenant_ctx=tenant_ctx,
            query=query or None,
            category_id=category_id_int,
        )
        qs = _apply_price_filters(qs, min_price, max_price)
        qs = qs.order_by(sort_by).values_list("id", flat=True)
        return list(qs)

    ids, _ = StoreCacheService.get_or_set(
        store_id=tenant_ctx.store_id,
        namespace="storefront_products",
        key_parts=[
            "list",
            getattr(request, "LANGUAGE_CODE", "ar"),
            f"q:{query or 'all'}",
            f"c:{category_id_int or 'all'}",
            f"min:{min_price or 'any'}",
            f"max:{max_price or 'any'}",
            f"sort:{sort_by}",
        ],
        producer=_load_product_ids,
        timeout=180,
    )

    paginator = Paginator(ids, per_page)
    try:
        products_page = paginator.page(page)
    except PageNotAnInteger:
        products_page = paginator.page(1)
    except EmptyPage:
        products_page = paginator.page(paginator.num_pages)

    page_ids = list(products_page.object_list or [])
    products = []
    if page_ids:
        preserved = Case(*[When(id=pk, then=pos) for pos, pk in enumerate(page_ids)], output_field=IntegerField())
        products = list(
            Product.objects.filter(id__in=page_ids)
            .prefetch_related("images", "categories", "variants")
            .order_by(preserved)
        )

    products_page.object_list = products

    categories = Category.objects.filter(store_id=tenant_ctx.store_id)
    category_ids = list(categories.values_list("id", flat=True))
    price_stats = Product.objects.filter(
        store_id=tenant_ctx.store_id,
        is_active=True,
        visibility=Product.VISIBILITY_ENABLED,
    ).aggregate(
        min_price=Coalesce(Min("price"), Decimal("0"), output_field=DecimalField()),
        max_price=Coalesce(Max("price"), Decimal("0"), output_field=DecimalField()),
    )

    context.update({
        "page_title": f"Search: {query}" if query else "All Products",
        "products": products_page,
        "categories": categories,
        "current_sort": sort_by,
        "current_min_price": min_price,
        "current_max_price": max_price,
        "min_product_price": price_stats.get("min_price", Decimal("0")),
        "max_product_price": price_stats.get("max_price", Decimal("999999")),
        "query": query,
    })

    return render(request, "storefront/product_list.html", context)


@require_GET
def category_products(request: HttpRequest, slug: str) -> HttpResponse:
    """Display products in a category."""
    try:
        tenant_ctx = _build_tenant_context(request)
    except CartError:
        return redirect("home")

    category_seo = get_object_or_404(CategorySEO, slug=slug)
    category = category_seo.category

    if category.store_id != tenant_ctx.store_id:
        return redirect("storefront:home")

    context = _get_storefront_context(request, tenant_ctx)

    products = _filtered_product_queryset(
        tenant_ctx=tenant_ctx,
        query=None,
        category_id=category.id,
    ).prefetch_related(
        "images",
        "categories",
        "variants"
    )

    # Apply filters
    min_price = request.GET.get("min_price")
    max_price = request.GET.get("max_price")

    products = _apply_price_filters(products, min_price, max_price)

    # Apply sorting
    sort_by = request.GET.get("sort", "-id")
    if sort_by in ["-id", "id", "price", "-price", "name", "-name"]:
        products = products.order_by(sort_by)

    # Pagination
    page = request.GET.get("page", 1)
    per_page = int(request.GET.get("per_page", context["settings"].product_per_page))
    paginator = Paginator(products, per_page)

    try:
        products_page = paginator.page(page)
    except PageNotAnInteger:
        products_page = paginator.page(1)
    except EmptyPage:
        products_page = paginator.page(paginator.num_pages)

    # Get all categories for sidebar
    categories = Category.objects.filter(store_id=tenant_ctx.store_id)
    category_ids = list(categories.values_list("id", flat=True))

    # Get price range
    price_stats = Product.objects.filter(
        store_id=tenant_ctx.store_id,
        categories__in=category_ids,
        is_active=True,
        visibility=Product.VISIBILITY_ENABLED,
    ).aggregate(
        min_price=Coalesce(F("price"), Decimal("0"), output_field=DecimalField()),
        max_price=Coalesce(F("price"), Decimal("0"), output_field=DecimalField()),
    )

    context.update({
        "page_title": category.name,
        "category": category,
        "category_seo": category_seo,
        "products": products_page,
        "categories": categories,
        "min_product_price": price_stats.get("min_price", Decimal("0")),
        "max_product_price": price_stats.get("max_price", Decimal("999999")),
        "current_sort": sort_by,
        "current_min_price": min_price,
        "current_max_price": max_price,
    })

    return render(request, "storefront/category.html", context)


@require_GET
def product_search(request: HttpRequest) -> HttpResponse:
    """Search products (delegates to product listing)."""
    return product_list(request)


@require_GET
def product_detail_sf(request: HttpRequest, slug: str) -> HttpResponse:
    """Display product detail page."""
    try:
        tenant_ctx = _build_tenant_context(request)
    except CartError:
        return redirect("home")

    product_seo = get_object_or_404(ProductSEO, slug=slug)
    product = product_seo.product

    if product.store_id != tenant_ctx.store_id:
        return redirect("storefront:home")

    context = _get_storefront_context(request, tenant_ctx)

    # Get variants if any
    variants = product.variants.filter(is_active=True).prefetch_related("options")

    # Get related products (same category)
    related_products = Product.objects.filter(
        store_id=tenant_ctx.store_id,
        is_active=True,
        visibility=Product.VISIBILITY_ENABLED,
        categories__in=product.categories.all(),
    ).exclude(id=product.id).prefetch_related(
        "images",
        "variants"
    ).distinct()[:4]

    context.update({
        "page_title": product_seo.meta_title,
        "product": product,
        "product_seo": product_seo,
        "variants": variants,
        "related_products": related_products,
        "in_stock": any(v.stock_quantity > 0 for v in variants) if variants else product.visibility == Product.VISIBILITY_ENABLED,
    })

    return render(request, "storefront/product_detail.html", context)


@login_required
def customer_orders(request: HttpRequest) -> HttpResponse:
    """Display customer's order history."""
    try:
        tenant_ctx = _build_tenant_context(request)
    except CartError:
        return redirect("home")

    customer = Customer.objects.filter(
        store_id=tenant_ctx.store_id,
        email=request.user.email
    ).first()

    if not customer:
        orders = Order.objects.none()
    else:
        orders = Order.objects.filter(
            store_id=tenant_ctx.store_id,
            customer=customer
        ).prefetch_related("items").order_by("-created_at")

    # Pagination
    page = request.GET.get("page", 1)
    paginator = Paginator(orders, 10)

    try:
        orders_page = paginator.page(page)
    except PageNotAnInteger:
        orders_page = paginator.page(1)
    except EmptyPage:
        orders_page = paginator.page(paginator.num_pages)

    context = _get_storefront_context(request, tenant_ctx)
    context.update({
        "page_title": "My Orders",
        "orders": orders_page,
    })

    return render(request, "storefront/customer_orders.html", context)


@login_required
def customer_addresses(request: HttpRequest) -> HttpResponse:
    """Display and manage customer addresses."""
    try:
        tenant_ctx = _build_tenant_context(request)
    except CartError:
        return redirect("home")

    customer = Customer.objects.filter(
        store_id=tenant_ctx.store_id,
        email=request.user.email
    ).first()

    if not customer:
        addresses = Address.objects.none()
    else:
        addresses = Address.objects.filter(customer=customer)

    context = _get_storefront_context(request, tenant_ctx)
    context.update({
        "page_title": "My Addresses",
        "addresses": addresses,
        "customer": customer,
    })

    return render(request, "storefront/customer_addresses.html", context)


@login_required
@require_http_methods(["POST"])
def customer_reorder(request: HttpRequest, order_id: int) -> HttpResponse:
    """Reorder items from a previous order."""
    try:
        tenant_ctx = _build_tenant_context(request)
    except CartError:
        return redirect("home")

    order = get_object_or_404(
        Order,
        id=order_id,
        store_id=tenant_ctx.store_id
    )

    customer = Customer.objects.filter(
        store_id=tenant_ctx.store_id,
        email=request.user.email
    ).first()

    if not customer or order.customer != customer:
        return redirect("storefront:customer_orders")

    # Create new cart and add items
    from apps.cart.application.use_cases.add_to_cart import AddToCartCommand, AddToCartUseCase
    from apps.cart.domain.errors import CartError

    for item in order.items.all():
        try:
            AddToCartUseCase.execute(AddToCartCommand(
                tenant_ctx=tenant_ctx,
                product_id=item.product_id,
                variant_id=item.variant_id,
                quantity=item.quantity,
            ))
        except CartError:
            pass

    return redirect("cart_web:cart_view")
