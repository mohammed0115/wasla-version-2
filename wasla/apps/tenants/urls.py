from django.urls import path
from apps.tenants.interfaces.web import views as wviews
from apps.tenants.interfaces.web import storefront_views

app_name = "tenants"

urlpatterns = [
    # Dashboard landing
    path("dashboard/", wviews.dashboard_home, name="dashboard_home"),
    path("dashboard/orders", wviews.dashboard_orders, name="dashboard_orders"),
    path("dashboard/payment-required", wviews.payment_required, name="payment_required"),
    path("dashboard/pending-activation", wviews.pending_activation, name="pending_activation"),
    path("dashboard/domains", wviews.dashboard_domains, name="dashboard_domains"),

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
    path("dashboard/store/users-roles", wviews.dashboard_users_roles, name="dashboard_users_roles"),
    path(
        "dashboard/store/users-roles/<int:membership_id>/role",
        wviews.dashboard_member_update_role,
        name="dashboard_member_update_role",
    ),
    path(
        "dashboard/store/users-roles/<int:membership_id>/deactivate",
        wviews.dashboard_member_deactivate,
        name="dashboard_member_deactivate",
    ),

    # Custom domains
    path("dashboard/domains/add", wviews.custom_domain_add, name="custom_domain_add"),
    path("dashboard/domains/<int:domain_id>/verify", wviews.custom_domain_verify, name="custom_domain_verify"),
    path("dashboard/domains/<int:domain_id>/disable", wviews.custom_domain_disable, name="custom_domain_disable"),

    path(
        ".well-known/wassla-domain-verification/<str:token>",
        wviews.custom_domain_verification,
        name="custom_domain_verification",
    ),

    # Storefront (tenant home)
    path("storefront", storefront_views.storefront_home, name="storefront_home"),
]
