"""Storefront sitemap for search engine optimization."""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from apps.catalog.models import Product, Category
from apps.storefront.models import ProductSEO, CategorySEO


class StorefrontHomeSitemap(Sitemap):
    """Sitemap for storefront home page."""
    changefreq = "daily"
    priority = 1.0

    def items(self):
        return [{"name": "storefront:home", "priority": 1.0}]

    def location(self, item):
        return reverse(item["name"])


class CategorySitemap(Sitemap):
    """Sitemap for product categories."""
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return CategorySEO.objects.all().select_related("category").order_by("-category__id")

    def location(self, item):
        return reverse("storefront:category", kwargs={"slug": item.slug})

    def lastmod(self, item):
        return item.updated_at

    def priority(self, item):
        return 0.8 if item.category.products.count() > 0 else 0.5


class ProductSitemap(Sitemap):
    """Sitemap for products."""
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return ProductSEO.objects.filter(
            product__is_active=True,
            product__visibility=Product.VISIBILITY_ENABLED
        ).select_related("product").order_by("-product__id")

    def location(self, item):
        return reverse("storefront:product_detail", kwargs={"slug": item.slug})

    def lastmod(self, item):
        return item.updated_at

    def priority(self, item):
        # Higher priority for featured products
        if item.product.variants.exists():
            return 0.7
        return 0.6


# Sitemap index
sitemaps = {
    "home": StorefrontHomeSitemap,
    "categories": CategorySitemap,
    "products": ProductSitemap,
}
