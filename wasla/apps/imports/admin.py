from django.contrib import admin

from .models import ImportJob, ImportRowError


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = ("id", "store_id", "status", "total_rows", "success_rows", "failed_rows", "created_at")
    list_filter = ("status",)
    search_fields = ("store_id",)


@admin.register(ImportRowError)
class ImportRowErrorAdmin(admin.ModelAdmin):
    list_display = ("id", "import_job", "row_number", "field", "message_key")
    search_fields = ("import_job__id", "field", "message_key")
