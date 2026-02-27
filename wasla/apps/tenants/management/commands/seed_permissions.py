from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.tenants.models import Permission, RolePermission, TenantMembership


PERMISSIONS = [
    ("catalog.create_product", "catalog", "Create catalog products"),
    ("catalog.update_product", "catalog", "Update catalog products"),
    ("orders.create_order", "orders", "Create customer orders"),
    ("orders.view_reports", "orders", "View orders sales reports"),
    ("wallet.view_wallet", "wallet", "View wallet balances"),
    ("wallet.view_withdrawals", "wallet", "View withdrawal requests"),
    ("wallet.create_withdrawal", "wallet", "Create withdrawal requests"),
    ("wallet.manage_withdrawals", "wallet", "Approve/reject/mark paid withdrawals"),
    ("wallet.view_ledger_integrity", "wallet", "View wallet ledger integrity"),
    ("settlements.view_balance", "settlements", "View settlements balance"),
    ("settlements.view_settlements", "settlements", "List and view settlements"),
    ("settlements.manage_settlements", "settlements", "Approve and mark settlements paid"),
    ("settlements.view_reports", "settlements", "View settlements monthly reports"),
    ("settlements.create_invoice_draft", "settlements", "Create settlements invoice draft"),
    ("plugins.view_plugins", "plugins", "View plugin catalog"),
    ("plugins.install_plugin", "plugins", "Install plugins"),
    ("plugins.enable_plugin", "plugins", "Enable plugins"),
    ("plugins.disable_plugin", "plugins", "Disable plugins"),
    ("plugins.uninstall_plugin", "plugins", "Uninstall plugins"),
    ("domains.queue_provision", "domains", "Queue domain provisioning/verification"),
    ("reviews.view_pending", "reviews", "View pending reviews for moderation"),
    ("reviews.moderate", "reviews", "Approve/reject reviews"),
]


ROLE_MATRIX = {
    TenantMembership.ROLE_OWNER: [code for code, _, _ in PERMISSIONS],
    TenantMembership.ROLE_ADMIN: [code for code, _, _ in PERMISSIONS],
    TenantMembership.ROLE_STAFF: [
        "catalog.create_product",
        "catalog.update_product",
        "orders.create_order",
        "orders.view_reports",
        "wallet.view_wallet",
        "wallet.view_withdrawals",
        "wallet.create_withdrawal",
        "settlements.view_balance",
        "settlements.view_settlements",
        "settlements.view_reports",
        "plugins.view_plugins",
        "reviews.view_pending",
    ],
    TenantMembership.ROLE_READ_ONLY: [
        "orders.view_reports",
        "wallet.view_wallet",
        "wallet.view_withdrawals",
        "settlements.view_balance",
        "settlements.view_settlements",
        "settlements.view_reports",
        "plugins.view_plugins",
    ],
}


class Command(BaseCommand):
    help = "Seed granular RBAC permissions and role mappings."

    def handle(self, *args, **options):
        permission_map: dict[str, Permission] = {}
        created_permissions = 0
        for code, module, description in PERMISSIONS:
            permission, created = Permission.objects.get_or_create(
                code=code,
                defaults={"module": module, "description": description},
            )
            if not created:
                updates = {}
                if permission.module != module:
                    updates["module"] = module
                if permission.description != description:
                    updates["description"] = description
                if updates:
                    for field, value in updates.items():
                        setattr(permission, field, value)
                    permission.save(update_fields=list(updates.keys()))
            else:
                created_permissions += 1
            permission_map[code] = permission

        created_role_permissions = 0
        for role, codes in ROLE_MATRIX.items():
            for code in codes:
                permission = permission_map[code]
                _, created = RolePermission.objects.get_or_create(role=role, permission=permission)
                if created:
                    created_role_permissions += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded permissions. created_permissions={created_permissions} created_role_permissions={created_role_permissions}"
            )
        )
