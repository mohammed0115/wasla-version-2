from django.contrib import admin
from django.contrib import messages
from django.utils import timezone

from .models import StoreSubscription, SubscriptionPlan, PaymentTransaction
from apps.tenants.services.provisioning import provision_store_after_payment


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "billing_cycle",
        "price",
        "is_active",
        "max_products",
        "max_orders_monthly",
        "max_staff_users",
    )
    list_editable = ("is_active",)
    list_filter = ("billing_cycle", "is_active")
    search_fields = ("name",)
    ordering = ("id",)


@admin.register(StoreSubscription)
class StoreSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "store_id", "plan", "status", "start_date", "end_date", "created_at")
    list_filter = ("status", "plan")
    search_fields = ("store_id", "plan__name")
    ordering = ("-created_at",)


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tenant",
        "plan",
        "amount",
        "currency",
        "method",
        "status",
        "reference",
        "created_at",
    )
    list_filter = ("status", "method", "plan")
    search_fields = ("tenant__slug", "tenant__name", "reference")
    ordering = ("-created_at",)
    actions = ("approve_and_create_store",)

    @admin.action(description="Approve selected payments & create store")
    def approve_and_create_store(self, request, queryset):
        approved_count = 0
        skipped_count = 0
        for tx in queryset.select_related("tenant", "plan"):
            if tx.status in {PaymentTransaction.STATUS_FAILED, PaymentTransaction.STATUS_CANCELLED}:
                skipped_count += 1
                continue
            owner = getattr(getattr(tx.tenant, "store_profile", None), "owner", None)
            if owner is None:
                skipped_count += 1
                continue
            if tx.status != PaymentTransaction.STATUS_PAID:
                tx.status = PaymentTransaction.STATUS_PAID
                tx.paid_at = timezone.now()
                tx.save(update_fields=["status", "paid_at"])
            provision_store_after_payment(merchant=owner, plan=tx.plan, payment=tx)
            approved_count += 1

        self.message_user(
            request,
            f"Approved/provisioned: {approved_count}, skipped: {skipped_count}",
            level=messages.INFO,
        )
