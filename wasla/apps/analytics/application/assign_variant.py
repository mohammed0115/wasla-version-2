from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256

from django.conf import settings
from django.utils import timezone

from apps.analytics.domain.policies import hash_identifier
from apps.analytics.domain.types import AssignmentDTO
from apps.analytics.models import Experiment, ExperimentAssignment
from apps.tenants.domain.tenant_context import TenantContext


@dataclass(frozen=True)
class AssignVariantCommand:
    tenant_ctx: TenantContext
    experiment_key: str
    actor_id: str | int | None = None
    session_key: str | None = None


class AssignVariantUseCase:
    @staticmethod
    def execute(cmd: AssignVariantCommand) -> AssignmentDTO:
        key = (cmd.experiment_key or "").strip()
        if not key:
            return AssignmentDTO(experiment_key="", variant="A", assigned=False)

        exp = Experiment.objects.filter(key=key).first()
        if not exp:
            return AssignmentDTO(experiment_key=key, variant="A", assigned=False)
        if exp.tenant_id and exp.tenant_id != cmd.tenant_ctx.tenant_id:
            return AssignmentDTO(experiment_key=key, variant="A", assigned=False)

        now = timezone.now()
        if exp.status != Experiment.STATUS_RUNNING:
            return AssignmentDTO(experiment_key=key, variant="A", assigned=False)
        if exp.start_at and now < exp.start_at:
            return AssignmentDTO(experiment_key=key, variant="A", assigned=False)
        if exp.end_at and now > exp.end_at:
            return AssignmentDTO(experiment_key=key, variant="A", assigned=False)

        actor_id = cmd.actor_id if cmd.actor_id is not None else cmd.tenant_ctx.user_id
        session_key = cmd.session_key if cmd.session_key is not None else cmd.tenant_ctx.session_key
        identity = str(actor_id) if actor_id is not None else (session_key or "")
        if not identity:
            return AssignmentDTO(experiment_key=key, variant="A", assigned=False)

        actor_hash = hash_identifier(actor_id) if actor_id is not None else ""
        session_hash = ""
        if not actor_hash:
            session_hash = hash_identifier(session_key) if session_key else ""

        if actor_hash:
            existing = (
                ExperimentAssignment.objects.filter(experiment=exp, actor_id_hash=actor_hash)
                .order_by("-assigned_at")
                .first()
            )
        else:
            existing = (
                ExperimentAssignment.objects.filter(experiment=exp, session_key_hash=session_hash)
                .order_by("-assigned_at")
                .first()
            )
        if existing:
            return AssignmentDTO(experiment_key=key, variant=existing.variant, assigned=True)

        variant = _choose_variant(
            key=key,
            identity=identity,
            variants=exp.variants_json or {"A": 100},
        )
        ExperimentAssignment.objects.create(
            experiment=exp,
            tenant_id=cmd.tenant_ctx.tenant_id,
            actor_id_hash=actor_hash,
            session_key_hash=session_hash,
            variant=variant,
            assigned_at=now,
        )
        return AssignmentDTO(experiment_key=key, variant=variant, assigned=True)


def _choose_variant(*, key: str, identity: str, variants: dict) -> str:
    weights = {str(k): int(v) for k, v in (variants or {"A": 100}).items() if int(v) > 0}
    if not weights:
        return "A"
    total = sum(weights.values())
    salt = (getattr(settings, "ANALYTICS_HASH_SALT", "") or getattr(settings, "SECRET_KEY", "")).strip()
    digest = sha256(f"{salt}:{key}:{identity}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % total
    cumulative = 0
    for variant, weight in weights.items():
        cumulative += weight
        if bucket < cumulative:
            return variant
    return "A"
