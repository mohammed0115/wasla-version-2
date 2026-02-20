from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.admin_portal.models import AdminRole, AdminUserRole


class Command(BaseCommand):
    help = "Assign an admin portal role to a user"

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("role_name")

    def handle(self, *args, **options):
        username = options["username"]
        role_name = options["role_name"]

        User = get_user_model()
        user = User.objects.filter(username=username).first()
        if not user:
            raise CommandError(f"User not found: {username}")

        role = AdminRole.objects.filter(name=role_name).first()
        if not role:
            raise CommandError(f"Role not found: {role_name}")

        user_role, _ = AdminUserRole.objects.get_or_create(user=user, defaults={"role": role})
        if user_role.role_id != role.id:
            user_role.role = role
            user_role.save(update_fields=["role"])

        user.is_staff = True
        user.save(update_fields=["is_staff"])

        self.stdout.write(self.style.SUCCESS(f"Assigned role {role.name} to {user.username}"))
