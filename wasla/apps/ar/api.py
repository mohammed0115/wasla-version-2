from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.ar.models import ARSession, ProductARAsset
from apps.ar.serializers import ProductARDataSerializer
from apps.cart.interfaces.api.responses import api_response
from apps.catalog.models import Product
from apps.tenants.guards import require_store, require_tenant


class ProductARDataAPI(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["AR"],
        summary="Get AR try-on data for a product",
        responses={200: ProductARDataSerializer},
    )
    def get(self, request, product_id: int):
        store = require_store(request)
        tenant = require_tenant(request)

        product = Product.objects.filter(id=product_id, store_id=store.id, is_active=True).first()
        if not product:
            return api_response(success=False, errors=["product_not_found"], status_code=status.HTTP_404_NOT_FOUND)

        asset = ProductARAsset.objects.filter(product_id=product.id, store_id=store.id, is_active=True).first()
        if not asset:
            return api_response(success=False, errors=["ar_asset_not_found"], status_code=status.HTTP_404_NOT_FOUND)

        session_key = request.session.session_key
        if not session_key:
            request.session.save()
            session_key = request.session.session_key

        ARSession.objects.create(
            store_id=store.id,
            tenant_id=tenant.id if tenant else None,
            product=product,
            user=request.user if request.user.is_authenticated else None,
            user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:255],
            ip_address=request.META.get("REMOTE_ADDR"),
            metadata_json={"session_key": session_key or ""},
        )

        data = {
            "product_id": product.id,
            "model_url": asset.glb_file.url,
            "texture_url": asset.texture_image.url if asset.texture_image else None,
            "metadata": asset.metadata_json,
        }
        return api_response(success=True, data=data)
