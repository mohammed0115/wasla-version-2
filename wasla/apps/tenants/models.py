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
    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="activated_tenants",
    )
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
    """
    Production-grade custom domain with SSL certificate management.
    
    State Machine:
      PENDING_VERIFICATION -> VERIFIED -> CERT_REQUESTED -> CERT_ISSUED -> ACTIVE
      Any state can transition to FAILED if checks fail
    """
    
    # Refined status choices - state machine
    STATUS_PENDING_VERIFICATION = "pending_verification"
    STATUS_VERIFIED = "verified"
    STATUS_CERT_REQUESTED = "cert_requested"
    STATUS_CERT_ISSUED = "cert_issued"
    STATUS_ACTIVE = "active"
    STATUS_DEGRADED = "degraded"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING_VERIFICATION, "Pending Verification"),
        (STATUS_VERIFIED, "Verified"),
        (STATUS_CERT_REQUESTED, "Certificate Requested"),
        (STATUS_CERT_ISSUED, "Certificate Issued"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_DEGRADED, "Degraded"),
        (STATUS_FAILED, "Failed"),
    ]

    # Verification methods
    METHOD_DNS_TXT = "dns_txt"
    METHOD_DNS_CNAME = "dns_cname"

    VERIFICATION_METHOD_CHOICES = [
        (METHOD_DNS_TXT, "DNS TXT Record"),
        (METHOD_DNS_CNAME, "DNS CNAME Record"),
    ]

    # Certificate provider
    PROVIDER_LETS_ENCRYPT = "lets_encrypt"

    CERT_PROVIDER_CHOICES = [
        (PROVIDER_LETS_ENCRYPT, "Let's Encrypt"),
    ]

    # Relationships
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="custom_domains")
    
    # Domain info
    domain = models.CharField(max_length=255, unique=True, db_index=True)
    is_primary = models.BooleanField(default=False)

    # Verification
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default=STATUS_PENDING_VERIFICATION, db_index=True)
    verification_method = models.CharField(max_length=20, choices=VERIFICATION_METHOD_CHOICES, default=METHOD_DNS_TXT)
    verification_token = models.CharField(max_length=256, unique=True, blank=True, default="")
    verified_at = models.DateTimeField(null=True, blank=True)

    # SSL Certificate
    cert_provider = models.CharField(max_length=25, choices=CERT_PROVIDER_CHOICES, default=PROVIDER_LETS_ENCRYPT)
    cert_issued_at = models.DateTimeField(null=True, blank=True)
    cert_expires_at = models.DateTimeField(null=True, blank=True)
    ssl_cert_path = models.TextField(blank=True, default="")
    ssl_key_path = models.TextField(blank=True, default="")

    # Health & Retry tracking
    last_check_at = models.DateTimeField(null=True, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True, default="")
    retry_count = models.IntegerField(default=0)
    next_retry_at = models.DateTimeField(null=True, blank=True)

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["domain"], name="storedomain_domain_idx"),
            models.Index(fields=["tenant", "status"], name="storedomain_tenant_status_idx"),
            models.Index(fields=["status", "next_retry_at"], name="storedomain_status_retry_idx"),
            models.Index(fields=["cert_expires_at"], name="storedomain_cert_expiry_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.domain} ({self.get_status_display()})"

    @classmethod
    def normalize_domain(cls, domain: str) -> str:
        """Normalize domain: lowercase, strip whitespace."""
        return domain.lower().strip()

    @classmethod
    def generate_verification_token(cls) -> str:
        """Generate cryptographically secure verification token."""
        import secrets
        return secrets.token_urlsafe(32)

    def can_transition_to(self, new_status: str) -> bool:
        """Validate state transitions."""
        valid_transitions = {
            self.STATUS_PENDING_VERIFICATION: [self.STATUS_VERIFIED, self.STATUS_FAILED],
            self.STATUS_VERIFIED: [self.STATUS_CERT_REQUESTED, self.STATUS_FAILED],
            self.STATUS_CERT_REQUESTED: [self.STATUS_CERT_ISSUED, self.STATUS_FAILED],
            self.STATUS_CERT_ISSUED: [self.STATUS_ACTIVE, self.STATUS_FAILED],
            self.STATUS_ACTIVE: [self.STATUS_DEGRADED, self.STATUS_FAILED],
            self.STATUS_DEGRADED: [self.STATUS_ACTIVE, self.STATUS_FAILED],
            self.STATUS_FAILED: [self.STATUS_PENDING_VERIFICATION],
        }
        return new_status in valid_transitions.get(self.status, [])

    def should_retry(self) -> bool:
        """Check if retry is due."""
        if not self.next_retry_at:
            return False
        from django.utils import timezone
        return timezone.now() >= self.next_retry_at

    def calculate_next_retry(self):
        """Exponential backoff: 5, 15, 45, 135, 405 min (capped at 24h)."""
        from django.utils import timezone
        from datetime import timedelta
        backoff_minutes = min(5 * (3 ** self.retry_count), 24 * 60)
        return timezone.now() + timedelta(minutes=backoff_minutes)

    def increment_retry(self):
        """Increment retry counter and set next retry time."""
        self.retry_count += 1
        self.next_retry_at = self.calculate_next_retry()


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


class Permission(models.Model):
    code = models.CharField(max_length=120, unique=True)
    module = models.CharField(max_length=60)
    description = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["module", "code"]),
        ]

    def __str__(self) -> str:
        return self.code


