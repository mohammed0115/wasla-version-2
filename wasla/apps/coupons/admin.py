from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from apps.coupons.models import Coupon, CouponUsageLog


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "store",
        "discount_display",
        "status_badge",
        "usage_display",
        "valid_dates",
    ]
    list_filter = ["store", "is_active", "discount_type", "created_at"]
    search_fields = ["code", "description"]
    readonly_fields = ["times_used", "created_at", "updated_at"]
    fieldsets = (
        ("Basic Information", {"fields": ("store", "code", "is_active")}),
        (
            "Discount",
            {"fields": ("discount_type", "discount_value", "max_discount_amount")},
        ),
        (
            "Restrictions",
            {
                "fields": (
                    "minimum_purchase_amount",
                    "usage_limit",
                    "usage_limit_per_customer",
                )
            },
        ),
        (
            "Validity",
            {"fields": ("start_date", "end_date"), "classes": ("wide",)},
        ),
        ("Usage", {"fields": ("times_used",), "classes": ("collapse",)}),
        (
            "Metadata",
            {
                "fields": ("description", "created_by", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def discount_display(self, obj):
        if obj.discount_type == Coupon.DISCOUNT_PERCENTAGE:
            return f"{obj.discount_value}%"
        else:
            return f"{obj.discount_value} SAR"

    discount_display.short_description = "Discount"

    def status_badge(self, obj):
        now = timezone.now()
        if not obj.is_active:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 3px 8px; border-radius: 3px;">Disabled</span>'
            )
        elif obj.start_date > now:
            return format_html(
                '<span style="background-color: #ffc107; color: black; padding: 3px 8px; border-radius: 3px;">Pending</span>'
            )
        elif obj.end_date < now:
            return format_html(
                '<span style="background-color: #6c757d; color: white; padding: 3px 8px; border-radius: 3px;">Expired</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 8px; border-radius: 3px;">Active</span>'
            )

    status_badge.short_description = "Status"

    def usage_display(self, obj):
        if obj.usage_limit:
            percentage = (obj.times_used / obj.usage_limit) * 100
            return f"{obj.times_used}/{obj.usage_limit} ({percentage:.1f}%)"
        else:
            return f"{obj.times_used} (Unlimited)"

    usage_display.short_description = "Usage"

    def valid_dates(self, obj):
        return f"{obj.start_date.strftime('%Y-%m-%d')} → {obj.end_date.strftime('%Y-%m-%d')}"

    valid_dates.short_description = "Valid"


@admin.register(CouponUsageLog)
class CouponUsageLogAdmin(admin.ModelAdmin):
    list_display = ["coupon", "customer", "order", "discount_applied", "used_at"]
    list_filter = ["coupon", "used_at"]
    search_fields = ["coupon__code", "customer__email", "order__id"]
    readonly_fields = ["coupon", "customer", "order", "discount_applied", "used_at"]
    date_hierarchy = "used_at"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
