from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed platform RBAC roles and permissions"

    def handle(self, *args, **options):
        call_command("seed_admin_portal_rbac", *args, **options)
