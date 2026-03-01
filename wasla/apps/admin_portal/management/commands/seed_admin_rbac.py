from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.admin_portal.models import AdminRole, AdminPermission, AdminRolePermission, AdminUserRole


class Command(BaseCommand):
    help = "Seed admin-portal RBAC roles and permissions"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Seeding admin RBAC...")

        permissions_list = [
            "view_dashboard",
            "manage_merchants",
            "manage_subscriptions",
            "manage_payments",
            "manage_settlements",
            "manage_users",
            "view_reports",
            "manage_system_settings",
        ]

        permissions = []
        for code in permissions_list:
            perm, _ = AdminPermission.objects.get_or_create(code=code)
            permissions.append(perm)

        superadmin_role, _ = AdminRole.objects.get_or_create(name="SUPERADMIN")
        admin_role, _ = AdminRole.objects.get_or_create(name="ADMIN")
        support_role, _ = AdminRole.objects.get_or_create(name="SUPPORT")

        # Attach all permissions to SUPERADMIN
        for perm in permissions:
            AdminRolePermission.objects.get_or_create(
                role=superadmin_role,
                permission=perm
            )

        # Example limited permissions
        limited_admin = ["view_dashboard", "manage_merchants", "view_reports"]
        for perm in permissions:
            if perm.code in limited_admin:
                AdminRolePermission.objects.get_or_create(
                    role=admin_role,
                    permission=perm
                )

        support_permissions = ["view_dashboard", "view_reports"]
        for perm in permissions:
            if perm.code in support_permissions:
                AdminRolePermission.objects.get_or_create(
                    role=support_role,
                    permission=perm
                )

        # Bind Django superusers to SUPERADMIN
        User = get_user_model()
        superusers = User.objects.filter(is_superuser=True)

        for user in superusers:
            AdminUserRole.objects.get_or_create(
                user=user,
                role=superadmin_role
            )

        self.stdout.write(self.style.SUCCESS("Admin RBAC seeded successfully"))
