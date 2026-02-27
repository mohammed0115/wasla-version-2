from __future__ import annotations

"""
Tenant (Store) resolution middleware.

AR:
- يحدد المتجر الحالي ويضعه في `request.tenant`.
- يدعم تحديد المتجر عبر Headers أو Session أو Domain/Subdomain.
- في وضع DEBUG فقط يسمح بـ `?store_id=` لتسهيل التطوير.

EN:
- Resolves the current store (tenant) and attaches it to `request.tenant`.
- Supports resolution via headers, session, and domain/subdomain.
- In DEBUG only, supports `?store_id=` to ease local development.
"""

from django.conf import settings
from django.http import Http404
from django.db.utils import OperationalError, ProgrammingError
from django.shortcuts import render
from django.utils import translation
from django.utils.deprecation import MiddlewareMixin

from .models import Tenant
from .infrastructure.subdomain_resolver import extract_subdomain
from .services.domain_resolution import resolve_tenant_by_host
from .managers import set_current_tenant_context, reset_current_tenant_context, tenant_bypass


class TenantResolverMiddleware(MiddlewareMixin):
    """Resolve store based on subdomain and attach store + tenant to request."""

    @staticmethod
    def _is_platform_subdomain_host(host: str) -> bool:
        normalized_host = (host or "").split(":", 1)[0].strip().lower()
        base_domain = (getattr(settings, "WASSLA_BASE_DOMAIN", "") or "").strip().lower()
        if base_domain and normalized_host.endswith(f".{base_domain}"):
            return True
        return normalized_host.endswith(".nip.io") or normalized_host.endswith(".localhost")

    def process_request(self, request):
        with tenant_bypass():
            if request.path.startswith("/admin-portal/"):
                request.store = None
                request.tenant = None
                return None

            host = request.get_host().split(":", 1)[0]
            subdomain = extract_subdomain(request.get_host())
            from apps.stores.models import Store

            if not subdomain:
                request.store = None
                request.tenant = None

                session_store_id = request.session.get("store_id")
                try:
                    session_store_id = int(session_store_id) if session_store_id is not None else None
                except (TypeError, ValueError):
                    session_store_id = None

                if session_store_id:
                    store = (
                        Store.objects.select_related("tenant")
                        .filter(tenant_id=session_store_id)
                        .order_by("id")
                        .first()
                    )
                    if store:
                        request.store = store
                        request.tenant = store.tenant
                        return None

                user = getattr(request, "user", None)
                if user and user.is_authenticated:
                    store = (
                        Store.objects.select_related("tenant")
                        .filter(owner=user)
                        .order_by("id")
                        .first()
                    )
                    if store:
                        if hasattr(request, "session"):
                            request.session["store_id"] = store.tenant_id
                        request.store = store
                        request.tenant = store.tenant
                        return None

                return None

            store_qs = Store.objects.select_related("tenant").filter(slug=subdomain)
            try:
                Store._meta.get_field("is_active")
                store_qs = store_qs.filter(is_active=True)
            except Exception:
                try:
                    Store._meta.get_field("status")
                    store_qs = store_qs.filter(status=Store.STATUS_ACTIVE)
                except Exception:
                    pass

            store = store_qs.first()
            if not store:
                if self._is_platform_subdomain_host(host) and not request.path.startswith("/api/"):
                    return render(
                        request,
                        "storefront/store_not_found.html",
                        {
                            "requested_subdomain": subdomain,
                            "base_domain": getattr(settings, "WASSLA_BASE_DOMAIN", "w-sala.com"),
                        },
                        status=404,
                    )
                raise Http404("Store not found")

            request.store = store
            request.tenant = store.tenant
            return None


