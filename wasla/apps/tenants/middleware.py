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
from .services.domain_resolution import (
    normalize_host,
    resolve_store_by_host,
    resolve_tenant_by_host,
    resolve_platform_store,
)


class TenantResolverMiddleware(MiddlewareMixin):
    """Resolve store based on subdomain and attach store + tenant to request."""

    @staticmethod
    def _is_platform_subdomain_host(host: str) -> bool:
        normalized_host = (host or "").split(":", 1)[0].strip().lower()
        base_domain = (getattr(settings, "WASSLA_BASE_DOMAIN", "") or "").strip().lower()
        if base_domain and normalized_host.endswith(f".{base_domain}"):
            return True
        return normalized_host.endswith(".nip.io") or normalized_host.endswith(".localhost")

    @staticmethod
    def _is_root_domain(host: str) -> bool:
        """Check if host is the root domain (w-sala.com or www.w-sala.com)."""
        normalized_host = (host or "").split(":", 1)[0].strip().lower()
        base_domain = (getattr(settings, "WASSLA_BASE_DOMAIN", "") or "").strip().lower()
        www_domain = f"www.{base_domain}" if base_domain else ""
        return normalized_host == base_domain or normalized_host == www_domain

    def process_request(self, request):
        if request.path.startswith("/admin-portal/"):
            request.store = None
            request.tenant = None
            return None

        host = normalize_host(request.get_host())
        subdomain = extract_subdomain(request.get_host())
        from apps.stores.models import Store

        # Root domain check: resolve to platform default store
        if self._is_root_domain(host) and not subdomain:
            default_store = resolve_platform_store()
            if default_store and default_store.tenant and default_store.tenant.is_active:
                request.store = default_store
                request.tenant = default_store.tenant
                return None
            # Default store not configured - will be handled by security middleware
            request.store = None
            request.tenant = None
            # Mark that this is a root domain request without default store
            request._is_root_domain_no_default = True
            return None

        store = resolve_store_by_host(host)
        if store:
            request.store = store
            request.tenant = store.tenant
            return None

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


class TenantMiddleware:
    """Attach the resolved tenant to the request as `request.tenant`."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = self._resolve_tenant(request)
        if request.tenant and not getattr(request, "store", None):
            try:
                from apps.stores.models import Store
                store = Store.objects.filter(tenant=request.tenant).order_by("id").first()
                if store:
                    request.store = store
            except Exception:
                pass
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


class StoreStatusGuardMiddleware(MiddlewareMixin):
    """
    Guard: Check store status before allowing request to proceed.
    
    Guards against:
    - Accessing suspended or inactive stores
    - Visiting unpublished storefronts
    
    Returns 503 (Service Unavailable) for inactive stores.
    """
    
    def process_request(self, request):
        """Check store status before allowing request to proceed."""
        # Allow admin portal to bypass this check
        if request.path.startswith("/admin-portal/"):
            return None
        
        # Allow health checks to bypass
        if request.path in ["/healthz", "/readyz", "/metrics"]:
            return None
        
        store = getattr(request, "store", None)
        if not store:
            return None
        
        # Check if store is ACTIVE or published
        status = getattr(store, "status", None)
        if status in ["suspended", "inactive", "deleted"]:
            context = {
                "store": store,
                "message": f"This store is currently {status}.",
            }
            return render(
                request,
                "stores/store_unavailable.html",
                context,
                status=503
            )
        
        return None


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
