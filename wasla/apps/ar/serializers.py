from rest_framework import serializers


class ProductARDataSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    model_url = serializers.CharField()
    texture_url = serializers.CharField(allow_null=True)
    metadata = serializers.JSONField()
