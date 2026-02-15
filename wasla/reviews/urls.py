
from django.urls import path
from .views.api import ReviewCreateAPI, ProductReviewsAPI

urlpatterns = [
    path("reviews/create/", ReviewCreateAPI.as_view()),
    path("products/<int:product_id>/reviews/", ProductReviewsAPI.as_view()),
]
