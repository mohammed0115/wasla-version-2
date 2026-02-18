from rest_framework import serializers


class PaymentInitiateSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(min_value=1)
    provider_code = serializers.CharField(max_length=50)
    return_url = serializers.CharField(max_length=255)
