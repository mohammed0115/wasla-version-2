from django.urls import path

from .views import analytics_events, analytics_experiments, analytics_experiment_detail


urlpatterns = [
    path("dashboard/analytics/events", analytics_events, name="dashboard_analytics_events"),
    path("dashboard/analytics/experiments", analytics_experiments, name="dashboard_analytics_experiments"),
    path("dashboard/analytics/experiments/<str:key>", analytics_experiment_detail, name="dashboard_analytics_experiment_detail"),
]
