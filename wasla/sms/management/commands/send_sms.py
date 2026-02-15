from __future__ import annotations

from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from sms.application.use_cases.send_sms import SendSmsCommand, SendSmsUseCase
from tenants.models import Tenant


class Command(BaseCommand):
    help = "Send an SMS using the configured SMS provider (tenant-aware)."

    def add_arguments(self, parser):
        parser.add_argument("--to", action="append", required=True, help="Recipient phone (repeatable).")
        parser.add_argument("--body", required=True, help="Message text.")
        parser.add_argument("--sender", default="", help="Sender name (optional; uses configured default).")
        parser.add_argument("--tenant", default="", help="Tenant slug or id (optional).")
        parser.add_argument(
            "--scheduled",
            default="",
            help="Schedule time (ISO like 2026-02-06T14:26). Optional.",
        )

    def handle(self, *args, **options):
        recipients: list[str] = options["to"] or []
        body: str = options["body"]
        sender: str = options["sender"] or ""
        tenant_arg: str = options["tenant"] or ""
        scheduled_raw: str = options["scheduled"] or ""

        tenant = self._resolve_tenant(tenant_arg) if tenant_arg else None
        scheduled_at = self._parse_scheduled(scheduled_raw) if scheduled_raw else None

        result = SendSmsUseCase.execute(
            SendSmsCommand(
                body=body,
                recipients=recipients,
                sender=sender or None,
                scheduled_at=scheduled_at,
                tenant=tenant,
                user=None,
                metadata={"source": "management_command"},
            )
        )

        self.stdout.write(self.style.SUCCESS(f"Sent SMS via {result.provider} (status={result.status}, log_id={result.log_id})"))

    @staticmethod
    def _resolve_tenant(raw: str) -> Tenant | None:
        raw = (raw or "").strip()
        if not raw:
            return None
        try:
            tenant_id = int(raw)
        except ValueError:
            tenant_id = None
        if tenant_id is not None:
            return Tenant.objects.filter(id=tenant_id, is_active=True).first()
        return Tenant.objects.filter(slug=raw, is_active=True).first()

    @staticmethod
    def _parse_scheduled(raw: str) -> datetime:
        value = (raw or "").strip()
        if not value:
            raise CommandError("Invalid --scheduled value.")
        try:
            scheduled_at = datetime.fromisoformat(value)
        except ValueError as exc:
            raise CommandError("Invalid --scheduled value. Use ISO like 2026-02-06T14:26") from exc

        if timezone.is_naive(scheduled_at):
            scheduled_at = timezone.make_aware(scheduled_at, timezone.get_current_timezone())
        return scheduled_at

