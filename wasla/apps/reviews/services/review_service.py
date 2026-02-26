
from ..models import Review

class ReviewService:

    @staticmethod
    def create_review(product, customer, rating, comment=""):
        try:
            rating_value = int(rating)
        except (TypeError, ValueError):
            raise ValueError("Rating must be between 1 and 5")

        if rating_value < 1 or rating_value > 5:
            raise ValueError("Rating must be between 1 and 5")

        return Review.objects.create(
            product=product,
            customer=customer,
            rating=rating_value,
            comment=comment,
            status="pending"
        )

    @staticmethod
    def approve_review(review):
        review.status = "approved"
        review.save(update_fields=["status"])

    @staticmethod
    def reject_review(review):
        review.status = "rejected"
        review.save(update_fields=["status"])
