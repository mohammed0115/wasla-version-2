from __future__ import annotations

from django.db import models


class ProductEmbedding(models.Model):
    store_id = models.IntegerField(db_index=True)
    product = models.OneToOneField(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="visual_embedding",
    )
    vector_hash = models.CharField(max_length=64, blank=True, default="")
    similarity_hint = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["store_id", "product"], name="uq_visual_embedding_store_product"),
        ]
        indexes = [
            models.Index(fields=["store_id", "similarity_hint"], name="vs_store_similarity_idx"),
            models.Index(fields=["store_id", "updated_at"], name="vs_store_updated_idx"),
        ]

    def __str__(self) -> str:
        return f"store={self.store_id}:product={self.product_id}"
