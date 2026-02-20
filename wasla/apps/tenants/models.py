from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q


def tenant_logo_upload_to(instance: "Tenant", filename: str) -> str:
    return f"tenants/{instance.slug}/branding/{filename}"


class Tenant(models.Model):
    slug = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    is_published = models.BooleanField(default=False)
    activated_at = models.DateTimeField(null=True, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)

    domain = models.CharField(max_length=255, blank=True, default="")
    subdomain = models.CharField(max_length=100, blank=True, default="")

    currency = models.CharField(max_length=10, default="SAR")
    language = models.CharField(max_length=10, default="ar")

    logo = models.ImageField(upload_to=tenant_logo_upload_to, blank=True, null=True)
    primary_color = models.CharField(max_length=7, blank=True, default="")
    secondary_color = models.CharField(max_length=7, blank=True, default="")

    setup_step = models.PositiveSmallIntegerField(default=1)
    setup_completed = models.BooleanField(default=False)
    setup_completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name or self.slug

    @property
    def owner(self):
        try:
            profile = self.store_profile
        except Exception:
            return None
        return getattr(profile, "owner", None)

    class Meta:
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["is_published"], name="tenants_tenant_is_pub_idx"),
        ]


class StoreDomain(models.Model):
    STATUS_PENDING_VERIFICATION = "PENDING_VERIFICATION"
    STATUS_VERIFIED = "VERIFIED"
    STATUS_SSL_PENDING = "SSL_PENDING"
    STATUS_SSL_ACTIVE = "SSL_ACTIVE"
    STATUS_PENDING = "PENDING"
    STATUS_VERIFYING = "VERIFYING"
    STATUS_ACTIVE = "ACTIVE"
    STATUS_FAILED = "FAILED"
    STATUS_DISABLED = "DISABLED"

    STATUS_CHOICES = [
        (STATUS_PENDING_VERIFICATION, "Pending Verification"),
        (STATUS_VERIFIED, "Verified"),
        (STATUS_SSL_PENDING, "SSL Pending"),
        (STATUS_SSL_ACTIVE, "SSL Active"),
        (STATUS_PENDING, "Pending"),
        (STATUS_VERIFYING, "Verifying"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_FAILED, "Failed"),
        (STATUS_DISABLED, "Disabled"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="custom_domains")
    domain = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_PENDING_VERIFICATION)
    verification_token = models.CharField(max_length=128, blank=True, default="")
    verified_at = models.DateTimeField(null=True, blank=True)
    ssl_cert_path = models.TextField(blank=True, default="")
    ssl_key_path = models.TextField(blank=True, default="")
    last_check_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["domain"], name="storedomain_domain_idx"),
            models.Index(fields=["tenant", "status"], name="storedomain_tenant_status_idx"),
            models.Index(fields=["status", "last_check_at"], name="storedomain_status_check_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.domain} ({self.status})"


class StoreProfile(models.Model):
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name="store_profile")
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_store_profile",
    )
    store_info_completed = models.BooleanField(default=False)
    setup_step = models.PositiveSmallIntegerField(default=1)
    is_setup_complete = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["store_info_completed"]),
            models.Index(fields=["setup_step"]),
            models.Index(fields=["is_setup_complete"]),
        ]

    def __str__(self) -> str:
        return f"{self.tenant.slug} ({self.owner_id})"


class StorePaymentSettings(models.Model):
    MODE_MANUAL = "manual"
    MODE_DUMMY = "dummy"
    MODE_GATEWAY = "gateway"

    MODE_CHOICES = [
        (MODE_MANUAL, "Manual (offline/COD)"),
        (MODE_DUMMY, "Dummy (testing)"),
        (MODE_GATEWAY, "Gateway (Phase 2)"),
    ]

    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name="payment_settings")
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default=MODE_MANUAL)
    provider_name = models.CharField(max_length=50, blank=True, default="")
    merchant_key = models.CharField(max_length=255, blank=True, default="")
    webhook_secret = models.CharField(max_length=255, blank=True, default="")
    is_enabled = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["mode", "is_enabled"]),
        ]

    def __str__(self) -> str:
        return f"{self.tenant.slug}:{self.mode}"


class StoreShippingSettings(models.Model):
    MODE_PICKUP = "pickup"
    MODE_MANUAL_DELIVERY = "manual_delivery"
    MODE_CARRIER = "carrier"

    MODE_CHOICES = [
        (MODE_PICKUP, "Pickup"),
        (MODE_MANUAL_DELIVERY, "Manual delivery"),
        (MODE_CARRIER, "Carrier (Phase 2)"),
    ]

    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name="shipping_settings")
    fulfillment_mode = models.CharField(max_length=20, choices=MODE_CHOICES, default=MODE_PICKUP)
    origin_city = models.CharField(max_length=100, blank=True, default="")
    delivery_fee_flat = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    free_shipping_threshold = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    is_enabled = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["fulfillment_mode", "is_enabled"]),
        ]

    def __str__(self) -> str:
        return f"{self.tenant.slug}:{self.fulfillment_mode}"


class TenantMembership(models.Model):
    ROLE_OWNER = "owner"
    ROLE_ADMIN = "admin"
    ROLE_STAFF = "staff"
    ROLE_READ_ONLY = "read_only"

    ROLE_CHOICES = [
        (ROLE_OWNER, "Owner"),
        (ROLE_ADMIN, "Admin"),
        (ROLE_STAFF, "Staff"),
        (ROLE_READ_ONLY, "Read-only"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tenant_memberships",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_OWNER)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "user"],
                name="uq_tenant_membership_tenant_user",
            ),
            models.UniqueConstraint(
                fields=["tenant"],
                condition=Q(role="owner") & Q(is_active=True),
                name="uq_tenant_membership_one_owner_per_tenant",
            ),
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(role="owner") & Q(is_active=True),
                name="uq_tenant_membership_one_owned_store_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "role", "is_active"]),
            models.Index(fields=["user", "role", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.tenant.slug}:{self.user_id}:{self.role}"


class TenantAuditLog(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="audit_logs")
    action = models.CharField(max_length=100)
    actor = models.CharField(max_length=100, blank=True, default="system")
    details = models.TextField(blank=True, default="")
    metadata = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "action"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.tenant.slug}:{self.action}:{self.created_at}"
