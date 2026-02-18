from __future__ import annotations

from django.conf import settings
from django.db.utils import OperationalError, ProgrammingError

from apps.emails.models import GlobalEmailSettings
from apps.system.domain.go_live_checks.types import GoLiveCheckItem, LEVEL_P0, LEVEL_P1


class SecurityReadinessChecker:
    category_key = "security"
    category_label = "Security readiness"

    def run(self) -> list[GoLiveCheckItem]:
        items: list[GoLiveCheckItem] = []

        debug_ok = not bool(getattr(settings, "DEBUG", False))
        items.append(
            GoLiveCheckItem(
                key="security.debug_disabled",
                label="Debug disabled",
                ok=debug_ok,
                level=LEVEL_P0,
                message="" if debug_ok else "Set DJANGO_DEBUG=0 before go-live.",
                category=self.category_key,
            )
        )

        secret = str(getattr(settings, "SECRET_KEY", "") or "")
        secret_ok = bool(secret) and "django-insecure" not in secret and len(secret) >= 32
        items.append(
            GoLiveCheckItem(
                key="security.secret_key",
                label="Secret key is production-grade",
                ok=secret_ok,
                level=LEVEL_P0,
                message=""
                if secret_ok
                else "Set a strong, unique DJANGO_SECRET_KEY (avoid default django-insecure keys).",
                category=self.category_key,
            )
        )

        rf_defaults = getattr(settings, "REST_FRAMEWORK", {}) or {}
        perms = tuple(rf_defaults.get("DEFAULT_PERMISSION_CLASSES", []) or [])
        tenant_perm = "apps.tenants.interfaces.api.permissions.HasTenantAccess"
        tenant_ok = tenant_perm in perms
        items.append(
            GoLiveCheckItem(
                key="security.tenant_access",
                label="Tenant access enforced in API permissions",
                ok=tenant_ok,
                level=LEVEL_P0,
                message=""
                if tenant_ok
                else "Add HasTenantAccess to REST_FRAMEWORK DEFAULT_PERMISSION_CLASSES.",
                category=self.category_key,
            )
        )

        email_ok = False
        email_message = ""
        try:
            settings_row = GlobalEmailSettings.objects.filter(enabled=True).order_by("-updated_at").first()
            if settings_row:
                provider = (settings_row.provider or "").lower()
                has_from = bool((settings_row.from_email or "").strip())
                if provider == GlobalEmailSettings.PROVIDER_SMTP:
                    email_ok = has_from and bool((settings_row.host or "").strip())
                else:
                    email_ok = has_from and bool((settings_row.password_encrypted or "").strip())
            if not email_ok:
                email_message = "Configure GlobalEmailSettings (enabled, from_email, and provider credentials)."
        except (OperationalError, ProgrammingError):
            email_ok = False
            email_message = "Email settings table is not ready. Run migrations first."

        items.append(
            GoLiveCheckItem(
                key="security.email_gateway",
                label="Global email gateway configured",
                ok=email_ok,
                level=LEVEL_P0,
                message=email_message,
                category=self.category_key,
            )
        )

        csp_ok = bool(getattr(settings, "SECURITY_CSP_ENABLED", False))
        items.append(
            GoLiveCheckItem(
                key="security.csp_enabled",
                label="Content Security Policy enabled",
                ok=csp_ok,
                level=LEVEL_P1,
                message="" if csp_ok else "Enable SECURITY_CSP_ENABLED for production.",
                category=self.category_key,
            )
        )

        rate_limits = getattr(settings, "SECURITY_RATE_LIMITS", []) or []
        rate_ok = bool(rate_limits)
        items.append(
            GoLiveCheckItem(
                key="security.rate_limits",
                label="Rate limiting configured",
                ok=rate_ok,
                level=LEVEL_P1,
                message="" if rate_ok else "Define SECURITY_RATE_LIMITS rules.",
                category=self.category_key,
            )
        )

        return items
