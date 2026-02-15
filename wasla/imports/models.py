"""
Bulk import models (CSV).

AR:
- تخزين معلومات مهمة الاستيراد وأخطاء الصفوف.
EN:
- Stores import job metadata and row-level errors.
"""

from django.conf import settings
from django.db import models


class ImportJob(models.Model):
    STATUS_CREATED = "CREATED"
    STATUS_VALIDATING = "VALIDATING"
    STATUS_IMPORTING = "IMPORTING"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_FAILED = "FAILED"

    STATUS_CHOICES = [
        (STATUS_CREATED, "Created"),
        (STATUS_VALIDATING, "Validating"),
        (STATUS_IMPORTING, "Importing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    SOURCE_CSV = "CSV"
    SOURCE_CHOICES = [
        (SOURCE_CSV, "CSV"),
    ]

    store_id = models.IntegerField(db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="import_jobs"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_CREATED)
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_CSV)
    original_file_path = models.CharField(max_length=500, blank=True, default="")
    total_rows = models.PositiveIntegerField(default=0)
    success_rows = models.PositiveIntegerField(default=0)
    failed_rows = models.PositiveIntegerField(default=0)
    errors_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["store_id", "created_at"]),
            models.Index(fields=["store_id", "status"]),
        ]

    def __str__(self) -> str:
        return f"ImportJob {self.id} ({self.status})"


class ImportRowError(models.Model):
    import_job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name="row_errors")
    row_number = models.PositiveIntegerField()
    field = models.CharField(max_length=100, blank=True, default="")
    message_key = models.CharField(max_length=200)
    raw_value = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["import_job", "row_number"]),
        ]

    def __str__(self) -> str:
        return f"ImportRowError {self.import_job_id}#{self.row_number}"
