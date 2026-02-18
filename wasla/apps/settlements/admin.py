from django.contrib import admin

from .models import AuditLog, LedgerAccount, LedgerEntry, Settlement, SettlementItem


@admin.register(LedgerAccount)
class LedgerAccountAdmin(admin.ModelAdmin):
    list_display = ("id", "store_id", "currency", "available_balance", "pending_balance", "created_at")
    search_fields = ("store_id", "currency")


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "store_id", "entry_type", "amount", "currency", "order_id", "settlement_id", "created_at")
    list_filter = ("entry_type", "currency")
    search_fields = ("store_id", "order_id", "settlement_id")


@admin.register(Settlement)
class SettlementAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "store_id",
        "period_start",
        "period_end",
        "gross_amount",
        "fees_amount",
        "net_amount",
        "status",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("store_id",)


@admin.register(SettlementItem)
class SettlementItemAdmin(admin.ModelAdmin):
    list_display = ("id", "settlement_id", "order_id", "order_amount", "fee_amount", "net_amount")
    search_fields = ("settlement_id", "order_id")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "action", "store_id", "actor_id", "created_at")
    search_fields = ("action", "store_id", "actor_id")
