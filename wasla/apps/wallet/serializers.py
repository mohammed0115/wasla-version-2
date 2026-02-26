
from rest_framework import serializers
from .models import (
    Wallet,
    WalletTransaction,
    WithdrawalRequest,
    Account,
    JournalEntry,
    JournalLine,
    FeePolicy,
    PaymentAllocation,
)


# ========== Accounting Models ==========

class AccountSerializer(serializers.ModelSerializer):
    """Serializer for Chart of Accounts."""
    
    class Meta:
        model = Account
        fields = [
            'id', 'tenant_id', 'store_id', 'code', 'name',
            'account_type', 'is_system', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'is_system']


class JournalLineSerializer(serializers.ModelSerializer):
    """Serializer for Journal Line (debit/credit)."""
    
    account_code = serializers.CharField(source='account.code', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)
    
    class Meta:
        model = JournalLine
        fields = [
            'id', 'account', 'account_code', 'account_name',
            'direction', 'amount', 'memo', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class JournalEntrySerializer(serializers.ModelSerializer):
    """Serializer for Journal Entry with lines."""
    
    lines = JournalLineSerializer(many=True, read_only=True)
    is_balanced_status = serializers.SerializerMethodField()
    
    class Meta:
        model = JournalEntry
        fields = [
            'id', 'tenant_id', 'store_id', 'entry_type', 'reference_type',
            'reference_id', 'idempotency_key', 'description', 'metadata',
            'created_by_id', 'created_at', 'is_balanced', 'is_balanced_status',
            'lines'
        ]
        read_only_fields = ['id', 'created_at', 'is_balanced']
    
    def get_is_balanced_status(self, obj):
        """Get balanced status with validation."""
        is_balanced, message = obj.validate_balanced()
        return {'balanced': is_balanced, 'message': message}


class JournalEntryListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing journal entries."""
    
    total_debit = serializers.SerializerMethodField()
    total_credit = serializers.SerializerMethodField()
    line_count = serializers.SerializerMethodField()
    
    class Meta:
        model = JournalEntry
        fields = [
            'id', 'entry_type', 'reference_type', 'reference_id',
            'description', 'created_at', 'is_balanced',
            'total_debit', 'total_credit', 'line_count'
        ]
        read_only_fields = fields
    
    def get_total_debit(self, obj):
        from decimal import Decimal
        return sum(
            line.amount for line in obj.lines.filter(direction='debit')
        ) or Decimal('0.00')
    
    def get_total_credit(self, obj):
        from decimal import Decimal
        return sum(
            line.amount for line in obj.lines.filter(direction='credit')
        ) or Decimal('0.00')
    
    def get_line_count(self, obj):
        return obj.lines.count()


class FeePolicySerializer(serializers.ModelSerializer):
    """Serializer for Fee Policy."""
    
    class Meta:
        model = FeePolicy
        fields = [
            'id', 'tenant_id', 'store_id', 'plan_id', 'name',
            'fee_type', 'fee_value', 'minimum_fee', 'apply_to_shipping',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PaymentAllocationSerializer(serializers.ModelSerializer):
    """Serializer for Payment Allocation (fee split)."""
    
    journal_entry_id = serializers.IntegerField(source='journal_entry.id', read_only=True)
    
    class Meta:
        model = PaymentAllocation
        fields = [
            'id', 'tenant_id', 'store_id', 'order_id', 'payment_id',
            'gross_amount', 'platform_fee', 'merchant_net', 'currency',
            'fee_policy_id', 'journal_entry_id', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


# ========== Wallet Models ==========

class WalletTransactionSerializer(serializers.ModelSerializer):
    """Serializer for Wallet Transaction."""
    
    class Meta:
        model = WalletTransaction
        fields = "__all__"


class WalletSerializer(serializers.ModelSerializer):
    """Serializer for Wallet with transactions."""
    
    transactions = WalletTransactionSerializer(many=True, read_only=True)

    class Meta:
        model = Wallet
        fields = "__all__"


class WalletSummarySerializer(serializers.Serializer):
    """Serializer for wallet summary view."""
    
    wallet_id = serializers.IntegerField()
    store_id = serializers.IntegerField()
    currency = serializers.CharField()
    available_balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    pending_balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    pending_withdrawal_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    effective_available_balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    is_active = serializers.BooleanField()


# ========== Withdrawal Models ==========

class WithdrawalRequestSerializer(serializers.ModelSerializer):
    """Full serializer for Withdrawal Request."""
    
    class Meta:
        model = WithdrawalRequest
        fields = '__all__'
        read_only_fields = [
            'id', 'tenant_id', 'wallet', 'status', 'requested_at',
            'processed_at', 'processed_by_user_id', 'approved_by_id',
            'reference_code', 'payout_reference', 'journal_entry'
        ]


class WithdrawalRequestListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing withdrawals."""
    
    class Meta:
        model = WithdrawalRequest
        fields = [
            'id', 'store_id', 'amount', 'status', 'reference_code',
            'requested_at', 'processed_at', 'note'
        ]
        read_only_fields = fields


class WithdrawalCreateSerializer(serializers.Serializer):
    """Serializer for creating withdrawal request."""
    
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0.01)
    note = serializers.CharField(max_length=255, required=False, allow_blank=True)


class WithdrawalApproveSerializer(serializers.Serializer):
    """Serializer for approving withdrawal."""
    
    pass  # No additional fields needed


class WithdrawalRejectSerializer(serializers.Serializer):
    """Serializer for rejecting withdrawal."""
    
    rejection_reason = serializers.CharField(max_length=500, required=True)


class WithdrawalMarkPaidSerializer(serializers.Serializer):
    """Serializer for marking withdrawal as paid."""
    
    payout_reference = serializers.CharField(max_length=255, required=True)

