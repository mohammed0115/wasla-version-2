
class FeaturePolicy:
    @staticmethod
    def can_use(subscription, feature_name: str) -> bool:
        return subscription.status == "active" and feature_name in subscription.plan.features
