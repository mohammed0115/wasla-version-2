
from ..models import Review

class ReviewService:

    @staticmethod
    def create_review(product, customer, rating, comment=""):
        if rating < 1 or rating > 5:
            raise ValueError("Rating must be between 1 and 5")

        return Review.objects.create(
            product=product,
            customer=customer,
            rating=rating,
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
