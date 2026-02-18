from django.urls import path

from apps.emails.interfaces.api import EmailTestAPI

urlpatterns = [
    path("settings/email/test/", EmailTestAPI.as_view()),
]

