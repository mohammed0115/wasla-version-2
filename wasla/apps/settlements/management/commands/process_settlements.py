"""
Django management command to manually process settlements.

Usage:
    python manage.py process_settlements
    python manage.py process_settlements --store-id 123
    python manage.py process_settlements --auto-approve
    python manage.py process_settlements --dry-run
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.settlements.tasks import (
    process_pending_settlements,
    process_single_store_settlement,
)


class Command(BaseCommand):
    help = "Process pending settlements for stores (respects 24h policy)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--store-id",
            type=int,
            help="Process settlement for specific store ID",
        )
        parser.add_argument(
            "--store-ids",
            nargs="+",
            type=int,
            help="Process settlements for multiple store IDs",
        )
        parser.add_argument(
            "--auto-approve",
            action="store_true",
            help="Automatically approve created settlements",
        )
        parser.add_argument(
            "--async",
            action="store_true",
            dest="async_mode",
            help="Run task asynchronously via Celery",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be processed without creating settlements",
        )

    def handle(self, *args, **options):
        store_id = options.get("store_id")
        store_ids = options.get("store_ids")
        auto_approve = options.get("auto_approve", False)
        async_mode = options.get("async_mode", False)
        dry_run = options.get("dry_run", False)

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No settlements will be created")
            )
            self._dry_run(store_id=store_id, store_ids=store_ids)
            return

        if async_mode:
            self._run_async(
                store_id=store_id,
                store_ids=store_ids,
                auto_approve=auto_approve,
            )
        else:
            self._run_sync(
                store_id=store_id,
                store_ids=store_ids,
                auto_approve=auto_approve,
            )

    def _run_sync(self, store_id=None, store_ids=None, auto_approve=False):
        """Run settlement processing synchronously."""
        self.stdout.write("Starting settlement processing (synchronous)...")

        if store_id:
            # Process single store
            result = process_single_store_settlement(
                store_id=store_id,
                auto_approve=auto_approve,
            )
            self._display_result(result, single_store=True)

        else:
            # Process all or multiple stores
            result = process_pending_settlements(
                auto_approve=auto_approve,
                store_ids=store_ids,
            )
            self._display_result(result, single_store=False)

    def _run_async(self, store_id=None, store_ids=None, auto_approve=False):
        """Run settlement processing asynchronously via Celery."""
        self.stdout.write("Starting settlement processing (asynchronous)...")

        if store_id:
            task = process_single_store_settlement.delay(
                store_id=store_id,
                auto_approve=auto_approve,
            )
            self.stdout.write(
                self.style.SUCCESS(f"Task queued for store {store_id}: {task.id}")
            )

        else:
            task = process_pending_settlements.delay(
                auto_approve=auto_approve,
                store_ids=store_ids,
            )
            self.stdout.write(self.style.SUCCESS(f"Task queued: {task.id}"))

        self.stdout.write(
            f"\nCheck task status with:\n"
            f"  python manage.py check_task_status {task.id}"
        )

    def _dry_run(self, store_id=None, store_ids=None):
        """Show what would be processed without creating settlements."""
        from datetime import timedelta
        from django.db.models import Count, Exists, OuterRef, Sum

        from apps.orders.models import Order
        from apps.settlements.models import SettlementItem
        from apps.stores.models import Store

        cutoff_time = timezone.now() - timedelta(hours=24)

        stores_qs = Store.objects.filter(status="active")
        if store_id:
            stores_qs = stores_qs.filter(id=store_id)
        elif store_ids:
            stores_qs = stores_qs.filter(id__in=store_ids)

        self.stdout.write(f"\nCutoff time (24h policy): {cutoff_time}\n")

        for store in stores_qs:
            already_settled = SettlementItem.objects.filter(order_id=OuterRef("pk"))

            eligible_orders = (
                Order.objects.for_tenant(store.id)
                .filter(
                    payment_status="paid",
                    created_at__lt=cutoff_time,
                )
                .annotate(is_settled=Exists(already_settled))
                .filter(is_settled=False)
            )

            stats = eligible_orders.aggregate(
                count=Count("id"),
                total=Sum("total_amount"),
            )

            if stats["count"] > 0:
                self.stdout.write(
                    f"\n{self.style.SUCCESS('✓')} Store {store.id} ({store.name}):"
                )
                self.stdout.write(f"  Orders: {stats['count']}")
                self.stdout.write(f"  Total amount: {stats['total']}")
            else:
                self.stdout.write(
                    f"\n{self.style.WARNING('○')} Store {store.id} ({store.name}): No eligible orders"
                )

    def _display_result(self, result, single_store=False):
        """Display settlement processing results."""
        if single_store:
            if result["settlement_created"]:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n✓ Settlement created: ID {result['settlement_id']}"
                    )
                )
                self.stdout.write(f"  Orders processed: {result['orders_count']}")
                self.stdout.write(f"  Gross amount: {result['gross_amount']}")
                self.stdout.write(f"  Net amount: {result['net_amount']}")

                if result["settlement_approved"]:
                    self.stdout.write(self.style.SUCCESS("  Status: Approved"))
                else:
                    self.stdout.write("  Status: Created (pending approval)")
            else:
                self.stdout.write(
                    self.style.WARNING("No eligible orders for settlement")
                )

        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✓ Processed {result['total_stores']} stores"
                )
            )
            self.stdout.write(
                f"  Settlements created: {result['settlements_created']}"
            )
            self.stdout.write(
                f"  Settlements approved: {result['settlements_approved']}"
            )
            self.stdout.write(
                f"  Total orders: {result['total_orders_processed']}"
            )
            self.stdout.write(
                f"  Total amount: {result['total_amount_settled']}"
            )

            if result["errors"]:
                self.stdout.write(
                    self.style.ERROR(f"\n✗ Errors ({len(result['errors'])}):")
                )
                for error in result["errors"]:
                    self.stdout.write(f"  - {error}")
