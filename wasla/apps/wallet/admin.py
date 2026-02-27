
from django.contrib import admin
from .models import Wallet, WalletTransaction, WithdrawalRequest

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant_id", "store_id", "available_balance", "pending_balance", "balance", "currency", "is_active")
    list_filter = ("is_active", "currency")
    search_fields = ("store_id", "tenant_id")

@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("wallet", "transaction_type", "balance_bucket", "event_type", "amount", "reference", "created_at")
    list_filter = ("transaction_type", "balance_bucket", "event_type")
    search_fields = ("reference",)


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "store_id", "amount", "status", "requested_at", "processed_at")
    list_filter = ("status",)
    search_fields = ("store_id", "note")
