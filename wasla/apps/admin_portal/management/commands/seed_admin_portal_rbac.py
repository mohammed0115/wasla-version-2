from django.core.management.base import BaseCommand

from apps.admin_portal.models import AdminPermission, AdminRole, AdminRolePermission


class Command(BaseCommand):
    help = "Seed admin-portal RBAC roles and permissions"

    ROLE_DESCRIPTIONS = {
        "SuperAdmin": "Full access",
        "Finance": "Finance role",
        "Support": "Support role",
        "Ops": "Ops role",
    }

    PERMISSIONS = {
        "TENANTS_VIEW": "View tenants",
        "TENANTS_EDIT": "Edit tenant activation/publish state",
        "STORES_VIEW": "View stores",
        "STORES_EDIT": "Edit store activation state",
        "FINANCE_VIEW": "View finance/payment pages",
        "FINANCE_MARK_INVOICE_PAID": "Mark invoices as paid",
        "WEBHOOKS_VIEW": "View webhook logs",
    }

    ROLE_PERMISSION_MAPPING = {
        "SuperAdmin": [
            "TENANTS_VIEW",
            "TENANTS_EDIT",
            "STORES_VIEW",
            "STORES_EDIT",
            "FINANCE_VIEW",
            "FINANCE_MARK_INVOICE_PAID",
            "WEBHOOKS_VIEW",
        ],
        "Finance": [
            "FINANCE_VIEW",
            "FINANCE_MARK_INVOICE_PAID",
        ],
        "Support": [
            "TENANTS_VIEW",
            "STORES_VIEW",
            "FINANCE_VIEW",
        ],
        "Ops": [
            "STORES_VIEW",
            "WEBHOOKS_VIEW",
        ],
    }

    def handle(self, *args, **options):
        created_roles = 0
        created_permissions = 0
        created_links = 0

        for role_name, description in self.ROLE_DESCRIPTIONS.items():
            _, created = AdminRole.objects.get_or_create(
                name=role_name,
                defaults={"description": description},
            )
            if created:
                created_roles += 1

        for code, description in self.PERMISSIONS.items():
            _, created = AdminPermission.objects.get_or_create(
                code=code,
                defaults={"description": description},
            )
            if created:
                created_permissions += 1

        for role_name, permission_codes in self.ROLE_PERMISSION_MAPPING.items():
            role = AdminRole.objects.get(name=role_name)
            for code in permission_codes:
                permission = AdminPermission.objects.get(code=code)
                _, created = AdminRolePermission.objects.get_or_create(
                    role=role,
                    permission=permission,
                )
                if created:
                    created_links += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Admin RBAC seeded: roles_created={created_roles}, permissions_created={created_permissions}, role_permissions_created={created_links}"
            )
        )
