"""
Theme & Branding models.
"""

from django.db import models

from apps.tenants.managers import TenantManager


class Theme(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name_key = models.CharField(max_length=100)
    preview_image_path = models.CharField(max_length=255, blank=True, default="")
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.code


def branding_logo_upload_to(instance: "StoreBranding", filename: str) -> str:
    return f"store_{instance.store_id}/branding/{filename}"


class StoreBranding(models.Model):
    objects = TenantManager()
    store_id = models.IntegerField(db_index=True)
    theme_code = models.CharField(max_length=50, blank=True, default="")
    logo_path = models.ImageField(upload_to=branding_logo_upload_to, blank=True, null=True)
    primary_color = models.CharField(max_length=7, blank=True, default="")
    secondary_color = models.CharField(max_length=7, blank=True, default="")
    accent_color = models.CharField(max_length=7, blank=True, default="")
    font_family = models.CharField(max_length=80, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("store_id",), name="uq_store_branding_store"),
        ]
        indexes = [
            models.Index(fields=["store_id"]),
        ]

    def __str__(self) -> str:
        return f"Branding {self.store_id}"
