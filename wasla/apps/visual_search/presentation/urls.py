from django.urls import path

from apps.visual_search.presentation.views import visual_search_view


app_name = "visual_search"

urlpatterns = [
    path("visual-search/", visual_search_view, name="visual_search"),
]
