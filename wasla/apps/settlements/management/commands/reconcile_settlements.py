"""
Django management command to generate reconciliation reports.

Usage:
    python manage.py reconcile_settlements
    python manage.py reconcile_settlements --lookback-days 14
    python manage.py reconcile_settlements --store-id 123
    python manage.py reconcile_settlements --detailed
"""

from django.core.management.base import BaseCommand

from apps.settlements.application.reconciliation import ReconciliationService


class Command(BaseCommand):
    help = "Generate reconciliation report for payments vs settlements"

    def add_arguments(self, parser):
        parser.add_argument(
            "--lookback-days",
            type=int,
            default=7,
            help="Number of days to look back (default: 7)",
        )
        parser.add_argument(
            "--store-id",
            type=int,
            help="Filter by specific store ID",
        )
        parser.add_argument(
            "--detailed",
            action="store_true",
            help="Show detailed list of discrepancies",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output in JSON format",
        )

    def handle(self, *args, **options):
        lookback_days = options["lookback_days"]
        store_id = options.get("store_id")
        detailed = options["detailed"]
        json_output = options["json"]

        self.stdout.write(f"Generating reconciliation report...")
        self.stdout.write(f"Lookback period: {lookback_days} days")
        if store_id:
            self.stdout.write(f"Store ID: {store_id}")
        self.stdout.write("")

        # Generate report
        report = ReconciliationService.generate_reconciliation_report(
            lookback_days=lookback_days,
            store_id=store_id,
        )

        if json_output:
            import json
            self.stdout.write(json.dumps(report.to_dict(), indent=2))
            return

        # Display report
        self._display_report(report, detailed=detailed)

    def _display_report(self, report, detailed=False):
        """Display reconciliation report in human-readable format."""
        # Header
        self.stdout.write(self.style.HTTP_INFO("=" * 70))
        self.stdout.write(
            self.style.HTTP_INFO("SETTLEMENT RECONCILIATION REPORT")
        )
        self.stdout.write(self.style.HTTP_INFO("=" * 70))
        self.stdout.write(f"Period: {report.cutoff_date.date()} to present")
        self.stdout.write(f"Lookback: {report.lookback_days} days")
        self.stdout.write("")

        # Unsettled orders
        self.stdout.write(self.style.WARNING("Unsettled Paid Orders:"))
        self.stdout.write(f"  Count: {report.unsettled_paid_orders_count}")
        self.stdout.write(f"  Amount: {report.unsettled_paid_orders_amount}")
        self.stdout.write("")

        # Orphaned items
        self.stdout.write(self.style.WARNING("Orphaned Settlement Items:"))
        self.stdout.write(f"  Count: {report.orphaned_settlement_items_count}")
        self.stdout.write("")

        # Amount mismatches
        self.stdout.write(self.style.WARNING("Amount Mismatches:"))
        self.stdout.write(f"  Count: {len(report.amount_mismatches)}")
        if detailed and report.amount_mismatches:
            self.stdout.write("\n  Details:")
            for mismatch in report.amount_mismatches[:20]:
                self.stdout.write(
                    f"    - Settlement Item {mismatch['settlement_item_id']}: "
                    f"Order {mismatch['order_id']}"
                )
                self.stdout.write(
                    f"      Settlement: {mismatch['settlement_amount']}, "
                    f"Order: {mismatch['order_amount']}, "
                    f"Diff: {mismatch['difference']}"
                )
        self.stdout.write("")

        # Payment vs Settlement
        self.stdout.write(self.style.SUCCESS("Payment vs Settlement:"))
        self.stdout.write(
            f"  Paid Intents: {report.payment_intents_count} "
            f"({report.payment_intents_amount})"
        )
        self.stdout.write(
            f"  Settled Items: {report.settled_items_count} "
            f"({report.settled_items_amount})"
        )
        self.stdout.write(f"  Difference: {report.payment_settlement_diff}")
        self.stdout.write("")

        # Summary
        if report.has_discrepancies:
            self.stdout.write(
                self.style.ERROR("⚠ DISCREPANCIES DETECTED - Review required!")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("✓ No discrepancies found - All reconciled!")
            )

        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO("=" * 70))

        # Show detailed unsettled orders if requested
        if detailed and report.unsettled_paid_orders_count > 0:
            self.stdout.write("\nDetailed Unsettled Orders:")
            unsettled = ReconciliationService.get_unsettled_orders_details(
                store_id=None,
                limit=50,
            )
            for order in unsettled:
                self.stdout.write(
                    f"  Order {order['order_id']} (Store {order['store_id']}): "
                    f"{order['total_amount']} - {order['hours_since_payment']:.1f}h ago"
                )
