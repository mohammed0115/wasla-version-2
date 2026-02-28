from django.urls import path

from .views import analytics_events, analytics_experiments, analytics_experiment_detail

# Import dashboard views
from apps.analytics.views import (
    merchant_kpi_view,
    merchant_dashboard_view,
    revenue_chart_data_view,
    funnel_analysis_view,
    export_kpi_csv_view,
    export_revenue_csv_view,
    export_funnel_csv_view,
    admin_executive_dashboard_view,
    admin_kpi_json_view,
    export_admin_kpi_csv_view,
)

urlpatterns = [
    # Legacy analytics
    path("dashboard/analytics/events", analytics_events, name="dashboard_analytics_events"),
    path("dashboard/analytics/experiments", analytics_experiments, name="dashboard_analytics_experiments"),
    path("dashboard/analytics/experiments/<str:key>", analytics_experiment_detail, name="dashboard_analytics_experiment_detail"),

    # New KPI Dashboard - Merchant
    path("dashboard/kpi/", merchant_kpi_view, name="merchant_kpi"),
    path("dashboard/", merchant_dashboard_view, name="merchant_dashboard"),
    path("api/revenue-chart/", revenue_chart_data_view, name="revenue_chart"),
    path("api/funnel/", funnel_analysis_view, name="funnel_analysis"),

    # CSV Exports
    path("export/kpi.csv", export_kpi_csv_view, name="export_kpi_csv"),
    path("export/revenue.csv", export_revenue_csv_view, name="export_revenue_csv"),
    path("export/funnel.csv", export_funnel_csv_view, name="export_funnel_csv"),

    # Admin Executive Dashboard
    path("admin/dashboard/", admin_executive_dashboard_view, name="admin_dashboard"),
    path("admin/api/kpi/", admin_kpi_json_view, name="admin_kpi_json"),
    path("admin/export/kpi.csv", export_admin_kpi_csv_view, name="export_admin_kpi_csv"),
]
