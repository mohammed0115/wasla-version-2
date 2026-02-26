from __future__ import annotations

from rest_framework import serializers

from apps.catalog.models import Product, ProductImage, ProductOption, ProductOptionGroup, ProductVariant


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image", "alt_text", "position", "is_primary"]


class ProductImageWriteSerializer(serializers.Serializer):
    id = serializers.IntegerField(min_value=1, required=False)
    image = serializers.ImageField(required=False)
    alt_text = serializers.CharField(max_length=255, required=False, allow_blank=True)
    position = serializers.IntegerField(min_value=0, required=False, default=0)
    is_primary = serializers.BooleanField(required=False, default=False)


class ProductOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductOption
        fields = ["id", "value"]


class ProductOptionGroupSerializer(serializers.ModelSerializer):
    options = ProductOptionSerializer(many=True)

    class Meta:
        model = ProductOptionGroup
        fields = ["id", "name", "is_required", "position", "options"]


class ProductVariantSerializer(serializers.ModelSerializer):
    options = ProductOptionSerializer(many=True)

    class Meta:
        model = ProductVariant
        fields = ["id", "sku", "price_override", "stock_quantity", "is_active", "options"]


class ProductVariantOptionRefSerializer(serializers.Serializer):
    group = serializers.CharField(max_length=120)
    value = serializers.CharField(max_length=120)


class ProductVariantWriteSerializer(serializers.Serializer):
    id = serializers.IntegerField(min_value=1, required=False)
    sku = serializers.CharField(max_length=64)
    price_override = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    stock_quantity = serializers.IntegerField(min_value=0, required=False, default=0)
    is_active = serializers.BooleanField(required=False, default=True)
    option_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
    )
    options = ProductVariantOptionRefSerializer(many=True, required=False)


class ProductOptionWriteSerializer(serializers.Serializer):
    id = serializers.IntegerField(min_value=1, required=False)
    value = serializers.CharField(max_length=120)


class ProductOptionGroupWriteSerializer(serializers.Serializer):
    id = serializers.IntegerField(min_value=1, required=False)
    name = serializers.CharField(max_length=120)
    is_required = serializers.BooleanField(required=False, default=False)
    position = serializers.IntegerField(min_value=0, required=False, default=0)
    options = ProductOptionWriteSerializer(many=True, required=False)


class ProductWriteSerializer(serializers.Serializer):
    sku = serializers.CharField(max_length=64)
    name = serializers.CharField(max_length=255)
    price = serializers.DecimalField(max_digits=12, decimal_places=2)
    quantity = serializers.IntegerField(min_value=0, required=False, default=0)
    is_active = serializers.BooleanField(required=False, default=True)
    description_ar = serializers.CharField(required=False, allow_blank=True)
    description_en = serializers.CharField(required=False, allow_blank=True)
    image = serializers.ImageField(required=False, allow_null=True)
    images = ProductImageWriteSerializer(many=True, required=False)
    option_groups = ProductOptionGroupWriteSerializer(many=True, required=False)
    variants = ProductVariantWriteSerializer(many=True, required=False)


class ProductDetailSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=False, allow_null=True)
    images = serializers.SerializerMethodField()
    option_groups = serializers.SerializerMethodField()
    variants = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "store_id",
            "sku",
            "name",
            "price",
            "is_active",
            "description_ar",
            "description_en",
            "image",
            "images",
            "option_groups",
            "variants",
        ]

    def get_images(self, obj: Product):
        images = obj.images.all().order_by("position", "id")
        return ProductImageSerializer(images, many=True).data

    def get_option_groups(self, obj: Product):
        groups = ProductOptionGroup.objects.filter(store_id=obj.store_id).prefetch_related("options").order_by("position", "id")
        return ProductOptionGroupSerializer(groups, many=True).data

    def get_variants(self, obj: Product):
        variants = obj.variants.prefetch_related("options").order_by("id")
        return ProductVariantSerializer(variants, many=True).data
