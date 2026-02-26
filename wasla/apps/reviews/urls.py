
from django.urls import path
from .views.api import PendingReviewsAPI, ProductReviewsAPI, ReviewCreateAPI, ReviewModerationAPI

urlpatterns = [
    path("reviews/create/", ReviewCreateAPI.as_view()),
    path("products/<int:product_id>/reviews/", ProductReviewsAPI.as_view()),
    path("reviews/moderation/pending/", PendingReviewsAPI.as_view()),
    path("reviews/moderation/<int:review_id>/", ReviewModerationAPI.as_view()),
]
