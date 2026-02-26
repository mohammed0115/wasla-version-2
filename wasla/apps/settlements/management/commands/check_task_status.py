"""
Django management command to check Celery task status.

Usage:
    python manage.py check_task_status <task_id>
"""

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Check status of a Celery task"

    def add_arguments(self, parser):
        parser.add_argument(
            "task_id",
            type=str,
            help="Celery task ID to check",
        )
        parser.add_argument(
            "--wait",
            action="store_true",
            help="Wait for task to complete",
        )

    def handle(self, *args, **options):
        task_id = options["task_id"]
        wait = options["wait"]

        try:
            from celery.result import AsyncResult
        except ImportError:
            raise CommandError(
                "Celery is not installed. Install with: pip install celery"
            )

        task = AsyncResult(task_id)

        self.stdout.write(f"Task ID: {task_id}")
        self.stdout.write(f"Status: {task.status}")

        if wait:
            self.stdout.write("Waiting for task to complete...")
            try:
                result = task.get(timeout=300)  # 5 minute timeout
                self.stdout.write(self.style.SUCCESS("\n✓ Task completed!"))
                self._display_result(result)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"\n✗ Task failed: {e}"))
        else:
            if task.ready():
                if task.successful():
                    self.stdout.write(self.style.SUCCESS("\n✓ Task completed!"))
                    self._display_result(task.result)
                else:
                    self.stdout.write(self.style.ERROR(f"\n✗ Task failed!"))
                    self.stdout.write(f"Error: {task.info}")
            else:
                self.stdout.write(
                    self.style.WARNING("\n○ Task is still running...")
                )
                self.stdout.write(
                    "\nRun with --wait to wait for completion, or check again later."
                )

    def _display_result(self, result):
        """Display task result."""
        if isinstance(result, dict):
            import json
            self.stdout.write("\nResult:")
            self.stdout.write(json.dumps(result, indent=2))
        else:
            self.stdout.write(f"\nResult: {result}")
