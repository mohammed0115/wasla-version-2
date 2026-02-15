from django.urls import path

from .views import BrandingUpdateAPI, ThemeListAPI


urlpatterns = [
    path("themes", ThemeListAPI.as_view()),
    path("branding/update", BrandingUpdateAPI.as_view()),
]
