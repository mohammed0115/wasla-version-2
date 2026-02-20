from django.db import migrations


DEFAULT_ROLES = [
    ("SuperAdmin", "Full platform access"),
    ("Finance", "Finance operations and invoice control"),
    ("Support", "Tenant/store/order support read-only"),
    ("Ops", "Operational troubleshooting and webhooks"),
]

DEFAULT_PERMISSIONS = [
    ("TENANTS_VIEW", "View tenants"),
    ("TENANTS_EDIT", "Edit tenant state"),
    ("STORES_VIEW", "View stores"),
    ("STORES_EDIT", "Edit store state"),
    ("FINANCE_VIEW", "View payments, settlements, invoices"),
    ("FINANCE_MARK_INVOICE_PAID", "Mark invoice as paid"),
    ("WEBHOOKS_VIEW", "View webhooks"),
]

ROLE_PERMISSIONS = {
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


def seed_rbac(apps, schema_editor):
    AdminRole = apps.get_model("admin_portal", "AdminRole")
    AdminPermission = apps.get_model("admin_portal", "AdminPermission")
    AdminRolePermission = apps.get_model("admin_portal", "AdminRolePermission")

    role_by_name = {}
    for name, description in DEFAULT_ROLES:
        role, _ = AdminRole.objects.get_or_create(name=name, defaults={"description": description})
        role_by_name[name] = role

    permission_by_code = {}
    for code, description in DEFAULT_PERMISSIONS:
        permission, _ = AdminPermission.objects.get_or_create(code=code, defaults={"description": description})
        permission_by_code[code] = permission

    for role_name, permission_codes in ROLE_PERMISSIONS.items():
        role = role_by_name[role_name]
        for code in permission_codes:
            permission = permission_by_code[code]
            AdminRolePermission.objects.get_or_create(role=role, permission=permission)


def reverse_seed_rbac(apps, schema_editor):
    AdminRolePermission = apps.get_model("admin_portal", "AdminRolePermission")
    AdminPermission = apps.get_model("admin_portal", "AdminPermission")
    AdminRole = apps.get_model("admin_portal", "AdminRole")

    AdminRolePermission.objects.all().delete()
    AdminPermission.objects.filter(code__in=[item[0] for item in DEFAULT_PERMISSIONS]).delete()
    AdminRole.objects.filter(name__in=[item[0] for item in DEFAULT_ROLES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("admin_portal", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_rbac, reverse_seed_rbac),
    ]
