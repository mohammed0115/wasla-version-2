from django.urls import path

from apps.visual_search.presentation.api_views import VisualSearchAPIView


app_name = "visual_search_api"

urlpatterns = [
    path("visual-search/", VisualSearchAPIView.as_view(), name="visual_search_api"),
]
