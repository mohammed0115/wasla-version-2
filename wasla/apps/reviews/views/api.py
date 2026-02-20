
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from apps.catalog.models import Product
from ..models import Review
from ..services.review_service import ReviewService
from ..serializers import ReviewSerializer
from apps.tenants.guards import require_store, require_tenant

class ReviewCreateAPI(APIView):
    def post(self, request):
        store = require_store(request)
        tenant = require_tenant(request)
        product = Product.objects.filter(id=request.data.get("product_id"), store_id=store.id).first()
        if not product:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        review = ReviewService.create_review(
            product=product,
            customer=request.user.customer,
            rating=request.data.get("rating"),
            comment=request.data.get("comment", "")
        )
        return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)

class ProductReviewsAPI(APIView):
    def get(self, request, product_id):
        store = require_store(request)
        reviews = Review.objects.for_tenant(store).filter(product_id=product_id, status="approved")
        return Response(ReviewSerializer(reviews, many=True).data)
