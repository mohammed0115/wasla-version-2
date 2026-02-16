from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),

    # Language switcher (POST)
    path("i18n/", include("django.conf.urls.i18n")),

    # Public web
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path("", include(("accounts.urls", "accounts"), namespace="accounts")),
    path("", include(("ai.interfaces.web.urls", "ai_web"), namespace="ai_web")),
    path("", include(("analytics.interfaces.web.urls", "analytics_web"), namespace="analytics_web")),
    path("", include(("cart.interfaces.web.urls", "cart_web"), namespace="cart_web")),
    path("", include(("checkout.interfaces.web.urls", "checkout_web"), namespace="checkout_web")),
    path("", include(("apps.visual_search.presentation.urls", "visual_search"), namespace="visual_search")),
    path("", include(("exports.interfaces.web.urls", "exports_web"), namespace="exports_web")),
    path("", include(("imports.interfaces.web.urls", "imports_web"), namespace="imports_web")),
    path("", include(("themes.interfaces.web.urls", "themes_web"), namespace="themes_web")),
    path("", include(("settlements.interfaces.web.urls", "settlements_web"), namespace="settlements_web")),
    path("", include(("tenants.urls", "tenants"), namespace="tenants")),
    path("", include(("plugins.urls", "plugins"), namespace="plugins")),

    # APIs
    path("api/", include(("ai.interfaces.api.urls", "ai_api"), namespace="ai_api")),
    path("api/", include(("analytics.interfaces.api.urls", "analytics_api"), namespace="analytics_api")),
    path("api/", include(("apps.visual_search.presentation.api_urls", "visual_search_api"), namespace="visual_search_api")),
    path("api/", include(("cart.interfaces.api.urls", "cart_api"), namespace="cart_api")),
    path("api/", include(("checkout.interfaces.api.urls", "checkout_api"), namespace="checkout_api")),
    path("api/", include(("exports.interfaces.api.urls", "exports_api"), namespace="exports_api")),
    path("api/", include(("imports.interfaces.api.urls", "imports_api"), namespace="imports_api")),
    path("api/", include(("orders.urls", "orders_api"), namespace="orders_api")),
    path("api/", include(("payments.interfaces.api.urls", "payments_api"), namespace="payments_api")),
    path("api/", include(("settlements.interfaces.api.urls", "settlements_api"), namespace="settlements_api")),
    path("api/", include(("themes.interfaces.api.urls", "themes_api"), namespace="themes_api")),
]
