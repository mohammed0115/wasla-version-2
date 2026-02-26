from __future__ import annotations

import uuid

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models

from apps.tenants.managers import TenantManager


def ar_glb_upload_to(instance, filename: str) -> str:
    return f"store_{instance.product.store_id}/ar/{filename}"


def ar_texture_upload_to(instance, filename: str) -> str:
    return f"store_{instance.product.store_id}/ar/textures/{filename}"


class ProductARAsset(models.Model):
    """Backend AR asset metadata for a product."""

    objects = TenantManager()
    TENANT_FIELD = "store_id"

    store_id = models.IntegerField(db_index=True)
    product = models.OneToOneField(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="ar_asset",
    )
    glb_file = models.FileField(
        upload_to=ar_glb_upload_to,
        validators=[FileExtensionValidator(allowed_extensions=["glb"])],
    )
    texture_image = models.ImageField(upload_to=ar_texture_upload_to, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["store_id", "is_active"]),
        ]

    def save(self, *args, **kwargs):
        self.store_id = self.product.store_id
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"AR Asset product={self.product_id} store={self.store_id}"


class ARSession(models.Model):
    """Tracks user sessions that request AR try-on data."""

    objects = TenantManager()
    TENANT_FIELD = "store_id"

    store_id = models.IntegerField(db_index=True)
    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="ar_sessions")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ar_sessions",
    )
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata_json = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["store_id", "started_at"]),
            models.Index(fields=["tenant_id", "started_at"]),
            models.Index(fields=["product", "started_at"]),
        ]

    def __str__(self) -> str:
        return f"AR Session {self.session_id} product={self.product_id}"
