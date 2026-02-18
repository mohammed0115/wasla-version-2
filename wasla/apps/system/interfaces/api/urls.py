from django.urls import path

from .views import GoLiveStatusAPI


urlpatterns = [
    path("go-live-status", GoLiveStatusAPI.as_view(), name="api_go_live_status"),
]
