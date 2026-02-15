from django.urls import path

from .views import ImportStartAPI, ImportStatusAPI


urlpatterns = [
    path("import/start", ImportStartAPI.as_view()),
    path("import/<int:job_id>", ImportStatusAPI.as_view()),
]
