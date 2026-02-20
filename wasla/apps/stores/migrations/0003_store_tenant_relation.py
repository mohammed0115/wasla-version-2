from django.db import migrations, models


def add_store_tenant_fk(apps, schema_editor):
    Store = apps.get_model("stores", "Store")
    Tenant = apps.get_model("tenants", "Tenant")

    table_name = Store._meta.db_table
    column_name = "tenant_id"

    with schema_editor.connection.cursor() as cursor:
        columns = [column.name for column in schema_editor.connection.introspection.get_table_description(cursor, table_name)]

    if column_name in columns:
        return

    field = models.ForeignKey(
        Tenant,
        on_delete=models.deletion.CASCADE,
        null=True,
        blank=True,
        related_name="stores",
        db_index=True,
    )
    field.set_attributes_from_name("tenant")
    schema_editor.add_field(Store, field)


def backfill_store_tenant(apps, schema_editor):
    Store = apps.get_model("stores", "Store")
    TenantMembership = apps.get_model("tenants", "TenantMembership")
    StoreProfile = apps.get_model("tenants", "StoreProfile")

    for store in Store.objects.filter(tenant__isnull=True).iterator():
        if not store.owner_id:
            continue

        membership_ids = list(
            TenantMembership.objects.filter(
                user_id=store.owner_id,
                role=TenantMembership.ROLE_OWNER,
                is_active=True,
            )
            .values_list("tenant_id", flat=True)
            .distinct()
        )
        if len(membership_ids) == 1:
            Store.objects.filter(pk=store.pk).update(tenant_id=membership_ids[0])
            continue

        profile_ids = list(
            StoreProfile.objects.filter(owner_id=store.owner_id)
            .values_list("tenant_id", flat=True)
            .distinct()
        )
        if len(profile_ids) == 1:
            Store.objects.filter(pk=store.pk).update(tenant_id=profile_ids[0])


class Migration(migrations.Migration):
    dependencies = [
        ("stores", "0002_store_storesettings_storesetupstep_and_more"),
        ("tenants", "0011_store_domain_status_updates"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_store_tenant_fk, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="store",
                    name="tenant",
                    field=models.ForeignKey(
                        "tenants.tenant",
                        on_delete=models.deletion.CASCADE,
                        null=True,
                        blank=True,
                        related_name="stores",
                        db_index=True,
                    ),
                ),
            ],
        ),
        migrations.RunPython(backfill_store_tenant, migrations.RunPython.noop),
    ]