class RolePermission(models.Model):
    role = models.CharField(max_length=20, choices=TenantMembership.ROLE_CHOICES)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name="role_permissions")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["role", "permission"], name="uq_role_permission_role_permission"),
        ]
        indexes = [
            models.Index(fields=["role"]),
        ]

    def __str__(self) -> str:
        return f"{self.role}:{self.permission.code}"


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

class DomainAuditLog(models.Model):
    """Audit trail for custom domain state changes."""
    
    ACTION_CREATED = "created"
    ACTION_STATUS_CHANGED = "status_changed"
    ACTION_VERIFIED = "verified"
    ACTION_CERT_REQUESTED = "cert_requested"
    ACTION_CERT_ISSUED = "cert_issued"
    ACTION_ACTIVATED = "activated"
    ACTION_FAILED = "failed"
    ACTION_RECHECKED = "rechecked"
    ACTION_DELETED = "deleted"

    ACTION_CHOICES = [
        (ACTION_CREATED, "Created"),
        (ACTION_STATUS_CHANGED, "Status Changed"),
        (ACTION_VERIFIED, "Verified"),
        (ACTION_CERT_REQUESTED, "Certificate Requested"),
        (ACTION_CERT_ISSUED, "Certificate Issued"),
        (ACTION_ACTIVATED, "Activated"),
        (ACTION_FAILED, "Failed"),
        (ACTION_RECHECKED, "Rechecked"),
        (ACTION_DELETED, "Deleted"),
    ]

    domain = models.ForeignKey(
        StoreDomain,
        on_delete=models.CASCADE,
        related_name="audit_logs"
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    
    previous_status = models.CharField(max_length=25, blank=True, default="")
    new_status = models.CharField(max_length=25, blank=True, default="")
    
    details = models.JSONField(default=dict, blank=True)
    failure_reason = models.TextField(blank=True, default="")
    
    performed_by = models.CharField(
        max_length=100,
        blank=True,
        default="system",
        help_text="User email or 'system' for automated tasks"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["domain", "created_at"]),
            models.Index(fields=["action", "created_at"]),
        ]
        verbose_name = "Domain Audit Log"
        verbose_name_plural = "Domain Audit Logs"

    def __str__(self) -> str:
        return f"{self.domain.domain} - {self.get_action_display()} at {self.created_at}"