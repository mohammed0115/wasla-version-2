from django.urls import path

from .api_views import DomainProvisionQueueAPI
from .monitoring_apis import (
    AdminDomainCheckAPI,
    AdminDomainHealthDetailAPI,
    AdminDomainListAPI,
    AdminDomainRenewAPI,
    MerchantDomainStatusAPI,
)


urlpatterns = [
    path("admin/domains/queue", DomainProvisionQueueAPI.as_view(), name="api_domains_queue"),
    path("admin/domains/", AdminDomainListAPI.as_view(), name="api_admin_domains_list"),
    path("admin/domains/<int:domain_id>/health/", AdminDomainHealthDetailAPI.as_view(), name="api_admin_domain_health"),
    path("admin/domains/<int:domain_id>/check/", AdminDomainCheckAPI.as_view(), name="api_admin_domain_check"),
    path("admin/domains/<int:domain_id>/renew/", AdminDomainRenewAPI.as_view(), name="api_admin_domain_renew"),
    path("domains/status/", MerchantDomainStatusAPI.as_view(), name="api_merchant_domain_status"),
]
