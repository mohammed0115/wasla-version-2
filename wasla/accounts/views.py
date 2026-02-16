from __future__ import annotations

import time
import json
from typing import Dict, Any

from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import (
    LoginForm,
    RegisterForm,
    OTPForm,
    PersonaCountryForm,
    PersonaLegalForm,
    PersonaExistingForm,
    PersonaChannelForm,
    PersonaCategoryMainForm,
)
from .services.otp import (
    store_otp,
    validate_otp,
    clear_otp,
    send_otp_email,
    OTP_PENDING_USER_ID,
    OTP_EMAIL_KEY,
    OTP_EXPIRES_AT_KEY,
)



User = get_user_model()


def _mask_email(email: str) -> str:
    local, sep, domain = email.partition("@")
    if not sep or not local or not domain:
        return email
    if len(local) <= 2:
        masked_local = local[0] + ("*" * (len(local) - 1))
    else:
        masked_local = local[:2] + ("*" * (len(local) - 2))
    return f"{masked_local}@{domain}"


def auth_page(request: HttpRequest) -> HttpResponse:
    """Tabs page: login + register (Salla-like)."""
    login_form = LoginForm(prefix="login")
    register_form = RegisterForm(prefix="register")

    active_tab = request.GET.get("tab", "register")  # default like screenshot
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "login":
            login_form = LoginForm(request.POST, prefix="login")
            if login_form.is_valid():
                user = login_form.cleaned_data["user"]
                login(request, user)
                # If persona not completed, continue
                if hasattr(user, "profile") and not user.profile.persona_completed:
                    return redirect("accounts:persona_welcome")
                return redirect("home")
            active_tab = "login"

        elif action == "register":
            register_form = RegisterForm(request.POST, prefix="register")
            if register_form.is_valid():
                email = register_form.cleaned_data["email"].lower().strip()
                full_name = register_form.cleaned_data["full_name"].strip()
                password = register_form.cleaned_data["password"]
                phone_country = register_form.cleaned_data["phone_country"]
                phone_number = register_form.cleaned_data["phone_number"].strip()

                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    first_name=full_name,
                    is_active=False,
                )
                # profile created by signal
                user.profile.phone_country = phone_country
                user.profile.phone_number = phone_number
                user.profile.save()

                otp = store_otp(request, email=email, user_id=user.id)
                send_otp_email(to_email=email, code=otp.code)
                return redirect("accounts:verify_otp")
            active_tab = "register"

    return render(request, "accounts/auth.html", {
        "login_form": login_form,
        "register_form": register_form,
        "active_tab": active_tab,
    })


def verify_otp(request: HttpRequest) -> HttpResponse:
    pending_user_id = request.session.get(OTP_PENDING_USER_ID)
    email = request.session.get(OTP_EMAIL_KEY)
    expires_at = int(request.session.get(OTP_EXPIRES_AT_KEY, 0))
    remaining = max(0, expires_at - int(time.time()))

    if not pending_user_id or not email:
        return redirect(reverse("accounts:auth") + "?tab=register")

    form = OTPForm()
    if request.method == "POST":
        form = OTPForm(request.POST)
        if form.is_valid():
            code = form.code()
            if validate_otp(request, code=code):
                try:
                    user = User.objects.get(id=pending_user_id)
                except User.DoesNotExist:
                    clear_otp(request)
                    return redirect("accounts:auth")

                user.is_active = True
                user.save(update_fields=["is_active"])
                clear_otp(request)

                login(request, user)
                return redirect("accounts:persona_welcome")

            form.add_error(None, "رمز غير صحيح أو منتهي الصلاحية.")
        else:
            form.add_error(None, "أدخل رمز التحقق بشكل صحيح.")

    return render(request, "accounts/verify_otp.html", {
        "form": form,
        "email": email,
        "masked_email": _mask_email(email),
        "remaining": remaining,
    })


def resend_otp(request: HttpRequest) -> HttpResponse:
    pending_user_id = request.session.get(OTP_PENDING_USER_ID)
    email = request.session.get(OTP_EMAIL_KEY)
    if not pending_user_id or not email:
        return redirect("accounts:auth")
    otp = store_otp(request, email=email, user_id=pending_user_id)
    send_otp_email(to_email=email, code=otp.code)
    messages.success(request, "تم إرسال رمز جديد.")
    return redirect("accounts:verify_otp")


