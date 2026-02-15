from django.urls import path

from .views import branding_edit, themes_list


urlpatterns = [
    path("dashboard/themes", themes_list, name="dashboard_themes"),
    path("dashboard/branding", branding_edit, name="dashboard_branding"),
]
