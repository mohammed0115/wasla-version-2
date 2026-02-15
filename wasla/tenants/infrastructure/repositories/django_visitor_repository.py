from __future__ import annotations

from datetime import timedelta

from django.apps import apps
from django.utils import timezone

from tenants.application.interfaces.visitor_repository_port import VisitorRepositoryPort


class DjangoVisitorRepository(VisitorRepositoryPort):
    def count_visitors_last_7_days(self, tenant_id: int) -> int:
        try:
            visitor_model = apps.get_model("analytics", "VisitorEvent")
        except LookupError:
            return 0

        now = timezone.now()
        start_7d = now - timedelta(days=7)
        return (
            visitor_model.objects.filter(tenant_id=tenant_id, created_at__gte=start_7d)
            .values("session_key")
            .distinct()
            .count()
        )