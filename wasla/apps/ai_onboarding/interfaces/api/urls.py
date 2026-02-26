from django.urls import path

from .views import OnboardingAnalyzeAPI, OnboardingProvisionAPI


urlpatterns = [
    path("onboarding/analyze/", OnboardingAnalyzeAPI.as_view(), name="onboarding_analyze"),
    path("onboarding/provision/", OnboardingProvisionAPI.as_view(), name="onboarding_provision"),
]
