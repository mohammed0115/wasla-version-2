from __future__ import annotations

from django.db import models


class Event(models.Model):
    ACTOR_ANON = "ANON"
    ACTOR_CUSTOMER = "CUSTOMER"
    ACTOR_MERCHANT = "MERCHANT"
    ACTOR_ADMIN = "ADMIN"

    ACTOR_CHOICES = [
        (ACTOR_ANON, "Anon"),
        (ACTOR_CUSTOMER, "Customer"),
        (ACTOR_MERCHANT, "Merchant"),
        (ACTOR_ADMIN, "Admin"),
    ]

    tenant_id = models.IntegerField(db_index=True)
    event_name = models.CharField(max_length=120)
    actor_type = models.CharField(max_length=20, choices=ACTOR_CHOICES, default=ACTOR_ANON)
    actor_id_hash = models.CharField(max_length=64, blank=True, default="")
    session_key_hash = models.CharField(max_length=64, blank=True, default="")
    object_type = models.CharField(max_length=50, blank=True, default="")
    object_id = models.CharField(max_length=64, blank=True, default="")
    properties_json = models.JSONField(default=dict, blank=True)
    user_agent = models.CharField(max_length=255, blank=True, default="")
    ip_hash = models.CharField(max_length=64, blank=True, default="")
    occurred_at = models.DateTimeField()

    class Meta:
        indexes = [
            models.Index(fields=["tenant_id", "event_name", "occurred_at"]),
            models.Index(fields=["tenant_id", "occurred_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.tenant_id}:{self.event_name}"


class Experiment(models.Model):
    STATUS_DRAFT = "DRAFT"
    STATUS_RUNNING = "RUNNING"
    STATUS_PAUSED = "PAUSED"
    STATUS_ENDED = "ENDED"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_RUNNING, "Running"),
        (STATUS_PAUSED, "Paused"),
        (STATUS_ENDED, "Ended"),
    ]

    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    key = models.CharField(max_length=120, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    variants_json = models.JSONField(default=dict, blank=True)
    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.key


class ExperimentAssignment(models.Model):
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE, related_name="assignments")
    tenant_id = models.IntegerField(db_index=True)
    actor_id_hash = models.CharField(max_length=64, blank=True, default="")
    session_key_hash = models.CharField(max_length=64, blank=True, default="")
    variant = models.CharField(max_length=20)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["experiment", "actor_id_hash", "session_key_hash"],
                name="uq_experiment_assignment_identity",
            )
        ]
        indexes = [
            models.Index(fields=["tenant_id", "assigned_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.experiment_id}:{self.variant}"


class RiskAssessment(models.Model):
    LEVEL_LOW = "LOW"
    LEVEL_MEDIUM = "MEDIUM"
    LEVEL_HIGH = "HIGH"

    LEVEL_CHOICES = [
        (LEVEL_LOW, "Low"),
        (LEVEL_MEDIUM, "Medium"),
        (LEVEL_HIGH, "High"),
    ]

    tenant_id = models.IntegerField(db_index=True)
    order_id = models.IntegerField(db_index=True)
    score = models.PositiveSmallIntegerField(default=0)
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default=LEVEL_LOW)
    reasons_json = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant_id", "order_id"], name="uq_risk_tenant_order"),
        ]
        indexes = [
            models.Index(fields=["tenant_id", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.tenant_id}:{self.order_id}:{self.level}"


class RecommendationSnapshot(models.Model):
    STRATEGY_RULES_V1 = "RULES_V1"

    tenant_id = models.IntegerField(db_index=True)
    context = models.CharField(max_length=40)
    object_id = models.CharField(max_length=64, blank=True, default="")
    recommended_ids_json = models.JSONField(default=list, blank=True)
    strategy = models.CharField(max_length=40, default=STRATEGY_RULES_V1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant_id", "context", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.tenant_id}:{self.context}"
