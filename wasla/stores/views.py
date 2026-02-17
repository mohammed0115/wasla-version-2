from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.db import transaction

from .models import Store, StoreSettings, StoreSetupStep
from .forms import (
    MerchantRegistrationForm,
    StoreBasicInfoForm,
    StoreDomainForm,
    StoreSettingsForm,
)


User = get_user_model()


@require_http_methods(["GET", "POST"])
def merchant_register(request):
    """
    Merchant registration page.
    
    GET: Display registration form
    POST: Process registration and create initial user account
    """
    if request.user.is_authenticated:
        # Check if user already has stores
        if request.user.stores.exists():
            return redirect("store_setup_basic")
        # Check if user just registered and should complete persona
        if not request.user.profile.persona_completed:
            return redirect("accounts:persona_country")

    if request.method == "POST":
        form = MerchantRegistrationForm(request.POST)
        if form.is_valid():
            # Create or update user
            email = request.user.email if request.user.is_authenticated else "merchant@example.com"
            full_name = form.cleaned_data["full_name"]
            phone = form.cleaned_data["phone_number"]
            business_name = form.cleaned_data["business_name"]

            if request.user.is_authenticated:
                user = request.user
                user.first_name = full_name.split()[0]
                user.last_name = " ".join(full_name.split()[1:]) if len(full_name.split()) > 1 else ""
                user.save()
            else:
                # This would require login/signup first in real flow
                messages.error(request, _("Please log in first."))
                return redirect("accounts:login")

            # Update profile with merchant info
            profile = user.profile
            profile.phone_number = phone
            profile.save()

            # Redirect to store setup wizard
            messages.success(request, _("Welcome! Let's set up your store."))
            return redirect("store_setup_basic")
    else:
        form = MerchantRegistrationForm()

    context = {
        "form": form,
        "page_title": _("Register as Merchant"),
    }
    return render(request, "stores/merchant_register.html", context)


@require_http_methods(["GET", "POST"])
@login_required
def store_setup_basic(request):
    """
    Store setup wizard - Step 1: Basic Information.
    
    Collects: Store name, description, category, logo
    """
    store = request.user.stores.first()
    setup = store.setup_step if store else None

    if request.method == "POST":
        if store:
            form = StoreBasicInfoForm(request.POST, request.FILES, instance=store)
        else:
            form = StoreBasicInfoForm(request.POST, request.FILES)

        if form.is_valid():
            store = form.save(commit=False)
            store.owner = request.user

            # Auto-generate slug if creating new store
            if not store.slug:
                base_slug = slugify(store.name)
                slug = base_slug
                counter = 1
                while Store.objects.filter(slug=slug, owner=request.user).exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1
                store.slug = slug

            # Auto-generate subdomain from name
            if not store.subdomain:
                base_subdomain = slugify(store.name)
                subdomain = base_subdomain
                counter = 1
                while Store.objects.filter(subdomain=subdomain).exists():
                    subdomain = f"{base_subdomain}-{counter}"
                    counter += 1
                store.subdomain = subdomain

            store.save()

            # Initialize setup tracking
            setup, created = StoreSetupStep.objects.get_or_create(store=store)
            setup.mark_step_complete(StoreSetupStep.STEP_BASIC)
            setup.current_step = StoreSetupStep.STEP_PRODUCTS
            setup.save()

            # Initialize store settings
            StoreSettings.objects.get_or_create(store=store)

            messages.success(request, _("Store information saved! Now let's add products."))
            return redirect("store_setup_products")
    else:
        if store:
            form = StoreBasicInfoForm(instance=store)
        else:
            form = StoreBasicInfoForm()

    context = {
        "form": form,
        "step": 1,
        "step_label": _("Basic Information"),
        "progress": 25,
    }
    return render(request, "stores/store_setup_basic.html", context)


@require_http_methods(["GET", "POST"])
@login_required
def store_setup_products(request):
    """
    Store setup wizard - Step 2: Product Upload.
    
    Handles: Bulk product image upload (up to 50 images)
    """
    store = get_object_or_404(Store, owner=request.user, setup_step__current_step=StoreSetupStep.STEP_PRODUCTS)
    setup = store.setup_step

    if request.method == "POST":
        # Handle file uploads
        uploaded_files = request.FILES.getlist("products")
        if uploaded_files:
            # In a real implementation, this would process images
            # For now, just mark as completed
            setup.mark_step_complete(StoreSetupStep.STEP_PRODUCTS)
            setup.current_step = StoreSetupStep.STEP_DESIGN
            setup.save()

            messages.success(request, _("Products uploaded successfully!"))
            return redirect("store_setup_design")
        else:
            messages.warning(request, _("Please select at least one image."))

    context = {
        "store": store,
        "step": 2,
        "step_label": _("Product Upload"),
        "progress": 50,
        "max_images": 50,
    }
    return render(request, "stores/store_setup_products.html", context)


