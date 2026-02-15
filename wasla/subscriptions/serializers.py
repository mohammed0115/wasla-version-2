
from rest_framework import serializers
from .models import SubscriptionPlan, StoreSubscription

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = "__all__"

class StoreSubscriptionSerializer(serializers.ModelSerializer):
    plan = SubscriptionPlanSerializer()
    class Meta:
        model = StoreSubscription
        fields = "__all__"
