"""
Settlement automation DRF serializers.

Serializes:
- SettlementBatch
- SettlementBatchItem
- ReconciliationReport
- SettlementRunLog
"""

from rest_framework import serializers
from apps.settlements.models import (
    SettlementBatch,
    SettlementBatchItem,
    ReconciliationReport,
    SettlementRunLog,
)


class SettlementBatchItemSerializer(serializers.ModelSerializer):
    """Serializer for individual batch items."""
    
    order_id = serializers.IntegerField(source="order.id", read_only=True)
    order_number = serializers.CharField(
        source="order.order_number", read_only=True
    )
    
    class Meta:
        model = SettlementBatchItem
        fields = [
            "id",
            "order_id",
            "order_number",
            "order_amount",
            "calculated_fee",
            "calculated_net",
            "status",
            "error_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "order_id",
            "order_number",
            "created_at",
            "updated_at",
        ]


class SettlementBatchSerializer(serializers.ModelSerializer):
    """Serializer for settlement batch."""
    
    store_id = serializers.IntegerField(source="store.id", read_only=True)
    store_name = serializers.CharField(source="store.name", read_only=True)
    items = SettlementBatchItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = SettlementBatch
        fields = [
            "id",
            "batch_reference",
            "store_id",
            "store_name",
            "total_orders",
            "total_amount",
            "total_fees",
            "total_net",
            "status",
            "started_at",
            "completed_at",
            "duration_ms",
            "orders_succeeded",
            "orders_failed",
            "failed_reason",
            "items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "batch_reference",
            "store_id",
            "store_name",
            "items",
            "created_at",
            "updated_at",
        ]


class ReconciliationReportSerializer(serializers.ModelSerializer):
    """Serializer for reconciliation report."""
    
    store_id = serializers.IntegerField(source="store.id", read_only=True)
    store_name = serializers.CharField(source="store.name", read_only=True)
    variance_pct = serializers.SerializerMethodField()
    
    class Meta:
        model = ReconciliationReport
        fields = [
            "id",
            "store_id",
            "store_name",
            "period_start",
            "period_end",
            "expected_total",
            "settled_total",
            "discrepancy",
            "discrepancy_percentage",
            "variance_pct",
            "unsettled_orders_count",
            "orphaned_items_count",
            "amount_mismatch_count",
            "status",
            "findings",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "store_id",
            "store_name",
            "created_at",
        ]
    
    def get_variance_pct(self, obj):
        """Get variance percentage as a formatted string."""
        return f"{obj.discrepancy_percentage:.2f}%"


class SettlementRunLogSerializer(serializers.ModelSerializer):
    """Serializer for settlement run log."""
    
    store_id = serializers.IntegerField(source="store.id", read_only=True, allow_null=True)
    store_name = serializers.CharField(
        source="store.name", read_only=True, allow_null=True
    )
    duration_seconds = serializers.SerializerMethodField()
    
    class Meta:
        model = SettlementRunLog
        fields = [
            "id",
            "task_name",
            "task_id",
            "status",
            "store_id",
            "store_name",
            "started_at",
            "completed_at",
            "duration_ms",
            "duration_seconds",
            "message",
            "orders_processed",
            "batches_created",
            "total_amount",
            "payload_json",
            "error_trace",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "task_name",
            "task_id",
            "status",
            "store_id",
            "store_name",
            "created_at",
        ]
    
    def get_duration_seconds(self, obj):
        """Convert milliseconds to seconds."""
        if obj.duration_ms:
            return f"{obj.duration_ms / 1000:.2f}s"
        return None
