from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from ..models import StoreSubscription
from apps.tenants.models import Tenant
from apps.stores.models import Store


class SubscriptionService:
    @staticmethod
    def get_active_subscription(store_id):
        subscription = (
            StoreSubscription.objects.select_related("plan")
            .filter(store_id=store_id)
            .order_by("-created_at", "-end_date")
            .first()
        )
        if subscription and SubscriptionService.is_subscription_entitled(subscription):
            return subscription
        return None

    @staticmethod
    def is_subscription_entitled(subscription: StoreSubscription | None, *, today: date | None = None) -> bool:
        if subscription is None:
            return False
        today = today or timezone.now().date()
        status = subscription.status
        if status in {StoreSubscription.STATUS_ACTIVE, StoreSubscription.STATUS_TRIAL}:
            return True
        if status in {StoreSubscription.STATUS_PAST_DUE, StoreSubscription.STATUS_EXPIRED}:
            grace_until = subscription.grace_until or subscription.current_period_end or subscription.end_date
            if grace_until and grace_until >= today:
                return True
        return False

    @staticmethod
    @transaction.atomic
    def subscribe_store(store_id, plan):
        if not getattr(plan, "is_active", True):
            raise ValueError("Plan is not active")
        start = date.today()
        end = start + (timedelta(days=30) if plan.billing_cycle == "monthly" else timedelta(days=365))
        tenant_id = None
        if Tenant.objects.filter(id=store_id).exists():
            tenant_id = store_id
        else:
            tenant_id = (
                Store.objects.filter(id=store_id)
                .values_list("tenant_id", flat=True)
                .first()
            )
        if tenant_id is None:
            tenant_id = store_id

        StoreSubscription.objects.filter(
            store_id=tenant_id,
            status=StoreSubscription.STATUS_ACTIVE,
        ).update(status=StoreSubscription.STATUS_CANCELED)
        return StoreSubscription.objects.create(
            store_id=tenant_id,
            plan=plan,
            start_date=start,
            end_date=end,
            current_period_end=end,
            status=StoreSubscription.STATUS_ACTIVE,
        )