@login_required
def do_logout(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect("accounts:auth")


# ---------------------------
# Persona (Salla-like)
# ---------------------------

@login_required
def persona_welcome(request: HttpRequest) -> HttpResponse:
    if request.user.profile.persona_completed:
        return redirect("home")
    if request.method == "POST":
        return redirect("accounts:persona_country")
    return render(request, "accounts/persona_welcome.html")

@login_required
def persona_country(request: HttpRequest) -> HttpResponse:
    if request.user.profile.persona_completed:
        return redirect("home")
    form = PersonaCountryForm(initial={"country": request.user.profile.country} if request.user.profile.country else None)
    if request.method == "POST":
        form = PersonaCountryForm(request.POST)
        if form.is_valid():
            request.user.profile.country = form.cleaned_data["country"]
            request.user.profile.save(update_fields=["country"])
            return redirect("accounts:persona_legal")
    return render(request, "accounts/persona_country.html", {"form": form})


@login_required
def persona_legal(request: HttpRequest) -> HttpResponse:
    if request.user.profile.persona_completed:
        return redirect("home")
    form = PersonaLegalForm(initial={"legal_entity": request.user.profile.legal_entity} if request.user.profile.legal_entity else None)
    if request.method == "POST":
        form = PersonaLegalForm(request.POST)
        if form.is_valid():
            request.user.profile.legal_entity = form.cleaned_data["legal_entity"]
            request.user.profile.save(update_fields=["legal_entity"])
            return redirect("accounts:persona_existing")
    return render(request, "accounts/persona_legal.html", {"form": form})


@login_required
def persona_existing(request: HttpRequest) -> HttpResponse:
    if request.user.profile.persona_completed:
        return redirect("home")
    form = PersonaExistingForm(initial={"has_existing_business": request.user.profile.has_existing_business} if request.user.profile.has_existing_business else None)
    if request.method == "POST":
        form = PersonaExistingForm(request.POST)
        if form.is_valid():
            request.user.profile.has_existing_business = form.cleaned_data["has_existing_business"]
            request.user.profile.save(update_fields=["has_existing_business"])
            return redirect("accounts:persona_channel")
    return render(request, "accounts/persona_existing.html", {"form": form})


@login_required
def persona_channel(request: HttpRequest) -> HttpResponse:
    if request.user.profile.persona_completed:
        return redirect("home")
    form = PersonaChannelForm(initial={"selling_channel": request.user.profile.selling_channel} if request.user.profile.selling_channel else None)
    if request.method == "POST":
        form = PersonaChannelForm(request.POST)
        if form.is_valid():
            request.user.profile.selling_channel = form.cleaned_data["selling_channel"]
            request.user.profile.save(update_fields=["selling_channel"])
            return redirect("accounts:persona_category_main")
    return render(request, "accounts/persona_channel.html", {"form": form})


@login_required
def persona_category_main(request: HttpRequest) -> HttpResponse:
    if request.user.profile.persona_completed:
        return redirect("home")

    form = PersonaCategoryMainForm(
        initial={
            "category_main": request.user.profile.category_main,
            "category_sub": request.user.profile.category_sub,
        }
        if request.user.profile.category_main
        else None
    )

    if request.method == "POST":
        form = PersonaCategoryMainForm(request.POST)
        if form.is_valid():
            request.user.profile.category_main = form.cleaned_data["category_main"]
            request.user.profile.category_sub = (form.cleaned_data.get("category_sub") or "").strip()
            request.user.profile.save(update_fields=["category_main", "category_sub"])
            # Next step: plans (Salla-like)
            return redirect("accounts:persona_plans")

    from .forms import SUBCATEGORY_MAP
    return render(request, "accounts/persona_category_main.html", {
        "form": form,
        "subs_json": json.dumps({k: v for k, v in SUBCATEGORY_MAP.items()}),
    })

@login_required
def persona_finish(request: HttpRequest) -> HttpResponse:
    if request.user.profile.persona_completed:
        return redirect("home")
    if request.method == "POST":
        request.user.profile.persona_completed = True
        request.user.profile.save(update_fields=["persona_completed"])
        # next: store creation (V1-P3). For now go home.
        return redirect("accounts:persona_plans")
    return render(request, "accounts/persona_finish.html")