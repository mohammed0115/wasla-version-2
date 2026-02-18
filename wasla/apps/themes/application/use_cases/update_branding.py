from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from apps.tenants.domain.tenant_context import TenantContext
from apps.tenants.models import Tenant
from apps.themes.domain.policies import validate_brand_colors, validate_font_family
from apps.themes.models import StoreBranding, Theme


@dataclass(frozen=True)
class UpdateBrandingCommand:
    tenant_ctx: TenantContext
    actor_id: int | None
    theme_code: str = ""
    logo_file: object | None = None
    primary_color: str = ""
    secondary_color: str = ""
    accent_color: str = ""
    font_family: str = ""


class UpdateBrandingUseCase:
    @staticmethod
    @transaction.atomic
    def execute(cmd: UpdateBrandingCommand) -> StoreBranding:
        if not cmd.tenant_ctx.tenant_id:
            raise ValueError("Tenant context is required.")

        theme_code = (cmd.theme_code or "").strip()
        if theme_code:
            theme = Theme.objects.filter(code=theme_code, is_active=True).first()
            if not theme:
                raise ValueError("Invalid theme.")

        colors = validate_brand_colors(
            primary=cmd.primary_color,
            secondary=cmd.secondary_color,
            accent=cmd.accent_color,
        )
        font_family = validate_font_family(cmd.font_family)

        branding, _ = StoreBranding.objects.get_or_create(store_id=cmd.tenant_ctx.tenant_id)
        if theme_code:
            branding.theme_code = theme_code
        if cmd.logo_file:
            branding.logo_path = cmd.logo_file
        branding.primary_color = colors["primary_color"]
        branding.secondary_color = colors["secondary_color"]
        branding.accent_color = colors["accent_color"]
        branding.font_family = font_family
        branding.save()

        tenant = Tenant.objects.filter(id=cmd.tenant_ctx.tenant_id).first()
        if tenant:
            if cmd.logo_file:
                tenant.logo = cmd.logo_file
            if colors["primary_color"]:
                tenant.primary_color = colors["primary_color"]
            if colors["secondary_color"]:
                tenant.secondary_color = colors["secondary_color"]
            tenant.save(update_fields=["logo", "primary_color", "secondary_color", "updated_at"])

        return branding
