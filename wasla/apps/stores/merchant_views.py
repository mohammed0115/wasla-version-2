from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.catalog.models import Category, Product
from apps.orders.models import Order

from .merchant_utils import merchant_required


def _merchant_layout_context(request: HttpRequest) -> dict[str, Any]:
    return {
        "merchant_store": getattr(request, "merchant_store", None),
        "nav": {
            "dashboard": reverse("stores:store_dashboard"),
            "products": reverse("stores:merchant_products"),
            "categories": reverse("stores:merchant_categories"),
            "orders": reverse("stores:merchant_orders"),
        },
    }


# ----------------------
# Categories (Merchant)
# ----------------------


@merchant_required
def merchant_category_list(request: HttpRequest) -> HttpResponse:
    store = request.merchant_store
    categories = Category.objects.filter(store_id=store.id).order_by("name")
    ctx = {**_merchant_layout_context(request), "categories": categories}
    return render(request, "merchant/categories_list.html", ctx)


@merchant_required
@require_http_methods(["GET", "POST"])
def merchant_category_create(request: HttpRequest) -> HttpResponse:
    store = request.merchant_store
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        slug = (request.POST.get("slug") or "").strip()
        if not name:
            messages.error(request, "Category name is required.")
        else:
            Category.objects.create(store_id=store.id, name=name, slug=slug or None)
            messages.success(request, "Category created.")
            return redirect("stores:merchant_categories")
    ctx = {**_merchant_layout_context(request), "mode": "create"}
    return render(request, "merchant/category_form.html", ctx)


@merchant_required
@require_http_methods(["GET", "POST"])
def merchant_category_edit(request: HttpRequest, category_id: int) -> HttpResponse:
    store = request.merchant_store
    category = get_object_or_404(Category, id=category_id, store_id=store.id)
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        slug = (request.POST.get("slug") or "").strip()
        if not name:
            messages.error(request, "Category name is required.")
        else:
            category.name = name
            category.slug = slug or None
            category.save(update_fields=["name", "slug"])
            messages.success(request, "Category updated.")
            return redirect("stores:merchant_categories")
    ctx = {**_merchant_layout_context(request), "mode": "edit", "category": category}
    return render(request, "merchant/category_form.html", ctx)


@merchant_required
@require_http_methods(["POST"])
def merchant_category_delete(request: HttpRequest, category_id: int) -> HttpResponse:
    store = request.merchant_store
    category = get_object_or_404(Category, id=category_id, store_id=store.id)
    category.delete()
    messages.success(request, "Category deleted.")
    return redirect("stores:merchant_categories")


# ----------------------
# Products (Merchant)
# ----------------------


@merchant_required
def merchant_product_list(request: HttpRequest) -> HttpResponse:
    store = request.merchant_store
    products = (
        Product.objects.filter(store_id=store.id)
        .prefetch_related("categories")
        .order_by("-created_at")
    )
    ctx = {**_merchant_layout_context(request), "products": products}
    return render(request, "merchant/products_list.html", ctx)


@merchant_required
@require_http_methods(["GET", "POST"])
def merchant_product_create(request: HttpRequest) -> HttpResponse:
    store = request.merchant_store
    categories = Category.objects.filter(store_id=store.id).order_by("name")

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        description = (request.POST.get("description") or "").strip()
        price = request.POST.get("price")
        currency = (request.POST.get("currency") or "SAR").strip() or "SAR"
        is_active = request.POST.get("is_active") == "on"
        category_ids = request.POST.getlist("categories")
        image = request.FILES.get("image")

        if not name:
            messages.error(request, "Product name is required.")
        elif not price:
            messages.error(request, "Price is required.")
        else:
            with transaction.atomic():
                product = Product.objects.create(
                    store_id=store.id,
                    name=name,
                    description=description,
                    price=price,
                    currency=currency,
                    is_active=is_active,
                    image=image,
                )
                if category_ids:
                    product.categories.set(
                        Category.objects.filter(store_id=store.id, id__in=category_ids)
                    )
            messages.success(request, "Product created.")
            return redirect("stores:merchant_products")

    ctx = {**_merchant_layout_context(request), "mode": "create", "categories": categories}
    return render(request, "merchant/product_form.html", ctx)


