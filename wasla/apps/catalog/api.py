from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework import serializers
from django.db import models
from django.utils.decorators import method_decorator
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema, inline_serializer

from apps.catalog.models import Inventory, Product, ProductVariant, StockMovement
from apps.catalog.serializers import ProductDetailSerializer, ProductWriteSerializer
from apps.catalog.services.variant_service import (
    ProductConfigurationService,
    ProductVariantService,
    VariantPricingService,
)
from apps.security.rbac import require_permission
from apps.tenants.guards import require_store
from core.infrastructure.store_cache import StoreCacheService


class LowStockAPI(APIView):
    """Return low stock products for a store (Phase 3)."""

    @extend_schema(
        tags=["Catalog / Inventory"],
        summary="List low stock products",
    )
    def get(self, request):
        store = require_store(request)

        qs = (
            Inventory.objects.select_related("product")
            .filter(product__store_id=store.id)
            .filter(quantity__lte=models.F("low_stock_threshold"))
            .order_by("quantity")
        )

        data = [
            {
                "product_id": inv.product_id,
                "product_name": inv.product.name,
                "quantity": inv.quantity,
                "low_stock_threshold": inv.low_stock_threshold,
            }
            for inv in qs
        ]
        return Response({"store_id": store.id, "items": data})


class StockMovementsAPI(APIView):
    """List stock movements for a store (Phase 3)."""

    @extend_schema(
        tags=["Catalog / Inventory"],
        summary="List stock movements",
        parameters=[
            OpenApiParameter(
                name="product_id",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Optional product id filter",
            )
        ],
    )
    def get(self, request):
        store = require_store(request)
        product_id = request.query_params.get("product_id")

        qs = StockMovement.objects.filter(store_id=store.id).select_related("product", "variant").order_by("-created_at")
        if product_id:
            qs = qs.filter(product_id=product_id)

        data = [
            {
                "id": m.id,
                "product_id": m.product_id,
                "product_name": m.product.name,
                "variant_id": m.variant_id,
                "variant_sku": m.variant.sku if m.variant_id and m.variant else None,
                "movement_type": m.movement_type,
                "quantity": m.quantity,
                "reason": m.reason,
                "order_id": m.order_id,
                "purchase_order_id": m.purchase_order_id,
                "created_at": m.created_at,
            }
            for m in qs[:200]
        ]

        return Response({"store_id": store.id, "items": data})


class ProductUpsertAPI(APIView):
    """Create product with nested option groups + variants."""

    @extend_schema(
        tags=["Catalog / Variants"],
        summary="Create product with nested variants",
        request=ProductWriteSerializer,
        responses={
            201: ProductDetailSerializer,
            400: OpenApiResponse(description="Validation or business rule error"),
        },
        examples=[
            OpenApiExample(
                "Create product with variants",
                value={
                    "sku": "TEE-BASE",
                    "name": "T-Shirt",
                    "price": "100.00",
                    "quantity": 50,
                    "description_ar": "",
                    "description_en": "Basic tee",
                    "option_groups": [
                        {
                            "name": "Color",
                            "is_required": True,
                            "position": 1,
                            "options": [{"value": "Red"}, {"value": "Blue"}],
                        },
                        {
                            "name": "Size",
                            "is_required": True,
                            "position": 2,
                            "options": [{"value": "M"}, {"value": "L"}],
                        },
                    ],
                    "variants": [
                        {
                            "sku": "TEE-RED-M",
                            "price_override": "120.00",
                            "stock_quantity": 7,
                            "is_active": True,
                            "options": [
                                {"group": "Color", "value": "Red"},
                                {"group": "Size", "value": "M"},
                            ],
                        }
                    ],
                },
                request_only=True,
            )
        ],
    )
    @method_decorator(require_permission("catalog.create_product"))
    def post(self, request):
        store = require_store(request)
        serializer = ProductWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            product = ProductConfigurationService.upsert_product_with_variants(
                store=store,
                payload=serializer.validated_data,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ProductDetailSerializer(product).data, status=status.HTTP_201_CREATED)


