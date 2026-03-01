from django.urls import path
from . import views
from .persiona.views import persona_plans, persona_business, ai_onboarding_wizard, ai_onboarding_suggestions

app_name = "accounts"

urlpatterns = [
    path("auth/", views.auth_page, name="auth"),
    path("auth/verify/", views.verify_otp, name="verify_otp"),
    path("auth/resend/", views.resend_otp, name="resend_otp"),
    path("auth/2fa/setup/", views.totp_setup, name="totp_setup"),
    path("auth/2fa/enable/", views.totp_enable, name="totp_enable"),
    path("auth/2fa/disable/", views.totp_disable, name="totp_disable"),
    path("logout/", views.do_logout, name="logout"),

    path("onboarding/welcome/", views.persona_welcome, name="persona_welcome"),
    path("onboarding/country/", views.persona_country, name="persona_country"),
    path("onboarding/legal/", views.persona_legal, name="persona_legal"),
    path("onboarding/existing/", views.persona_existing, name="persona_existing"),
    path("onboarding/channel/", views.persona_channel, name="persona_channel"),
    path("onboarding/category/", views.persona_category_main, name="persona_category_main"),
    path("onboarding/finish/", views.persona_finish, name="persona_finish"),
    path("onboarding/ai-wizard/", ai_onboarding_wizard, name="ai_onboarding_wizard"),
    path("onboarding/ai-suggestions/", ai_onboarding_suggestions, name="ai_onboarding_suggestions"),
    path("persona/plans/", persona_plans, name="persona_plans"),
    path("persona/business/", persona_business, name="persona_business"),


]