class TenantMiddleware:
    """Attach the resolved tenant to the request as `request.tenant`."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = self._resolve_tenant(request)
        return self.get_response(request)

    def _resolve_tenant(self, request):
        """
        Resolve tenant using a predictable priority order.

        Order:
        1) `X-Tenant` / `X-Tenant-Id` headers (id or slug/domain)
        2) DEBUG querystring (`store_id` / `tenant_id`) -> stored in session
        3) session `store_id`
        4) domain / subdomain
        """
        tenant = None

        raw_header = (
            request.headers.get("X-Tenant")
            or request.headers.get("X-Tenant-Id")
            or request.headers.get("X-Tenant-ID")
        )
        if raw_header:
            raw_header = raw_header.strip()
            try:
                header_store_id = int(raw_header)
            except ValueError:
                header_store_id = None

            try:
                if header_store_id is not None:
                    tenant = Tenant.objects.filter(id=header_store_id, is_active=True).first()
                else:
                    tenant = Tenant.objects.filter(slug=raw_header, is_active=True).first()
                    if not tenant:
                        tenant = resolve_tenant_by_host(raw_header)

                if tenant:
                    request.session["store_id"] = tenant.id
                    return tenant
            except (OperationalError, ProgrammingError):
                return None

        if settings.DEBUG:
            raw_store_id = request.GET.get("store_id") or request.GET.get("tenant_id")
            if raw_store_id:
                try:
                    store_id = int(raw_store_id)
                except ValueError:
                    store_id = None
                if store_id:
                    request.session["store_id"] = store_id

        store_id = request.session.get("store_id")
        try:
            store_id = int(store_id) if store_id is not None else None
        except (TypeError, ValueError):
            store_id = None

        host = request.get_host().split(":", 1)[0]

        try:
            if store_id is not None:
                tenant = Tenant.objects.filter(id=store_id, is_active=True).first()
                if tenant:
                    return tenant

            if host:
                tenant = resolve_tenant_by_host(host)
                if tenant:
                    request.session["store_id"] = tenant.id
                    return tenant

        except (OperationalError, ProgrammingError):
            return None

        return None


class TenantContextMiddleware:
    """Attach tenant context to query layer for the duration of the request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant = getattr(request, "tenant", None)
        store = getattr(request, "store", None)
        bypass = False
        if request.path.startswith("/admin/") or request.path.startswith("/admin-portal/"):
            bypass = True
        user = getattr(request, "user", None)
        if user and getattr(user, "is_superuser", False):
            bypass = True

        token = set_current_tenant_context(
            tenant_id=getattr(tenant, "id", None),
            store_id=getattr(store, "id", None),
            bypass=bypass,
        )
        try:
            return self.get_response(request)
        finally:
            reset_current_tenant_context(token)


class TenantGuardMiddleware:
    """Block tenant-scoped requests when tenant is not resolved."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(request, "tenant", None) is None:
            if self._is_exempt(request):
                return self.get_response(request)
            return render(
                request,
                "storefront/store_not_found.html",
                {
                    "requested_subdomain": extract_subdomain(request.get_host()),
                    "base_domain": getattr(settings, "WASSLA_BASE_DOMAIN", "w-sala.com"),
                },
                status=404,
            )
        return self.get_response(request)

    @staticmethod
    def _is_exempt(request) -> bool:
        path = request.path or "/"
        if path.startswith("/static/") or path.startswith("/media/"):
            return True
        if path in {"/health/", "/healthz/"}:
            return True
        if path.startswith("/admin/") or path.startswith("/admin-portal/"):
            return True
        if path.startswith("/api/schema/") or path.startswith("/api/docs/") or path.startswith("/api/redoc/"):
            return True
        if path.startswith("/api/payments/webhook/") or path.startswith("/api/payments/webhooks/"):
            return True
        if path == "/" or path.startswith("/accounts/") or path.startswith("/i18n/"):
            return True
        return False


class TenantLocaleMiddleware:
    """
    Set a tenant default language if user hasn't selected one.
    Must run before Django's LocaleMiddleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant = getattr(request, "tenant", None)
        if tenant and hasattr(tenant, "language"):
            lang = (tenant.language or "").strip()
            if lang:
                cookie_name = getattr(settings, "LANGUAGE_COOKIE_NAME", "django_language")
                has_cookie = bool(request.COOKIES.get(cookie_name))
                if not has_cookie:
                    translation.activate(lang)
                    request.LANGUAGE_CODE = lang
        return self.get_response(request)
