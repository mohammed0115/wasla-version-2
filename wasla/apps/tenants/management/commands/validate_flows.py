from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.test import Client

from apps.tenants.application.use_cases.user_flows.runner import run_all_flows
from apps.tenants.models import Tenant


class Command(BaseCommand):
    help = "Validate user flows using Django test client (PASS/FAIL with reasons)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant",
            default="default",
            help="Tenant slug or numeric id.",
        )
        parser.add_argument(
            "--fail-fast",
            action="store_true",
            help="Stop on first failing flow.",
        )

    def handle(self, *args, **options):
        tenant_arg: str = options["tenant"]
        fail_fast: bool = options["fail_fast"]

        tenant = self._resolve_tenant(tenant_arg)
        if not tenant:
            raise CommandError(f"Tenant not found: {tenant_arg!r}")

        client = Client()
        reports = run_all_flows(tenant_slug=tenant.slug, client=client)

        failures = 0
        for report in reports:
            if report.passed:
                self.stdout.write(self.style.SUCCESS(f"[PASS] {report.name} (tenant={report.tenant_slug})"))
                continue

            failures += 1
            self.stdout.write(self.style.ERROR(f"[FAIL] {report.name} (tenant={report.tenant_slug})"))
            for step in report.steps:
                if not step.ok:
                    self.stdout.write(f"  - {step.name}: {step.details}")

            if fail_fast:
                raise CommandError("Flow validation failed (fail-fast).")

        if failures:
            raise CommandError(f"Flow validation failed: {failures} flow(s) failed.")

        self.stdout.write(self.style.SUCCESS("All flow validations passed."))

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
