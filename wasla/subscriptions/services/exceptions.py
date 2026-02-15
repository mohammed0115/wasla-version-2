class SubscriptionError(ValueError):
    pass


class NoActiveSubscriptionError(SubscriptionError):
    pass


class SubscriptionFeatureNotAllowedError(SubscriptionError):
    pass


class SubscriptionLimitExceededError(SubscriptionError):
    def __init__(self, limit_name: str, limit: int, usage: int):
        super().__init__(f"Subscription limit exceeded: {limit_name} ({usage}/{limit})")
        self.limit_name = limit_name
        self.limit = limit
        self.usage = usage

