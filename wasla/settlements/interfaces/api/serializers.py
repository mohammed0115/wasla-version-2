from __future__ import annotations

from rest_framework import serializers


class BalanceSerializer(serializers.Serializer):
    currency = serializers.CharField()
    available_balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    pending_balance = serializers.DecimalField(max_digits=14, decimal_places=2)


class SettlementSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    gross_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    fees_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    net_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    status = serializers.CharField()
    created_at = serializers.DateTimeField()
    approved_at = serializers.DateTimeField(allow_null=True)
    paid_at = serializers.DateTimeField(allow_null=True)


class SettlementItemSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    order_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    fee_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    net_amount = serializers.DecimalField(max_digits=14, decimal_places=2)


class SettlementDetailSerializer(serializers.Serializer):
    settlement = SettlementSerializer()
    items = SettlementItemSerializer(many=True)
