from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Plan(models.Model):
    name = models.CharField(max_length=100)
    price_monthly = models.DecimalField(max_digits=8, decimal_places=2)
    price_yearly = models.DecimalField(max_digits=8, decimal_places=2)
    is_popular = models.BooleanField(default=False)
    is_free = models.BooleanField(default=False)

    def __str__(self):
        return self.name


def store_logo_upload_to(instance, filename: str) -> str:
    """Upload path for store logos."""
    return f"stores/{instance.id}/logo/{filename}"


class Store(models.Model):
    """
    Merchant store model.
    
    Each store represents a unique store/shop owned by a merchant.
    Store isolation is achieved via store_id in other models.
    """

    STATUS_DRAFT = "draft"
    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_SUSPENDED = "suspended"

    STATUS_CHOICES = [
        (STATUS_DRAFT, _("Draft")),
        (STATUS_ACTIVE, _("Active")),
        (STATUS_INACTIVE, _("Inactive")),
        (STATUS_SUSPENDED, _("Suspended")),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="stores",
        help_text="User who owns/manages this store"
    )
    
    # Basic information
    name = models.CharField(max_length=255, help_text="Store display name")
    slug = models.SlugField(max_length=255, unique=True, help_text="URL-safe identifier")
    description = models.TextField(blank=True, default="", help_text="Store description")
    
    # Branding
    logo = models.ImageField(
        upload_to=store_logo_upload_to,
        blank=True,
        null=True,
        help_text="Store logo image"
    )
    
    # Category & business info
    category = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Primary business category"
    )
    country = models.CharField(
        max_length=2,
        default="SA",
        help_text="Store country code"
    )
    
    # Domain configuration
    subdomain = models.CharField(
        max_length=255,
        unique=True,
        help_text="Subdomain for store (e.g., mystore.visualai.sa)"
    )
    custom_domain = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
        help_text="Custom domain (premium feature)"
    )
    
    # Plan
    plan = models.ForeignKey(
        Plan,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Subscription plan"
    )
    
    # Theme
    theme_color_primary = models.CharField(
        max_length=7,
        default="#000000",
        help_text="Primary theme color (hex)"
    )
    theme_color_secondary = models.CharField(
        max_length=7,
        default="#ffffff",
        help_text="Secondary theme color (hex)"
    )
    theme_name = models.CharField(
        max_length=100,
        default="default",
        help_text="Theme template name"
    )
    
    # Status & timestamps
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        help_text="Current store status"
    )
    is_featured = models.BooleanField(default=False, help_text="Featured in discover")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    launched_at = models.DateTimeField(null=True, blank=True, help_text="When store went live")
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "created_at"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["subdomain"]),
        ]
        unique_together = [
            ("owner", "slug"),  # Each user's stores must have unique slugs
        ]

    def __str__(self):
        return f"{self.name} ({self.owner.email})"

    @property
    def store_id(self):
        """Return ID as store_id for multi-tenant queries."""
        return self.id

    @property
    def is_published(self):
        """Check if store is published and visible."""
        return self.status == self.STATUS_ACTIVE

    def get_display_domain(self):
        """Get effective domain for store."""
        if self.custom_domain:
            return self.custom_domain
        return f"{self.subdomain}.visualai.sa"


class StoreSettings(models.Model):
    """Settings and configuration for a store."""

    store = models.OneToOneField(Store, on_delete=models.CASCADE, related_name="settings")
    
    # Notifications
    notify_on_order = models.BooleanField(default=True)
    notify_email = models.EmailField(blank=True, default="")
    
    # Inventory
    low_stock_threshold = models.PositiveIntegerField(default=10)
    auto_publish_products = models.BooleanField(default=True)
    
    # Settlement
    settlement_frequency = models.CharField(
        max_length=20,
        choices=[("daily", "Daily"), ("weekly", "Weekly"), ("monthly", "Monthly")],
        default="weekly"
    )
    payout_method = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Bank transfer, wallet, etc."
    )
    
    # Metadata
    metadata_json = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Settings for {self.store.name}"


class StoreSetupStep(models.Model):
    """Track progress through store setup wizard."""

    STEP_BASIC = "basic"
    STEP_PRODUCTS = "products"
    STEP_DESIGN = "design"
    STEP_DOMAIN = "domain"
    
    STEP_CHOICES = [
        (STEP_BASIC, _("Basic Information")),
        (STEP_PRODUCTS, _("Product Upload")),
        (STEP_DESIGN, _("Design & Theme")),
        (STEP_DOMAIN, _("Domain Setup")),
    ]

    store = models.OneToOneField(Store, on_delete=models.CASCADE, related_name="setup_step")
    current_step = models.CharField(
        max_length=20,
        choices=STEP_CHOICES,
        default=STEP_BASIC,
    )
    completed_steps = models.JSONField(default=list, blank=True)  # List of completed step IDs
    
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Setup: {self.store.name} - {self.current_step}"

    def mark_step_complete(self, step: str):
        """Mark a setup step as completed."""
        if step not in self.completed_steps:
            self.completed_steps.append(step)
            self.save()

    def move_to_next_step(self):
        """Move to next setup step."""
        steps = [self.STEP_BASIC, self.STEP_PRODUCTS, self.STEP_DESIGN, self.STEP_DOMAIN]
        current_idx = steps.index(self.current_step) if self.current_step in steps else 0
        if current_idx < len(steps) - 1:
            self.current_step = steps[current_idx + 1]
            self.save()
