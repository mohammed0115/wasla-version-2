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
from django.utils import translation
from django.utils.deprecation import MiddlewareMixin

from .models import Tenant
from .infrastructure.subdomain_resolver import extract_subdomain
from .services.domain_resolution import resolve_tenant_by_host


class TenantResolverMiddleware(MiddlewareMixin):
    """Resolve store based on subdomain and attach store + tenant to request."""

    def process_request(self, request):
        if request.path.startswith("/admin-portal/"):
            request.store = None
            request.tenant = None
            return None

        subdomain = extract_subdomain(request.get_host())
        if not subdomain:
            request.store = None
            request.tenant = None
            return None

        from apps.stores.models import Store

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
