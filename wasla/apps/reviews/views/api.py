
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from apps.catalog.models import Product
from apps.customers.models import Customer
from ..models import Review
from ..services.review_service import ReviewService
from ..serializers import ReviewSerializer, ReviewModerationSerializer
from apps.security.rbac import require_permission
from apps.tenants.guards import require_store, require_tenant

class ReviewCreateAPI(APIView):
    def post(self, request):
        store = require_store(request)
        require_tenant(request)
        product = Product.objects.filter(id=request.data.get("product_id"), store_id=store.id).first()
        if not product:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        customer = Customer.objects.filter(store_id=store.id, email=getattr(request.user, "email", "")).first()
        if not customer:
            return Response({"detail": "Customer not found for current store."}, status=status.HTTP_400_BAD_REQUEST)

        review = ReviewService.create_review(
            product=product,
            customer=customer,
            rating=request.data.get("rating"),
            comment=request.data.get("comment", "")
        )
        return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)

class ProductReviewsAPI(APIView):
    def get(self, request, product_id):
        store = require_store(request)
        reviews = Review.objects.filter(product_id=product_id, product__store_id=store.id, status="approved")
        return Response(ReviewSerializer(reviews, many=True).data)


class PendingReviewsAPI(APIView):
    @method_decorator(require_permission("reviews.view_pending"))
    def get(self, request):
        store = require_store(request)
        require_tenant(request)
        reviews = Review.objects.filter(product__store_id=store.id, status="pending").order_by("-created_at")
        return Response(ReviewSerializer(reviews, many=True).data)


class ReviewModerationAPI(APIView):
    @method_decorator(require_permission("reviews.moderate"))
    def patch(self, request, review_id):
        store = require_store(request)
        require_tenant(request)
        review = get_object_or_404(
            Review.objects.select_related("product").filter(product__store_id=store.id),
            id=review_id,
        )

        serializer = ReviewModerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        decision = serializer.validated_data["status"]

        if decision == "approved":
            ReviewService.approve_review(review)
        elif decision == "rejected":
            ReviewService.reject_review(review)
        else:
            return Response({"detail": "Invalid moderation status."}, status=status.HTTP_400_BAD_REQUEST)

        review.refresh_from_db()
        return Response(ReviewSerializer(review).data, status=status.HTTP_200_OK)
