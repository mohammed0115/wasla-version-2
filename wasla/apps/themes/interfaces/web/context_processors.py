from __future__ import annotations

from apps.themes.models import StoreBranding, Theme


def branding_meta(request):
    tenant = getattr(request, "tenant", None)
    tenant_id = getattr(tenant, "id", None)
    if not tenant_id:
        return {}
    branding = StoreBranding.objects.for_tenant(tenant_id).first()
    theme = None
    if branding and branding.theme_code:
        theme = Theme.objects.filter(code=branding.theme_code, is_active=True).first()
    return {
        "store_branding": branding,
        "store_theme": theme,
    }
