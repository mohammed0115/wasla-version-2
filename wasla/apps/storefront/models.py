"""Storefront models for SEO and customer features."""
from django.db import models
from django.utils.text import slugify


class ProductSEO(models.Model):
    """SEO metadata for products."""

    product = models.OneToOneField(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="seo"
    )
    slug = models.SlugField(max_length=255, unique=True)
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.CharField(max_length=500, blank=True)
    og_image = models.ImageField(upload_to="seo/og/", blank=True, null=True)
    canonical_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Product SEO"
        verbose_name_plural = "Product SEOs"

    def __str__(self) -> str:
        return f"SEO: {self.product.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.product.name)
        if not self.meta_title:
            self.meta_title = self.product.name
        if not self.meta_description:
            desc = self.product.description_ar or self.product.description_en
            self.meta_description = desc[:500] if desc else ""
        super().save(*args, **kwargs)


class CategorySEO(models.Model):
    """SEO metadata for categories."""

    category = models.OneToOneField(
        "catalog.Category",
        on_delete=models.CASCADE,
        related_name="seo"
    )
    slug = models.SlugField(max_length=255, unique=True)
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.CharField(max_length=500, blank=True)
    og_image = models.ImageField(upload_to="seo/og/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Category SEO"
        verbose_name_plural = "Category SEOs"

    def __str__(self) -> str:
        return f"SEO: {self.category.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.category.name)
        if not self.meta_title:
            self.meta_title = self.category.name
        super().save(*args, **kwargs)


class ProductSearch(models.Model):
    """Full-text search index for products."""

    product = models.OneToOneField(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="search_index"
    )
    search_text = models.TextField()  # Denormalized text for search
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Product Search Index"
        verbose_name_plural = "Product Search Indexes"
        indexes = [
            models.Index(fields=["search_text"]),
        ]

    def __str__(self) -> str:
        return f"Search: {self.product.id}"

    @staticmethod
    def build_search_text(product) -> str:
        """Build searchable text from product fields."""
        parts = [
            product.name,
            product.sku,
            product.description_en,
            product.description_ar,
        ]
        return " ".join(str(p) for p in parts if p)

    def save(self, *args, **kwargs):
        if not self.search_text:
            self.search_text = self.build_search_text(self.product)
        super().save(*args, **kwargs)


class StorefrontSettings(models.Model):
    """Global storefront configuration per store."""

    store = models.OneToOneField(
        "stores.Store",
        on_delete=models.CASCADE,
        related_name="storefront_settings"
    )
    product_per_page = models.PositiveIntegerField(default=20)
    enable_search = models.BooleanField(default=True)
    enable_filters = models.BooleanField(default=True)
    enable_wishlist = models.BooleanField(default=True)
    enable_reviews = models.BooleanField(default=False)
    default_currency = models.CharField(max_length=10, default="SAR")
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.15)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Storefront Settings"
        verbose_name_plural = "Storefront Settings"

    def __str__(self) -> str:
        return f"Storefront: {self.store.name}"
