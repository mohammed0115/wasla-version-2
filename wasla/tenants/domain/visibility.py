from __future__ import annotations

from datetime import datetime
from enum import Enum


class StorefrontState(str, Enum):
    LIVE = "live"
    COMING_SOON = "coming_soon"
    MAINTENANCE = "maintenance"


def get_storefront_state(
    *,
    tenant_is_active: bool,
    is_published: bool,
    activated_at: datetime | None,
    deactivated_at: datetime | None,
) -> StorefrontState:
    if not tenant_is_active:
        return StorefrontState.MAINTENANCE
    if is_published:
        return StorefrontState.LIVE
    if activated_at and deactivated_at:
        return StorefrontState.MAINTENANCE
    return StorefrontState.COMING_SOON