@require_http_methods(["GET", "POST"])
@login_required
def store_setup_design(request):
    """
    Store setup wizard - Step 3: Design & Theme.
    
    Selects: Theme, colors, and styling
    """
    store = get_object_or_404(Store, owner=request.user, setup_step__current_step=StoreSetupStep.STEP_DESIGN)
    setup = store.setup_step

    if request.method == "POST":
        theme_name = request.POST.get("theme_name", "default")
        primary_color = request.POST.get("primary_color", "#000000")
        secondary_color = request.POST.get("secondary_color", "#ffffff")

        store.theme_name = theme_name
        store.theme_color_primary = primary_color
        store.theme_color_secondary = secondary_color
        store.save()

        setup.mark_step_complete(StoreSetupStep.STEP_DESIGN)
        setup.current_step = StoreSetupStep.STEP_DOMAIN
        setup.save()

        messages.success(request, _("Design saved! Final step: Domain configuration."))
        return redirect("store_setup_domain")

    context = {
        "store": store,
        "step": 3,
        "step_label": _("Design & Theme"),
        "progress": 75,
        "themes": [
            {
                "name": "classic",
                "label": _("Classic Elegant"),
                "colors": ("#2c3e50", "#ecf0f1"),
            },
            {
                "name": "modern",
                "label": _("Modern Bold"),
                "colors": ("#000000", "#ff6b6b"),
            },
            {
                "name": "minimal",
                "label": _("Minimal Clean"),
                "colors": ("#ffffff", "#333333"),
            },
        ],
    }
    return render(request, "stores/store_setup_design.html", context)


@require_http_methods(["GET", "POST"])
@login_required
def store_setup_domain(request):
    """
    Store setup wizard - Step 4: Domain Configuration.
    
    Configures: Subdomain, custom domain, launch
    """
    store = get_object_or_404(Store, owner=request.user, setup_step__current_step=StoreSetupStep.STEP_DOMAIN)
    setup = store.setup_step

    if request.method == "POST":
        form = StoreDomainForm(request.POST, instance=store)
        if form.is_valid():
            form.save()

            setup.mark_step_complete(StoreSetupStep.STEP_DOMAIN)
            setup.current_step = StoreSetupStep.STEP_DOMAIN  # All steps complete
            setup.completed_at = None  # We'll set this on launch
            setup.save()

            messages.success(request, _("Domain configured! Ready to launch your store."))
            return redirect("store_setup_success")
    else:
        form = StoreDomainForm(instance=store)

    context = {
        "form": form,
        "store": store,
        "step": 4,
        "step_label": _("Domain Setup"),
        "progress": 100,
        "domain_hint": f"{store.name.lower().replace(' ', '')}.visualai.sa",
    }
    return render(request, "stores/store_setup_domain.html", context)


@require_http_methods(["GET", "POST"])
@login_required
def store_setup_success(request):
    """
    Store setup wizard - Success / Launch!
    
    Shows summary and launch button
    """
    store = get_object_or_404(Store, owner=request.user, setup_step__isnull=False)
    setup = store.setup_step

    if request.method == "POST":
        # Launch the store
        store.status = Store.STATUS_ACTIVE
        from django.utils import timezone
        store.launched_at = timezone.now()
        store.save()

        setup.completed_at = timezone.now()
        setup.save()

        messages.success(
            request,
            _("🎉 Congratulations! Your store is now live! Welcome to the Visual AI Platform!")
        )
        return redirect("store_dashboard", store_id=store.id)

    context = {
        "store": store,
        "setup_time": setup.started_at,
        "product_count": store.catalog_products.count() if hasattr(store, 'catalog_products') else 0,
    }
    return render(request, "stores/store_setup_success.html", context)


@require_http_methods(["GET"])
@login_required
def store_dashboard(request, store_id=None):
    """
    Merchant dashboard showing store metrics and management.
    """
    if store_id:
        store = get_object_or_404(Store, id=store_id, owner=request.user)
    else:
        store = request.user.stores.first()
        if not store:
            return redirect("store_setup_basic")

    # Get store metrics
    context = {
        "store": store,
        "total_sales_today": 0,  # TODO: Calculate from orders
        "new_orders": 0,  # TODO: Count orders
        "visitors": 0,  # TODO: From analytics
        "conversion_rate": 0,  # TODO: Calculate
    }
    return render(request, "stores/dashboard.html", context)
