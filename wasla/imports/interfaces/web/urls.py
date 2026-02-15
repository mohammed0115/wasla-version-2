from django.urls import path

from .views import import_index, import_job_detail, import_start


urlpatterns = [
    path("dashboard/import", import_index, name="dashboard_import"),
    path("dashboard/import/start", import_start, name="dashboard_import_start"),
    path("dashboard/import/<int:job_id>", import_job_detail, name="dashboard_import_detail"),
]
