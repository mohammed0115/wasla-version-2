"""Merchant dashboard views for product and variant management."""

from typing import Any

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.catalog.forms import ProductForm, ProductOptionGroupForm, ProductOptionFormSet, ProductVariantForm, ProductVariantFormSet
from apps.catalog.models import Product, ProductOptionGroup, ProductVariant
from apps.catalog.services.variant_service import ProductConfigurationService
from apps.security.rbac import require_permission
from apps.stores.models import Store
from apps.tenants.guards import require_store


@login_required
def product_list(request):
    """List all products for the current store."""
    store = require_store(request)
    products = Product.objects.filter(store_id=store.id).order_by("-id")
    return render(
        request,
        "dashboard/catalog/product_list.html",
        {"products": products, "store": store},
    )


@login_required
def product_create(request):
    """Create a new product with variants."""
    store = require_store(request)
    require_permission(request, "catalog.create_product")

    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.store_id = store.id
            product.save()
            # Redirect to edit view to add variants
            return redirect("catalog:product_edit", product_id=product.id)
    else:
        form = ProductForm()

    return render(
        request,
        "dashboard/catalog/product_form.html",
        {"form": form, "product": None, "store": store, "action": "Create"},
    )


@login_required
def product_edit(request, product_id: int):
    """Edit product and manage its option groups and variants."""
    store = require_store(request)
    require_permission(request, "catalog.update_product")

    product = get_object_or_404(Product, id=product_id, store_id=store.id)
    option_groups = ProductOptionGroup.objects.filter(store=store).prefetch_related("options").order_by("position")
    variants = product.variants.prefetch_related("options").order_by("id")

    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            product = form.save()
            return redirect("catalog:product_detail", product_id=product.id)
    else:
        form = ProductForm(instance=product)

    return render(
        request,
        "dashboard/catalog/product_edit.html",
        {
            "form": form,
            "product": product,
            "store": store,
            "option_groups": option_groups,
            "variants": variants,
        },
    )


@login_required
def product_detail(request, product_id: int):
    """View product details and manage variants."""
    store = require_store(request)
    product = get_object_or_404(Product, id=product_id, store_id=store.id)
    option_groups = ProductOptionGroup.objects.filter(store=store).prefetch_related("options").order_by("position")
    variants = product.variants.prefetch_related("options").order_by("id")

    return render(
        request,
        "dashboard/catalog/product_detail.html",
        {
            "product": product,
            "store": store,
            "option_groups": option_groups,
            "variants": variants,
        },
    )


@login_required
def option_group_create(request, product_id: int):
    """Create a new option group for a product."""
    store = require_store(request)
    require_permission(request, "catalog.update_product")

    product = get_object_or_404(Product, id=product_id, store_id=store.id)

    if request.method == "POST":
        form = ProductOptionGroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.store = store
            group.save()
            return redirect("catalog:product_edit", product_id=product.id)
    else:
        form = ProductOptionGroupForm()

    return render(
        request,
        "dashboard/catalog/option_group_form.html",
        {"form": form, "product": product, "group": None, "action": "Create"},
    )


@login_required
def option_group_edit(request, product_id: int, group_id: int):
    """Edit an option group and its options."""
    store = require_store(request)
    require_permission(request, "catalog.update_product")

    product = get_object_or_404(Product, id=product_id, store_id=store.id)
    group = get_object_or_404(ProductOptionGroup, id=group_id, store=store)

    if request.method == "POST":
        form = ProductOptionGroupForm(request.POST, instance=group)
        option_formset = ProductOptionFormSet(request.POST, instance=group)
        if form.is_valid() and option_formset.is_valid():
            form.save()
            option_formset.save()
            return redirect("catalog:product_edit", product_id=product.id)
    else:
        form = ProductOptionGroupForm(instance=group)
        option_formset = ProductOptionFormSet(instance=group)

    return render(
        request,
        "dashboard/catalog/option_group_edit.html",
        {
            "form": form,
            "option_formset": option_formset,
            "product": product,
            "group": group,
        },
    )


@login_required
def variant_create(request, product_id: int):
    """Create a new variant for a product."""
    store = require_store(request)
    require_permission(request, "catalog.update_product")

    product = get_object_or_404(Product, id=product_id, store_id=store.id)

    if request.method == "POST":
        form = ProductVariantForm(request.POST, store_id=store.id)
        if form.is_valid():
            variant = form.save(commit=False)
            variant.product = product
            variant.store_id = store.id
            variant.save()
            # Save M2M options
            form.save_m2m()
            return redirect("catalog:product_edit", product_id=product.id)
    else:
        form = ProductVariantForm(store_id=store.id)

    return render(
        request,
        "dashboard/catalog/variant_form.html",
        {"form": form, "product": product, "variant": None, "action": "Create"},
    )


@login_required
def variant_edit(request, product_id: int, variant_id: int):
    """Edit an existing variant."""
    store = require_store(request)
    require_permission(request, "catalog.update_product")

    product = get_object_or_404(Product, id=product_id, store_id=store.id)
    variant = get_object_or_404(ProductVariant, id=variant_id, product=product, store_id=store.id)

    if request.method == "POST":
        form = ProductVariantForm(request.POST, instance=variant, store_id=store.id)
        if form.is_valid():
            form.save()
            return redirect("catalog:product_edit", product_id=product.id)
    else:
        form = ProductVariantForm(instance=variant, store_id=store.id)

    return render(
        request,
        "dashboard/catalog/variant_form.html",
        {"form": form, "product": product, "variant": variant, "action": "Edit"},
    )


@login_required
def variant_delete(request, product_id: int, variant_id: int):
    """Delete a variant."""
    store = require_store(request)
    require_permission(request, "catalog.update_product")

    product = get_object_or_404(Product, id=product_id, store_id=store.id)
    variant = get_object_or_404(ProductVariant, id=variant_id, product=product, store_id=store.id)

    if request.method == "POST":
        variant.delete()
        return redirect("catalog:product_edit", product_id=product.id)

    return render(
        request,
        "dashboard/catalog/variant_confirm_delete.html",
        {"variant": variant, "product": product},
    )


@login_required
def variant_stock_api(request, variant_id: int):
    """API endpoint to get variant stock (JSON)."""
    store = require_store(request)
    variant = get_object_or_404(ProductVariant, id=variant_id, store_id=store.id)
    return JsonResponse({
        "id": variant.id,
        "sku": variant.sku,
        "stock_quantity": variant.stock_quantity,
        "price_override": str(variant.price_override) if variant.price_override else None,
    })

