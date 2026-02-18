
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from apps.catalog.models import Product
from ..models import Review
from ..services.review_service import ReviewService
from ..serializers import ReviewSerializer

class ReviewCreateAPI(APIView):
    def post(self, request):
        product = Product.objects.get(id=request.data.get("product_id"))
        review = ReviewService.create_review(
            product=product,
            customer=request.user.customer,
            rating=request.data.get("rating"),
            comment=request.data.get("comment", "")
        )
        return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)

class ProductReviewsAPI(APIView):
    def get(self, request, product_id):
        reviews = Review.objects.filter(product_id=product_id, status="approved")
        return Response(ReviewSerializer(reviews, many=True).data)