@merchant_required
@require_http_methods(["GET", "POST"])
def merchant_product_edit(request: HttpRequest, product_id: int) -> HttpResponse:
    store = request.merchant_store
    product = get_object_or_404(Product, id=product_id, store_id=store.id)
    categories = Category.objects.filter(store_id=store.id).order_by("name")

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        description = (request.POST.get("description") or "").strip()
        price = request.POST.get("price")
        currency = (request.POST.get("currency") or product.currency).strip() or "SAR"
        is_active = request.POST.get("is_active") == "on"
        category_ids = request.POST.getlist("categories")
        image = request.FILES.get("image")
        clear_image = request.POST.get("clear_image") == "on"

        if not name:
            messages.error(request, "Product name is required.")
        elif not price:
            messages.error(request, "Price is required.")
        else:
            with transaction.atomic():
                product.name = name
                product.description = description
                product.price = price
                product.currency = currency
                product.is_active = is_active
                if clear_image:
                    product.image = None
                elif image is not None:
                    product.image = image
                product.save()
                product.categories.set(
                    Category.objects.filter(store_id=store.id, id__in=category_ids)
                )
            messages.success(request, "Product updated.")
            return redirect("stores:merchant_products")

    ctx = {
        **_merchant_layout_context(request),
        "mode": "edit",
        "product": product,
        "categories": categories,
        "selected_category_ids": set(product.categories.values_list("id", flat=True)),
    }
    return render(request, "merchant/product_form.html", ctx)


@merchant_required
@require_http_methods(["POST"])
def merchant_product_delete(request: HttpRequest, product_id: int) -> HttpResponse:
    store = request.merchant_store
    product = get_object_or_404(Product, id=product_id, store_id=store.id)
    product.delete()
    messages.success(request, "Product deleted.")
    return redirect("stores:merchant_products")


# ----------------------
# Orders (Merchant)
# ----------------------


@merchant_required
def merchant_orders_list(request: HttpRequest) -> HttpResponse:
    store = request.merchant_store
    orders = Order.objects.filter(store_id=store.id).order_by("-created_at")
    ctx = {**_merchant_layout_context(request), "orders": orders}
    return render(request, "merchant/orders_list.html", ctx)


@merchant_required
def merchant_order_detail(request: HttpRequest, order_id: str) -> HttpResponse:
    store = request.merchant_store
    order = get_object_or_404(Order, id=order_id, store_id=store.id)
    ctx = {
        **_merchant_layout_context(request),
        "order": order,
        "allowed_statuses": [
            Order.Status.PENDING,
            Order.Status.PAID,
            Order.Status.PROCESSING,
            Order.Status.SHIPPED,
            Order.Status.DELIVERED,
            Order.Status.CANCELLED,
            Order.Status.REFUNDED,
        ],
    }
    return render(request, "merchant/order_detail.html", ctx)


def _is_valid_status_transition(old: str, new: str) -> bool:
    allowed = {
        Order.Status.PENDING: {Order.Status.PAID, Order.Status.CANCELLED},
        Order.Status.PAID: {Order.Status.PROCESSING, Order.Status.REFUNDED},
        Order.Status.PROCESSING: {Order.Status.SHIPPED, Order.Status.CANCELLED},
        Order.Status.SHIPPED: {Order.Status.DELIVERED},
        Order.Status.DELIVERED: set(),
        Order.Status.CANCELLED: set(),
        Order.Status.REFUNDED: set(),
    }
    return new in allowed.get(old, set())


@merchant_required
@require_http_methods(["POST"])
def merchant_order_change_status(request: HttpRequest, order_id: str) -> HttpResponse:
    store = request.merchant_store
    order = get_object_or_404(Order, id=order_id, store_id=store.id)
    new_status = (request.POST.get("status") or "").strip()

    if not new_status:
        messages.error(request, "Please choose a status.")
        return redirect("stores:merchant_order_detail", order_id=order.id)

    if not _is_valid_status_transition(order.status, new_status):
        messages.error(request, "Invalid status transition.")
        return redirect("stores:merchant_order_detail", order_id=order.id)

    order.status = new_status
    order.save(update_fields=["status"])
    messages.success(request, f"Order status updated to {new_status}.")
    return redirect("stores:merchant_order_detail", order_id=order.id)


@merchant_required
@require_http_methods(["POST"])
def merchant_order_refund_placeholder(request: HttpRequest, order_id: str) -> HttpResponse:
    store = request.merchant_store
    order = get_object_or_404(Order, id=order_id, store_id=store.id)
    if order.status not in {Order.Status.PAID, Order.Status.PROCESSING}:
        messages.error(request, "Refund is only available for paid/processing orders.")
        return redirect("stores:merchant_order_detail", order_id=order.id)
    order.status = Order.Status.REFUNDED
    order.payment_status = Order.PaymentStatus.REFUNDED
    order.save(update_fields=["status", "payment_status"])
    messages.success(request, "Refund placeholder applied (status set to refunded).")
    return redirect("stores:merchant_order_detail", order_id=order.id)
