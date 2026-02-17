from django.urls import path

from .views import (
    merchant_register,
    store_setup_basic,
    store_setup_products,
    store_setup_design,
    store_setup_domain,
    store_setup_success,
    store_dashboard,
)


urlpatterns = [
    path("merchant/register", merchant_register, name="merchant_register"),
    path("merchant/setup/basic", store_setup_basic, name="store_setup_basic"),
    path("merchant/setup/products", store_setup_products, name="store_setup_products"),
    path("merchant/setup/design", store_setup_design, name="store_setup_design"),
    path("merchant/setup/domain", store_setup_domain, name="store_setup_domain"),
    path("merchant/setup/success", store_setup_success, name="store_setup_success"),
    path("merchant/dashboard", store_dashboard, name="store_dashboard"),
    path("merchant/dashboard/<int:store_id>", store_dashboard, name="store_dashboard_with_id"),
]
