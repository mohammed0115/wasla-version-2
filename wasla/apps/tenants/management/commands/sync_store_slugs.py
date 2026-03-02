from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from apps.stores.models import Store


class Command(BaseCommand):
    help = "Sync Store.slug/subdomain to Tenant.slug for tenants with a single store."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply changes (default: dry-run).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limit number of stores to process.",
        )

    def handle(self, *args, **options):
        apply = bool(options.get("apply"))
        limit = int(options.get("limit") or 0) or None

        qs = Store.objects.select_related("tenant").order_by("id")
        if limit:
            qs = qs[:limit]

        updated = 0
        skipped = 0

        for store in qs:
            tenant = store.tenant
            if tenant is None:
                skipped += 1
                continue

            if Store.objects.filter(tenant_id=tenant.id).count() != 1:
                skipped += 1
                continue

            target = (tenant.slug or tenant.subdomain or "").strip().lower()
            if not target:
                skipped += 1
                continue

            if store.slug == target and store.subdomain == target:
                skipped += 1
                continue

            conflict = Store.objects.filter(
                Q(slug=target) | Q(subdomain=target)
            ).exclude(id=store.id)
            if conflict.exists():
                self.stdout.write(
                    self.style.WARNING(
                        f"SKIP store {store.id}: target '{target}' conflicts with another store."
                    )
                )
                skipped += 1
                continue

            self.stdout.write(
                f"{'APPLY' if apply else 'DRY'} store {store.id}: "
                f"{store.slug}/{store.subdomain} -> {target}"
            )
            if apply:
                with transaction.atomic():
                    store.slug = target
                    store.subdomain = target
                    store.save(update_fields=["slug", "subdomain", "updated_at"])
                updated += 1

        summary = f"Sync complete. updated={updated} skipped={skipped} mode={'apply' if apply else 'dry-run'}"
        self.stdout.write(self.style.SUCCESS(summary))
