from django.urls import path

from apps.ai_onboarding.interfaces.api_views import (
    OnboardingAnalyzeAPIView,
    OnboardingProvisionAPIView,
)
from apps.ai_onboarding.interfaces.web_views import wizard_analyze_step, wizard_finish_provision


app_name = "ai_onboarding"

urlpatterns = [
    path("api/onboarding/analyze/", OnboardingAnalyzeAPIView.as_view(), name="onboarding_analyze"),
    path("api/onboarding/provision/", OnboardingProvisionAPIView.as_view(), name="onboarding_provision"),
    path("onboarding/wizard/analyze/", wizard_analyze_step, name="wizard_analyze_step"),
    path("onboarding/wizard/provision/", wizard_finish_provision, name="wizard_finish_provision"),
]
