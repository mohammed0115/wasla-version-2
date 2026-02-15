from __future__ import annotations

from .exceptions import (
    NoActiveSubscriptionError,
    SubscriptionFeatureNotAllowedError,
    SubscriptionLimitExceededError,
)
from .feature_policy import FeaturePolicy
from .subscription_service import SubscriptionService


class SubscriptionEntitlementService:
    @staticmethod
    def get_active_subscription_or_raise(store_id):
        subscription = SubscriptionService.get_active_subscription(store_id)
        if not subscription:
            raise NoActiveSubscriptionError("No active subscription for this store")
        return subscription

    @staticmethod
    def get_active_plan_or_raise(store_id):
        subscription = SubscriptionEntitlementService.get_active_subscription_or_raise(store_id)
        plan = subscription.plan
        if not getattr(plan, "is_active", True):
            raise NoActiveSubscriptionError("Subscription plan is not active")
        return plan

    @staticmethod
    def assert_feature_enabled(store_id: int, feature_name: str) -> None:
        subscription = SubscriptionEntitlementService.get_active_subscription_or_raise(store_id)
        if not FeaturePolicy.can_use(subscription, feature_name):
            raise SubscriptionFeatureNotAllowedError(
                f"Feature '{feature_name}' is not allowed for this plan"
            )

    @staticmethod
    def assert_within_limit(
        *,
        store_id: int,
        limit_field: str,
        current_usage: int,
        increment: int = 1,
    ) -> None:
        plan = SubscriptionEntitlementService.get_active_plan_or_raise(store_id)
        limit = getattr(plan, limit_field, None)
        if limit is None:
            return
        if current_usage + increment > limit:
            raise SubscriptionLimitExceededError(limit_field, int(limit), int(current_usage))

