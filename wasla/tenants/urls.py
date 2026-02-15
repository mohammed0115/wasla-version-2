from django.urls import path
from tenants.interfaces.web import views as wviews
from tenants.interfaces.web import storefront_views

app_name = "tenants"

urlpatterns = [
    # Dashboard landing
    path("dashboard/", wviews.dashboard_home, name="dashboard_home"),
    path("dashboard/orders", wviews.dashboard_orders, name="dashboard_orders"),

    # Merchant onboarding / setup
    path("dashboard/setup", wviews.dashboard_setup_store, name="dashboard_setup_store"),
    path("store/create", wviews.store_create, name="store_create"),
    path("store/setup", wviews.store_setup_start, name="store_setup_start"),
    path("store/setup/step-1", wviews.store_setup_step1, name="store_setup_step1"),
    path("store/setup/step-2", wviews.store_setup_step2, name="store_setup_step2"),
    path("store/setup/step-3", wviews.store_setup_step3, name="store_setup_step3"),
    path("store/setup/step-4", wviews.store_setup_step4, name="store_setup_step4"),
    path("dashboard/setup/payment", wviews.dashboard_setup_payment, name="dashboard_setup_payment"),
    path("dashboard/setup/shipping", wviews.dashboard_setup_shipping, name="dashboard_setup_shipping"),
    path("dashboard/setup/activate", wviews.dashboard_setup_activate, name="dashboard_setup_activate"),

    # Store settings
    path("dashboard/store/info", wviews.store_settings_update, name="store_settings_update"),

    # Custom domains
    path("dashboard/domains", wviews.custom_domain_verification, name="custom_domain_verification"),
    path("dashboard/domains/add", wviews.custom_domain_add, name="custom_domain_add"),
    path("dashboard/domains/verify", wviews.custom_domain_verify, name="custom_domain_verify"),
    path("dashboard/domains/disable", wviews.custom_domain_disable, name="custom_domain_disable"),

    # Storefront (tenant home)
    path("storefront", storefront_views.storefront_home, name="storefront_home"),
]
