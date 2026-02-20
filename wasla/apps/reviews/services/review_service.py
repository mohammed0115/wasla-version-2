
from ..models import Review
from apps.stores.models import Store

class ReviewService:

    @staticmethod
    def create_review(product, customer, rating, comment=""):
        if rating < 1 or rating > 5:
            raise ValueError("Rating must be between 1 and 5")

        store_id = getattr(product, "store_id", None)
        tenant_id = (
            Store.objects.filter(id=store_id)
            .values_list("tenant_id", flat=True)
            .first()
            if store_id is not None
            else None
        )
        return Review.objects.create(
            tenant_id=tenant_id,
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
