from __future__ import annotations

from django.conf import settings
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator


class OnboardingProfile(models.Model):
    store = models.ForeignKey(
        "stores.Store",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="onboarding_profiles",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="onboarding_profiles",
    )
    country = models.CharField(max_length=10, default="SA")
    language = models.CharField(max_length=10, default="ar")
    device_type = models.CharField(max_length=32, default="web")
    business_type = models.CharField(max_length=64)
    expected_products = models.PositiveIntegerField(null=True, blank=True)
    expected_orders_per_day = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["business_type", "country"]),
        ]

    def __str__(self) -> str:
        return f"profile={self.id} user={self.user_id}"


class OnboardingDecision(models.Model):
    profile = models.OneToOneField(
        OnboardingProfile,
        on_delete=models.CASCADE,
        related_name="decision",
    )
    recommended_plan = models.ForeignKey(
        "subscriptions.SubscriptionPlan",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="onboarding_decisions",
    )
    recommended_plan_code = models.CharField(max_length=32, default="BASIC")
    needs_variants = models.BooleanField(default=False)
    recommended_theme = models.CharField(max_length=100, default="default")
    recommended_categories = models.JSONField(default=list, blank=True)
    shipping_profile = models.JSONField(default=dict, blank=True)
    complexity_score = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    rationale = models.TextField(blank=True, default="")
    llm_used = models.BooleanField(default=False)
    llm_confidence = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["profile"], name="uq_onboarding_decision_profile"),
        ]
        indexes = [
            models.Index(fields=["recommended_plan_code", "complexity_score"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"decision={self.id} profile={self.profile_id}"


class ProvisioningRequest(models.Model):
    profile = models.ForeignKey(
        OnboardingProfile,
        on_delete=models.CASCADE,
        related_name="provisioning_requests",
    )
    store = models.ForeignKey(
        "stores.Store",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="provisioning_requests",
    )
    idempotency_key = models.CharField(max_length=120)
    status = models.CharField(max_length=20, default="pending")
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "idempotency_key"],
                name="uq_provisioning_profile_idempotency_key",
            )
        ]
        indexes = [
            models.Index(fields=["idempotency_key"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"profile={self.profile_id} key={self.idempotency_key}"


class ProvisioningActionLog(models.Model):
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]

    store = models.ForeignKey(
        "stores.Store",
        on_delete=models.CASCADE,
        related_name="provisioning_action_logs",
    )
    profile = models.ForeignKey(
        OnboardingProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="provisioning_action_logs",
    )
    idempotency_key = models.CharField(max_length=120, default="")
    action = models.CharField(max_length=120)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SUCCESS)
    error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["store", "created_at"]),
            models.Index(fields=["action", "status"]),
            models.Index(fields=["idempotency_key"]),
        ]

    def __str__(self) -> str:
        return f"store={self.store_id} action={self.action} status={self.status}"
