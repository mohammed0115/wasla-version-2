from django.urls import path

from .admin_views import force_renew_ssl, monitoring_dashboard, monitoring_detail, rerun_health_check

urlpatterns = [
    path("admin-portal/domains/", monitoring_dashboard, name="domains_admin_dashboard"),
    path("admin-portal/domains/<int:domain_id>/", monitoring_detail, name="domains_admin_detail"),
    path("admin-portal/domains/<int:domain_id>/check/", rerun_health_check, name="domains_admin_check"),
    path("admin-portal/domains/<int:domain_id>/renew/", force_renew_ssl, name="domains_admin_renew"),
]
