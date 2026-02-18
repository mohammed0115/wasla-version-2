
from datetime import date, timedelta
from django.db import transaction
from ..models import StoreSubscription


class SubscriptionService:
    @staticmethod
    def get_active_subscription(store_id):
        today = date.today()
        return (
            StoreSubscription.objects.select_related("plan")
            .filter(store_id=store_id, status="active", end_date__gte=today)
            .order_by("-end_date")
            .first()
        )

    @staticmethod
    @transaction.atomic
    def subscribe_store(store_id, plan):
        if not getattr(plan, "is_active", True):
            raise ValueError("Plan is not active")
        start = date.today()
        end = start + (timedelta(days=30) if plan.billing_cycle == "monthly" else timedelta(days=365))
        StoreSubscription.objects.filter(store_id=store_id, status="active").update(status="expired")
        return StoreSubscription.objects.create(
            store_id=store_id, plan=plan, start_date=start, end_date=end, status="active"
        )
