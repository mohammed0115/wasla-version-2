from django.contrib import admin
from apps.shipping.models import Shipment, ShippingZone, ShippingRate


@admin.register(ShippingZone)
class ShippingZoneAdmin(admin.ModelAdmin):
    list_display = ["name", "store", "countries", "status_badge", "priority"]
    list_filter = ["store", "is_active", "created_at"]
    search_fields = ["name", "countries"]
    fieldsets = (
        ("Basic Information", {"fields": ("store", "name", "description")}),
        ("Coverage", {"fields": ("countries",)}),
        ("Settings", {"fields": ("is_active", "priority")}),
        (
            "Metadata",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )
    readonly_fields = ["created_at", "updated_at"]

    def status_badge(self, obj):
        from django.utils.html import format_html

        return format_html(
            '<span style="background-color: #28a745; padding: 3px 8px; border-radius: 3px; color: white;">Active</span>'
            if obj.is_active
            else '<span style="background-color: #6c757d; padding: 3px 8px; border-radius: 3px; color: white;">Inactive</span>'
        )

    status_badge.short_description = "Status"


@admin.register(ShippingRate)
class ShippingRateAdmin(admin.ModelAdmin):
    list_display = ["name", "zone", "rate_type", "base_rate", "is_active", "priority"]
    list_filter = ["zone", "rate_type", "is_active"]
    search_fields = ["name", "zone__name"]
    fieldsets = (
        ("Basic Information", {"fields": ("zone", "name", "rate_type")}),
        ("Pricing", {"fields": ("base_rate", "free_shipping_threshold")}),
        (
            "Weight Configuration",
            {"fields": ("min_weight", "max_weight"), "classes": ("wide",)},
        ),
        (
            "Delivery",
            {"fields": ("estimated_days",)},
        ),
        ("Settings", {"fields": ("is_active", "priority")}),
        (
            "Metadata",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ["id", "order", "carrier", "status", "tracking_number", "created_at"]
    list_filter = ["carrier", "status", "created_at"]
    search_fields = ["order__id", "tracking_number"]
    readonly_fields = ["order", "created_at"]
