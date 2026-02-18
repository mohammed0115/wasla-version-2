from django.db import models


class AIRequestLog(models.Model):
    FEATURE_DESCRIPTION = "DESCRIPTION"
    FEATURE_CATEGORY = "CATEGORY"
    FEATURE_SEARCH = "SEARCH"

    FEATURE_CHOICES = [
        (FEATURE_DESCRIPTION, "Description"),
        (FEATURE_CATEGORY, "Category"),
        (FEATURE_SEARCH, "Search"),
    ]

    STATUS_SUCCESS = "SUCCESS"
    STATUS_FAILED = "FAILED"

    STATUS_CHOICES = [
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]

    store_id = models.IntegerField(db_index=True)
    feature = models.CharField(max_length=20, choices=FEATURE_CHOICES)
    provider = models.CharField(max_length=50, default="")
    latency_ms = models.IntegerField(default=0)
    token_count = models.IntegerField(null=True, blank=True)
    cost_estimate = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_SUCCESS)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["store_id", "created_at"]),
            models.Index(fields=["feature", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.store_id}:{self.feature}:{self.status}"


class AIProductEmbedding(models.Model):
    store_id = models.IntegerField(db_index=True)
    product = models.OneToOneField("catalog.Product", on_delete=models.CASCADE, related_name="ai_embedding")
    provider = models.CharField(max_length=50, default="")
    image_fingerprint = models.CharField(max_length=64, blank=True, default="", db_index=True)
    vector = models.JSONField(default=list, blank=True)
    attributes = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["store_id", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Embedding {self.product_id}"
