from __future__ import annotations

from datetime import datetime, time, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.apps import apps
from django.db import DatabaseError, OperationalError, ProgrammingError
from django.utils import timezone

from tenants.application.interfaces.visitor_repository_port import VisitorRepositoryPort


class DjangoVisitorRepository(VisitorRepositoryPort):
    @staticmethod
    def _tzinfo(tz: str) -> ZoneInfo:
        try:
            return ZoneInfo(tz)
        except Exception:
            return ZoneInfo("UTC")

    def count_visitors_last_7_days(self, store_id: int, tz: str) -> int:
        tzinfo = self._tzinfo(tz)
        local_now = timezone.localtime(timezone.now(), tzinfo)
        start_date = local_now.date() - timedelta(days=6)
        local_start = datetime.combine(start_date, time.min, tzinfo=tzinfo)
        local_end = datetime.combine(local_now.date() + timedelta(days=1), time.min, tzinfo=tzinfo)
        start_7d = local_start.astimezone(dt_timezone.utc)
        end_7d = local_end.astimezone(dt_timezone.utc)

        try:
            visitor_model = apps.get_model("analytics", "VisitorEvent")
        except LookupError:
            try:
                visitor_model = apps.get_model("analytics", "Event")
            except LookupError:
                return 0

        try:
            field_names = {field.name for field in visitor_model._meta.fields}
            if "created_at" in field_names:
                timestamp_field = "created_at"
            elif "occurred_at" in field_names:
                timestamp_field = "occurred_at"
            else:
                return 0

            if "session_key" in field_names:
                session_field = "session_key"
            elif "session_key_hash" in field_names:
                session_field = "session_key_hash"
            else:
                return 0

            return (
                visitor_model.objects.filter(
                    **{
                        ("store_id" if "store_id" in field_names else "tenant_id"): store_id,
                        f"{timestamp_field}__gte": start_7d,
                        f"{timestamp_field}__lt": end_7d,
                    }
                )
                .values(session_field)
                .distinct()
                .count()
            )
        except (DatabaseError, OperationalError, ProgrammingError, Exception):
            return 0
