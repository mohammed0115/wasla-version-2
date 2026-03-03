from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DataExportRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("request_id", models.CharField(help_text="Unique request identifier", max_length=100, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("processing", "Processing"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                            ("expired", "Expired"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                (
                    "format_type",
                    models.CharField(
                        choices=[
                            ("json", "JSON"),
                            ("csv", "CSV"),
                            ("xml", "XML"),
                        ],
                        default="json",
                        help_text="Data export format",
                        max_length=20,
                    ),
                ),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                (
                    "processed_at",
                    models.DateTimeField(blank=True, help_text="When export was generated", null=True),
                ),
                (
                    "expires_at",
                    models.DateTimeField(blank=True, help_text="When download link expires (30 days)", null=True),
                ),
                ("download_count", models.IntegerField(default=0, help_text="Number of times downloaded")),
                (
                    "data_file",
                    models.FileField(blank=True, help_text="Generated data export file", upload_to="privacy/data_exports/"),
                ),
                ("file_size", models.BigIntegerField(default=0, help_text="Size of export file in bytes")),
                ("included_data", models.JSONField(default=dict, help_text="List of data categories included")),
                ("error_message", models.TextField(blank=True, help_text="Error details if processing failed")),
                ("notes", models.TextField(blank=True, help_text="Admin notes")),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="data_export_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Data Export Request",
                "verbose_name_plural": "Data Export Requests",
                "db_table": "privacy_data_export_request",
                "ordering": ["-requested_at"],
            },
        ),
        migrations.CreateModel(
            name="AccountDeletionRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("request_id", models.CharField(help_text="Unique request identifier", max_length=100, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending Confirmation"),
                            ("confirmed", "Confirmed"),
                            ("processing", "Processing"),
                            ("completed", "Completed"),
                            ("rejected", "Rejected"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                (
                    "reason",
                    models.CharField(
                        choices=[
                            ("no_longer_needed", "No longer needed"),
                            ("privacy_concerns", "Privacy concerns"),
                            ("found_alternative", "Found alternative"),
                            ("other", "Other"),
                        ],
                        default="other",
                        max_length=50,
                    ),
                ),
                (
                    "confirmation_code",
                    models.CharField(blank=True, help_text="Code sent to email for confirmation", max_length=100),
                ),
                (
                    "is_confirmed",
                    models.BooleanField(default=False, help_text="User confirmed deletion via email link"),
                ),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                (
                    "confirmed_at",
                    models.DateTimeField(blank=True, help_text="When user confirmed deletion", null=True),
                ),
                (
                    "processed_at",
                    models.DateTimeField(blank=True, help_text="When account was deleted", null=True),
                ),
                (
                    "grace_period_ends_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="Grace period before irreversible deletion (14 days)",
                        null=True,
                    ),
                ),
                (
                    "data_backup",
                    models.FileField(
                        blank=True,
                        help_text="Backup of user data before deletion",
                        upload_to="privacy/deletion_backups/",
                    ),
                ),
                ("reason_details", models.TextField(blank=True, help_text="Additional reason details")),
                ("notes", models.TextField(blank=True, help_text="Admin notes")),
                (
                    "is_irreversible",
                    models.BooleanField(default=False, help_text="Account fully deleted and unrecoverable"),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="deletion_request",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Account Deletion Request",
                "verbose_name_plural": "Account Deletion Requests",
                "db_table": "privacy_account_deletion_request",
                "ordering": ["-requested_at"],
            },
        ),
        migrations.CreateModel(
            name="DataAccessLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("view", "View User Data"),
                            ("export", "Export Data"),
                            ("download", "Download Export"),
                            ("delete", "Delete Account"),
                            ("restore", "Restore Account"),
                            ("consent_grant", "Grant Consent"),
                            ("consent_revoke", "Revoke Consent"),
                            ("login", "User Login"),
                            ("password_change", "Password Change"),
                            ("email_change", "Email Change"),
                        ],
                        max_length=30,
                    ),
                ),
                ("accessed_by", models.CharField(help_text="Who accessed (user, admin, system)", max_length=100)),
                ("ip_address", models.GenericIPAddressField(blank=True, help_text="IP address of accessor", null=True)),
                ("user_agent", models.TextField(blank=True, help_text="Browser/device info")),
                ("data_categories", models.JSONField(default=list, help_text="Which data was accessed")),
                ("purpose", models.CharField(blank=True, help_text="Purpose of access", max_length=255)),
                ("details", models.JSONField(blank=True, default=dict, help_text="Additional details")),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="data_access_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Data Access Log",
                "verbose_name_plural": "Data Access Logs",
                "db_table": "privacy_data_access_log",
                "ordering": ["-timestamp"],
            },
        ),
        migrations.CreateModel(
            name="ConsentRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "consent_type",
                    models.CharField(
                        choices=[
                            ("marketing", "Marketing Communications"),
                            ("analytics", "Analytics & Tracking"),
                            ("third_party", "Third-party Sharing"),
                            ("profiling", "Profiling & Personalization"),
                            ("cookies", "Cookies & Similar Tech"),
                        ],
                        max_length=30,
                    ),
                ),
                ("is_granted", models.BooleanField(help_text="User granted or revoked this consent")),
                ("granted_at", models.DateTimeField(blank=True, help_text="When consent was given", null=True)),
                ("revoked_at", models.DateTimeField(blank=True, help_text="When consent was revoked", null=True)),
                ("version", models.CharField(default="1.0", help_text="Version of privacy policy agreed to", max_length=20)),
                ("ip_address", models.GenericIPAddressField(blank=True, help_text="IP when consent given", null=True)),
                ("user_agent", models.TextField(blank=True, help_text="Device info for audit")),
                (
                    "method",
                    models.CharField(
                        choices=[
                            ("checkbox", "Checkbox"),
                            ("explicit", "Explicit Agreement"),
                            ("email", "Email Confirmation"),
                            ("phone", "Phone Confirmation"),
                        ],
                        default="checkbox",
                        max_length=50,
                    ),
                ),
                ("notes", models.TextField(blank=True, help_text="Additional context")),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="consent_records",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Consent Record",
                "verbose_name_plural": "Consent Records",
                "db_table": "privacy_consent_record",
                "unique_together": {("user", "consent_type")},
            },
        ),
        migrations.AddIndex(
            model_name="dataexportrequest",
            index=models.Index(fields=["user", "status"], name="privacy_dat_user_id_e83f0f_idx"),
        ),
        migrations.AddIndex(
            model_name="dataexportrequest",
            index=models.Index(fields=["request_id"], name="privacy_dat_request_83ff26_idx"),
        ),
        migrations.AddIndex(
            model_name="dataexportrequest",
            index=models.Index(fields=["status", "requested_at"], name="privacy_dat_status__50a3e4_idx"),
        ),
        migrations.AddIndex(
            model_name="accountdeletionrequest",
            index=models.Index(fields=["user", "status"], name="privacy_acc_user_id_57bc8b_idx"),
        ),
        migrations.AddIndex(
            model_name="accountdeletionrequest",
            index=models.Index(fields=["request_id"], name="privacy_acc_request_a35bba_idx"),
        ),
        migrations.AddIndex(
            model_name="accountdeletionrequest",
            index=models.Index(fields=["status", "requested_at"], name="privacy_acc_status__2f4f2a_idx"),
        ),
        migrations.AddIndex(
            model_name="dataaccesslog",
            index=models.Index(fields=["user", "action"], name="privacy_dat_user_id_8cf9c1_idx"),
        ),
        migrations.AddIndex(
            model_name="dataaccesslog",
            index=models.Index(fields=["timestamp"], name="privacy_dat_timesta_1c1a9f_idx"),
        ),
        migrations.AddIndex(
            model_name="dataaccesslog",
            index=models.Index(fields=["accessed_by"], name="privacy_dat_access_2e58b7_idx"),
        ),
        migrations.AddIndex(
            model_name="consentrecord",
            index=models.Index(fields=["user", "consent_type"], name="privacy_con_user_id_32f5c4_idx"),
        ),
        migrations.AddIndex(
            model_name="consentrecord",
            index=models.Index(fields=["is_granted"], name="privacy_con_is_gra_1f7b65_idx"),
        ),
    ]
