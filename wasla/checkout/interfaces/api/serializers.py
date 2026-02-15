from rest_framework import serializers


class CheckoutStartSerializer(serializers.Serializer):
    pass


class CheckoutAddressSerializer(serializers.Serializer):
    session_id = serializers.IntegerField(min_value=1)
    full_name = serializers.CharField(max_length=200)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=32)
    line1 = serializers.CharField(max_length=255)
    city = serializers.CharField(max_length=100)
    country = serializers.CharField(max_length=100)


class CheckoutShippingSerializer(serializers.Serializer):
    session_id = serializers.IntegerField(min_value=1)
    method_code = serializers.CharField(max_length=64)


class CheckoutOrderSerializer(serializers.Serializer):
    session_id = serializers.IntegerField(min_value=1)
