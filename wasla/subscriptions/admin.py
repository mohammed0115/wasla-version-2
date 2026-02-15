from django.contrib import admin

from .models import StoreSubscription, SubscriptionPlan


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
    list_filter = ("billing_cycle", "is_active")
    search_fields = ("name",)
    ordering = ("id",)


@admin.register(StoreSubscription)
class StoreSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "store_id", "plan", "status", "start_date", "end_date", "created_at")
    list_filter = ("status", "plan")
    search_fields = ("store_id", "plan__name")
    ordering = ("-created_at",)
