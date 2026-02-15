from django.urls import path

from .api_views import DomainProvisionQueueAPI


urlpatterns = [
    path("admin/domains/queue", DomainProvisionQueueAPI.as_view(), name="api_domains_queue"),
]
