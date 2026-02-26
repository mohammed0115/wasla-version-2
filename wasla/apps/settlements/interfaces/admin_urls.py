"""
URL routing for settlement admin monitoring endpoints.
"""

from django.urls import path

from .admin_views import (
    settlement_dashboard,
    reconciliation_report,
    trigger_settlement_run,
    task_status,
    settlement_health,
)

app_name = "settlements_admin"

urlpatterns = [
    # Dashboard
    path("dashboard/", settlement_dashboard, name="dashboard"),
    
    # Reconciliation
    path("reconciliation/", reconciliation_report, name="reconciliation"),
    
    # Health check
    path("health/", settlement_health, name="health"),
    
    # Manual triggers
    path("trigger/", trigger_settlement_run, name="trigger"),
    
    # Task status
    path("task/<str:task_id>/", task_status, name="task_status"),
]
