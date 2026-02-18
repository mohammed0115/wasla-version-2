
class FeaturePolicy:
    @staticmethod
    def can_use(subscription, feature_name: str) -> bool:
        if subscription.status != "active":
            return False
        requested = (feature_name or "").strip().lower()
        available = {str(feature).strip().lower() for feature in (subscription.plan.features or [])}
        return requested in available
