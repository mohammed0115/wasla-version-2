from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path("admin/", admin.site.urls),
    
    # Wasla Admin Portal
    path("admin-portal/", include(("apps.admin_portal.urls", "admin_portal"), namespace="admin_portal")),

    # API Documentation - Swagger UI, ReDoc, and OpenAPI Schema
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),

    # Language switcher (POST)
    path("i18n/", include("django.conf.urls.i18n")),

    # Public web
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path("", include(("apps.accounts.urls", "accounts"), namespace="accounts")),
    path("", include(("apps.ai.interfaces.web.urls", "ai_web"), namespace="ai_web")),
    path("", include(("apps.analytics.interfaces.web.urls", "analytics_web"), namespace="analytics_web")),
    path("", include(("apps.cart.interfaces.web.urls", "cart_web"), namespace="cart_web")),
    path("", include(("apps.checkout.interfaces.web.urls", "checkout_web"), namespace="checkout_web")),
    path("", include(("apps.visual_search.presentation.urls", "visual_search"), namespace="visual_search")),
    path("", include(("apps.exports.interfaces.web.urls", "exports_web"), namespace="exports_web")),
    path("", include(("apps.imports.interfaces.web.urls", "imports_web"), namespace="imports_web")),
    path("", include(("apps.themes.interfaces.web.urls", "themes_web"), namespace="themes_web")),
    path("", include(("apps.settlements.interfaces.web.urls", "settlements_web"), namespace="settlements_web")),
    path("", include(("apps.stores.urls", "stores"), namespace="stores")),
    path("", include(("apps.tenants.urls", "tenants"), namespace="tenants")),
    path("", include(("apps.plugins.urls", "plugins"), namespace="plugins")),

    # APIs
    path("api/", include(("apps.ai.interfaces.api.urls", "ai_api"), namespace="ai_api")),
    path("api/", include(("apps.analytics.interfaces.api.urls", "analytics_api"), namespace="analytics_api")),
    path("api/", include(("apps.visual_search.presentation.api_urls", "visual_search_api"), namespace="visual_search_api")),
    path("api/", include(("apps.cart.interfaces.api.urls", "cart_api"), namespace="cart_api")),
    path("api/", include(("apps.checkout.interfaces.api.urls", "checkout_api"), namespace="checkout_api")),
    path("api/", include(("apps.exports.interfaces.api.urls", "exports_api"), namespace="exports_api")),
    path("api/", include(("apps.imports.interfaces.api.urls", "imports_api"), namespace="imports_api")),
    path("api/", include(("apps.orders.urls", "orders_api"), namespace="orders_api")),
    path("api/", include(("apps.purchases.urls", "purchases_api"), namespace="purchases_api")),
    path("api/", include(("apps.payments.interfaces.api.urls", "payments_api"), namespace="payments_api")),
    path("api/", include(("apps.settlements.interfaces.api.urls", "settlements_api"), namespace="settlements_api")),
    path("api/", include(("apps.themes.interfaces.api.urls", "themes_api"), namespace="themes_api")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
