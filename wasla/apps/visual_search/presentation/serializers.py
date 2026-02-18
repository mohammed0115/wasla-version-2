from rest_framework import serializers


class VisualSearchRequestSerializer(serializers.Serializer):
    image = serializers.ImageField(required=False, allow_null=True)
    image_url = serializers.URLField(required=False, allow_blank=True)
    max_results = serializers.IntegerField(min_value=1, max_value=50, required=False, default=12)
    min_price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    max_price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    sort_by = serializers.ChoiceField(
        choices=["similarity", "price_low", "price_high", "newest"],
        required=False,
        default="similarity",
    )

    def validate(self, attrs):
        image = attrs.get("image")
        image_url = (attrs.get("image_url") or "").strip()

        if not image and not image_url:
            raise serializers.ValidationError("Provide image or image_url.")

        min_price = attrs.get("min_price")
        max_price = attrs.get("max_price")
        if min_price is not None and max_price is not None and min_price > max_price:
            raise serializers.ValidationError("min_price must be less than or equal to max_price.")

        attrs["image_url"] = image_url
        return attrs
