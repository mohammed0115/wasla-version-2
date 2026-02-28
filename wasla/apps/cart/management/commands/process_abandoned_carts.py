"""Django management command to process abandoned carts."""
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.cart.services import AbandonedCartService, AbandonedCartRecoveryEmailService
from apps.stores.models import Store


class Command(BaseCommand):
    help = "Process abandoned carts, mark them, and send recovery emails"

    def add_arguments(self, parser):
        parser.add_argument(
            "--store-id",
            type=int,
            help="Process only specific store (optional)",
        )
        parser.add_argument(
            "--hours",
            type=int,
            default=24,
            help="Hours since last activity to consider abandoned (default: 24)",
        )
        parser.add_argument(
            "--send-reminders",
            action="store_true",
            help="Send reminder emails for abandoned carts",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without actually doing it",
        )

    def handle(self, *args, **options):
        store_id = options.get("store_id")
        hours = options.get("hours", 24)
        send_reminders = options.get("send_reminders", False)
        dry_run = options.get("dry_run", False)

        store = None
        if store_id:
            try:
                store = Store.objects.get(id=store_id)
                self.stdout.write(f"Processing abandoned carts for store: {store.name}")
            except Store.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Store with ID {store_id} not found"))
                return

        # Get stats before
        stats_before = AbandonedCartService.get_abandoned_cart_stats(store)
        self.stdout.write(
            f"Total abandoned carts: {stats_before['total_abandoned_carts']}"
        )
        self.stdout.write(
            f"Total abandoned value: {stats_before['total_abandoned_value']} SAR"
        )

        # Mark abandoned carts
        abandoned_carts = AbandonedCartService.get_abandoned_carts(store, hours)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY RUN] Would mark {abandoned_carts.count()} carts as abandoned"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Marked {abandoned_carts.count()} carts as abandoned")
            )

        # Send reminders if requested
        if send_reminders:
            reminder_carts = AbandonedCartService.get_abandoned_carts_for_reminder(
                store, hours
            )
            reminder_count = reminder_carts.count()

            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f"[DRY RUN] Would send {reminder_count} reminder emails"
                    )
                )
            else:
                sent_count = 0
                for cart in reminder_carts:
                    if AbandonedCartRecoveryEmailService.send_recovery_email(cart):
                        sent_count += 1

                self.stdout.write(
                    self.style.SUCCESS(f"Sent {sent_count}/{reminder_count} reminder emails")
                )

        # Get stats after
        if not dry_run:
            stats_after = AbandonedCartService.get_abandoned_cart_stats(store)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Final abandoned carts: {stats_after['total_abandoned_carts']}"
                )
            )
