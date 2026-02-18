from __future__ import annotations

from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.views import APIView

from apps.cart.interfaces.api.responses import api_response
from apps.tenants.domain.tenant_context import TenantContext
from apps.themes.application.use_cases.list_themes import ListThemesUseCase
from apps.themes.application.use_cases.update_branding import (
    UpdateBrandingCommand,
    UpdateBrandingUseCase,
)


def _build_tenant_context(request) -> TenantContext:
    tenant = getattr(request, "tenant", None)
    tenant_id = getattr(tenant, "id", None)
    currency = getattr(tenant, "currency", "SAR")
    if not tenant_id:
        raise ValueError("Tenant context is required.")
    if not request.session.session_key:
        request.session.save()
    session_key = request.session.session_key
    user_id = request.user.id if request.user.is_authenticated else None
    return TenantContext(tenant_id=tenant_id, currency=currency, user_id=user_id, session_key=session_key)


class ThemeListAPI(APIView):
    def get(self, request):
        themes = ListThemesUseCase.execute()
        data = [
            {
                "code": theme.code,
                "name_key": theme.name_key,
                "preview_image_path": theme.preview_image_path,
            }
            for theme in themes
        ]
        return api_response(success=True, data={"items": data})


class BrandingUpdateAPI(APIView):
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request):
        tenant_ctx = _build_tenant_context(request)
        payload = request.data or {}
        try:
            branding = UpdateBrandingUseCase.execute(
                UpdateBrandingCommand(
                    tenant_ctx=tenant_ctx,
                    actor_id=request.user.id if request.user.is_authenticated else None,
                    theme_code=payload.get("theme_code", ""),
                    logo_file=request.FILES.get("logo_file"),
                    primary_color=payload.get("primary_color", ""),
                    secondary_color=payload.get("secondary_color", ""),
                    accent_color=payload.get("accent_color", ""),
                    font_family=payload.get("font_family", ""),
                )
            )
        except ValueError as exc:
            return api_response(success=False, errors=[str(exc)], status_code=status.HTTP_400_BAD_REQUEST)

        return api_response(
            success=True,
            data={
                "theme_code": branding.theme_code,
                "primary_color": branding.primary_color,
                "secondary_color": branding.secondary_color,
                "accent_color": branding.accent_color,
                "font_family": branding.font_family,
                "logo_path": getattr(branding.logo_path, "url", ""),
            },
        )
