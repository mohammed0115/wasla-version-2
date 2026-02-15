from django.urls import path

from .views import admin_go_live_status


urlpatterns = [
    path("admin/go-live-status", admin_go_live_status, name="admin_go_live_status"),
]
