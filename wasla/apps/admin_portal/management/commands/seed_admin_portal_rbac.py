from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.admin_portal.models import (
    AdminPermission,
    AdminRole,
    AdminRolePermission,
    AdminUserRole,
)


class Command(BaseCommand):
    help = "Seed admin-portal RBAC roles and permissions"

    ROLE_DEFINITIONS = [
        {"name": "SUPERADMIN", "description": "Full access to the admin portal."},
        {"name": "SUPPORT", "description": "Support operations for users, tenants, and stores."},
        {"name": "FINANCE", "description": "Finance operations for payments and settlements."},
        {"name": "READONLY", "description": "Read-only access to admin portal data."},
    ]

    PERMISSIONS = [
        {"code": "portal.access", "name": "Portal Access", "description": "Access the admin portal."},
        {"code": "portal.users.view", "name": "View Users", "description": "View admin portal users."},
        {"code": "portal.users.manage", "name": "Manage Users", "description": "Create, update, and disable admin users."},
        {"code": "portal.tenants.view", "name": "View Tenants", "description": "View tenant records."},
        {"code": "portal.tenants.manage", "name": "Manage Tenants", "description": "Activate, deactivate, and publish tenants."},
        {"code": "portal.stores.view", "name": "View Stores", "description": "View store records."},
        {"code": "portal.stores.manage", "name": "Manage Stores", "description": "Activate and deactivate stores."},
        {"code": "portal.payments.view", "name": "View Payments", "description": "View payments, invoices, and transactions."},
        {"code": "portal.payments.manage", "name": "Manage Payments", "description": "Create or approve payments and transactions."},
        {"code": "portal.settlements.view", "name": "View Settlements", "description": "View settlement records and invoices."},
        {"code": "portal.settlements.approve", "name": "Approve Settlements", "description": "Approve settlements and mark invoices paid."},
        {"code": "portal.subscriptions.view", "name": "View Subscriptions", "description": "View subscription records."},
        {"code": "portal.subscriptions.manage", "name": "Manage Subscriptions", "description": "Manage subscription records."},
        {"code": "portal.audit.view", "name": "View Audit Logs", "description": "View audit and webhook logs."},
        {"code": "portal.roles.manage", "name": "Manage Roles", "description": "Manage admin roles and permissions."},
    ]

    def handle(self, *args, **options):
        self.stdout.write("Seeding admin portal RBAC...")

        created_roles = 0
        updated_roles = 0
        created_permissions = 0
        updated_permissions = 0
        created_links = 0
        created_superuser_roles = 0
        updated_superuser_roles = 0

        with transaction.atomic():
            roles_by_name: dict[str, AdminRole] = {}
            for role_def in self.ROLE_DEFINITIONS:
                role, created = AdminRole.objects.get_or_create(
                    name=role_def["name"],
                    defaults={"description": role_def["description"]},
                )
                if created:
                    created_roles += 1
                elif role.description != role_def["description"]:
                    role.description = role_def["description"]
                    role.save(update_fields=["description"])
                    updated_roles += 1
                roles_by_name[role.name] = role

            permissions_by_code: dict[str, AdminPermission] = {}
            for perm_def in self.PERMISSIONS:
                perm, created = AdminPermission.objects.get_or_create(
                    code=perm_def["code"],
                    defaults={"description": perm_def["description"]},
                )
                if created:
                    created_permissions += 1
                elif perm.description != perm_def["description"]:
                    perm.description = perm_def["description"]
                    perm.save(update_fields=["description"])
                    updated_permissions += 1
                permissions_by_code[perm.code] = perm

            all_permission_codes = [perm["code"] for perm in self.PERMISSIONS]
            view_permission_codes = [code for code in all_permission_codes if code.endswith(".view")]

            role_permission_mapping = {
                "SUPERADMIN": all_permission_codes,
                "SUPPORT": [
                    "portal.access",
                    "portal.users.view",
                    "portal.users.manage",
                    "portal.tenants.view",
                    "portal.tenants.manage",
                    "portal.stores.view",
                    "portal.stores.manage",
                    "portal.audit.view",
                ],
                "FINANCE": [
                    "portal.access",
                    "portal.payments.view",
                    "portal.payments.manage",
                    "portal.settlements.view",
                    "portal.settlements.approve",
                    "portal.audit.view",
                ],
                "READONLY": ["portal.access", *view_permission_codes],
            }

            # Ensure all mapped roles exist (defensive against missing definitions).
            for role_name in role_permission_mapping:
                if role_name in roles_by_name:
                    continue
                role, created = AdminRole.objects.get_or_create(
                    name=role_name,
                    defaults={"description": f"{role_name} role"},
                )
                if created:
                    created_roles += 1
                roles_by_name[role_name] = role

            for role_name, permission_codes in role_permission_mapping.items():
                role = roles_by_name[role_name]
                for code in permission_codes:
                    permission = permissions_by_code[code]
                    _, created = AdminRolePermission.objects.get_or_create(
                        role=role,
                        permission=permission,
                    )
                    if created:
                        created_links += 1

            superadmin_role = roles_by_name["SUPERADMIN"]
            User = get_user_model()
            for user in User.objects.filter(is_superuser=True):
                user_role, created = AdminUserRole.objects.get_or_create(
                    user=user,
                    defaults={"role": superadmin_role},
                )
                if created:
                    created_superuser_roles += 1
                elif user_role.role_id != superadmin_role.id:
                    user_role.role = superadmin_role
                    user_role.save(update_fields=["role"])
                    updated_superuser_roles += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Admin portal RBAC seeded: "
                f"roles_created={created_roles}, roles_updated={updated_roles}, "
                f"permissions_created={created_permissions}, permissions_updated={updated_permissions}, "
                f"role_permissions_created={created_links}, "
                f"superuser_roles_created={created_superuser_roles}, "
                f"superuser_roles_updated={updated_superuser_roles}"
            )
        )