class ProductUpdateAPI(APIView):
    """Update product with nested option groups + variants."""

    @extend_schema(
        tags=["Catalog / Variants"],
        summary="Update product and nested variants",
        request=ProductWriteSerializer,
        responses={
            200: ProductDetailSerializer,
            400: OpenApiResponse(description="Validation or business rule error"),
            404: OpenApiResponse(description="Product not found"),
        },
        examples=[
            OpenApiExample(
                "Update existing product variants",
                value={
                    "sku": "TEE-BASE",
                    "name": "T-Shirt Updated",
                    "price": "105.00",
                    "quantity": 40,
                    "variants": [
                        {
                            "id": 11,
                            "sku": "TEE-RED-M",
                            "price_override": "119.00",
                            "stock_quantity": 9,
                            "is_active": True,
                            "option_ids": [101, 202],
                        }
                    ],
                },
                request_only=True,
            )
        ],
    )
    @method_decorator(require_permission("catalog.update_product"))
    def put(self, request, product_id: int):
        return self._update(request=request, product_id=product_id)

    @extend_schema(
        tags=["Catalog / Variants"],
        summary="Partially update product and nested variants",
        request=ProductWriteSerializer,
        responses={
            200: ProductDetailSerializer,
            400: OpenApiResponse(description="Validation or business rule error"),
            404: OpenApiResponse(description="Product not found"),
        },
    )
    @method_decorator(require_permission("catalog.update_product"))
    def patch(self, request, product_id: int):
        return self._update(request=request, product_id=product_id)

    def _update(self, *, request, product_id: int):
        store = require_store(request)
        product = Product.objects.filter(id=product_id, store_id=store.id).first()
        if not product:
            return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProductWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            product = ProductConfigurationService.upsert_product_with_variants(
                store=store,
                payload=serializer.validated_data,
                product=product,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ProductDetailSerializer(product).data, status=status.HTTP_200_OK)


class VariantStockAPI(APIView):
    """Return stock for a specific variant scoped by current store."""

    @extend_schema(
        tags=["Catalog / Variants"],
        summary="Get variant stock",
        responses={
            200: inline_serializer(
                name="VariantStockResponse",
                fields={
                    "variant_id": serializers.IntegerField(),
                    "product_id": serializers.IntegerField(),
                    "sku": serializers.CharField(),
                    "stock_quantity": serializers.IntegerField(),
                    "is_active": serializers.BooleanField(),
                },
            ),
            404: OpenApiResponse(description="Variant not found"),
        },
    )
    def get(self, request, variant_id: int):
        store = require_store(request)
        variant = ProductVariant.objects.filter(id=variant_id, store_id=store.id).first()
        if not variant:
            return Response({"detail": "Variant not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(
            {
                "variant_id": variant.id,
                "product_id": variant.product_id,
                "sku": variant.sku,
                "stock_quantity": variant.stock_quantity,
                "is_active": variant.is_active,
            }
        )


class VariantPriceResolveAPI(APIView):
    """Resolve final unit price from product base price + optional variant override."""

    @extend_schema(
        tags=["Catalog / Variants"],
        summary="Resolve product or variant price",
        parameters=[
            OpenApiParameter(
                name="variant_id",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Optional variant id for override pricing",
            ),
        ],
        responses={
            200: inline_serializer(
                name="VariantPriceResponse",
                fields={
                    "product_id": serializers.IntegerField(),
                    "variant_id": serializers.IntegerField(allow_null=True),
                    "price": serializers.CharField(),
                },
            ),
            404: OpenApiResponse(description="Product or variant not found"),
        },
        examples=[
            OpenApiExample(
                "Resolve base product price",
                value={"product_id": 15, "variant_id": None, "price": "100.00"},
                response_only=True,
            ),
            OpenApiExample(
                "Resolve variant override price",
                value={"product_id": 15, "variant_id": 33, "price": "120.00"},
                response_only=True,
            ),
        ],
    )
    def get(self, request, product_id: int):
        store = require_store(request)
        variant_id = request.query_params.get("variant_id")

        variant_id_int = None
        if variant_id:
            try:
                variant_id_int = int(variant_id)
            except (TypeError, ValueError):
                return Response({"detail": "Variant not found."}, status=status.HTTP_404_NOT_FOUND)

        def _resolve_payload() -> dict | None:
            product = Product.objects.filter(id=product_id, store_id=store.id).first()
            if not product:
                return None

            variant = None
            if variant_id_int is not None:
                try:
                    variant = ProductVariantService.get_variant_for_store(
                        store_id=store.id,
                        product_id=product.id,
                        variant_id=variant_id_int,
                    )
                except (ValueError, TypeError):
                    return {"_variant_not_found": True}

            resolved_price = VariantPricingService.resolve_price(product=product, variant=variant)
            return {
                "product_id": product.id,
                "variant_id": variant.id if variant else None,
                "price": str(resolved_price),
            }

        payload, _ = StoreCacheService.get_or_set(
            store_id=store.id,
            namespace="variant_price",
            key_parts=[product_id, variant_id_int or "none"],
            producer=_resolve_payload,
            timeout=180,
        )

        if payload is None:
            return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)
        if payload.get("_variant_not_found"):
            return Response({"detail": "Variant not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response(payload)
