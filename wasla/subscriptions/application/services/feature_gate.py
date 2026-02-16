from __future__ import annotations

from subscriptions.services.entitlement_service import SubscriptionEntitlementService
from subscriptions.services.exceptions import (
    NoActiveSubscriptionError,
    SubscriptionFeatureNotAllowedError,
)


class FeatureGateService:
    AI_TOOLS = "ai_tools"
    AI_VISUAL_SEARCH = "ai_visual_search"

    @staticmethod
    def can_use_feature(tenant_id: int, feature_key: str) -> bool:
        normalized_feature = (feature_key or "").strip().lower()
        if not normalized_feature:
            return False
        try:
            SubscriptionEntitlementService.assert_feature_enabled(tenant_id, normalized_feature)
        except (NoActiveSubscriptionError, SubscriptionFeatureNotAllowedError):
            return False
        return True
