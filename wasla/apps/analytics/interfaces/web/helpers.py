from __future__ import annotations

from apps.analytics.application.assign_variant import AssignVariantCommand, AssignVariantUseCase
from apps.tenants.domain.tenant_context import TenantContext
from apps.tenants.guards import require_store, require_tenant


def _build_tenant_context(request) -> TenantContext:
    store = require_store(request)
    tenant = require_tenant(request)
    tenant_id = tenant.id
    store_id = store.id
    currency = getattr(tenant, "currency", "SAR")
    if not store_id:
        raise ValueError("Tenant context is required.")
    if not request.session.session_key:
        request.session.save()
    session_key = request.session.session_key
    user_id = request.user.id if request.user.is_authenticated else None
    return TenantContext(
        tenant_id=tenant_id,
        store_id=store_id,
        currency=currency,
        user_id=user_id,
        session_key=session_key,
    )


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
