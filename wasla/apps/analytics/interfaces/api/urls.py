from django.urls import path

from .views import ExperimentAssignmentAPI, RecommendationsAPI, RiskAssessmentAPI, TrackEventAPI


urlpatterns = [
    path("events", TrackEventAPI.as_view(), name="api_events"),
    path("experiments/<str:key>/assignment", ExperimentAssignmentAPI.as_view(), name="api_experiment_assignment"),
    path("recommendations", RecommendationsAPI.as_view(), name="api_recommendations"),
    path("risk/<int:order_id>", RiskAssessmentAPI.as_view(), name="api_risk_assessment"),
]
