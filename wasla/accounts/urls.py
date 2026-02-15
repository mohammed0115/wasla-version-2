from django.urls import path
from . import views
from .persiona.views import persona_plans,persona_business

app_name = "accounts"

urlpatterns = [
    path("auth/", views.auth_page, name="auth"),
    path("auth/verify/", views.verify_otp, name="verify_otp"),
    path("auth/resend/", views.resend_otp, name="resend_otp"),
    path("logout/", views.do_logout, name="logout"),

    path("onboarding/welcome/", views.persona_welcome, name="persona_welcome"),
    path("onboarding/country/", views.persona_country, name="persona_country"),
    path("onboarding/legal/", views.persona_legal, name="persona_legal"),
    path("onboarding/existing/", views.persona_existing, name="persona_existing"),
    path("onboarding/channel/", views.persona_channel, name="persona_channel"),
    path("onboarding/category/", views.persona_category_main, name="persona_category_main"),
    path("onboarding/finish/", views.persona_finish, name="persona_finish"),
    path("persona/plans/", persona_plans, name="persona_plans"),
    path("persona/business/", persona_business, name="persona_business"),


]