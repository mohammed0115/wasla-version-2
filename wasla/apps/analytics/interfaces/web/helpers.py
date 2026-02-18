from __future__ import annotations

from apps.analytics.application.assign_variant import AssignVariantCommand, AssignVariantUseCase
from apps.tenants.domain.tenant_context import TenantContext


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


def is_variant(request, experiment_key: str, variant: str = "B") -> bool:
    tenant_ctx = _build_tenant_context(request)
    result = AssignVariantUseCase.execute(
        AssignVariantCommand(
            tenant_ctx=tenant_ctx,
            experiment_key=experiment_key,
            actor_id=request.user.id if request.user.is_authenticated else None,
            session_key=request.session.session_key,
        )
    )
    return result.variant == variant
