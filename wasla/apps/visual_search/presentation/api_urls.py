from django.urls import path

from apps.visual_search.presentation.api_views import VisualSearchAPIView, VoiceSearchAPIView


app_name = "visual_search_api"

urlpatterns = [
    path("visual-search/", VisualSearchAPIView.as_view(), name="visual_search_api"),
    path("search/voice/", VoiceSearchAPIView.as_view(), name="voice_search_api"),
]
