"""BNPL app URL configuration."""

from django.urls import path
from . import views

app_name = "bnpl"

urlpatterns = [
    # Payment initiation
    path(
        "checkout/bnpl/initiate/<int:order_id>/",
        views.initiate_bnpl_payment,
        name="initiate_payment",
    ),
    # Success/failure redirects
    path(
        "checkout/bnpl-success/",
        views.bnpl_payment_success,
        name="payment_success",
    ),
    path(
        "checkout/bnpl-failure/",
        views.bnpl_payment_failure,
        name="payment_failure",
    ),
    path(
        "checkout/bnpl-cancel/",
        views.bnpl_payment_cancel,
        name="payment_cancel",
    ),
    # Webhooks (external)
    path(
        "api/webhooks/tabby/",
        views.tabby_webhook,
        name="tabby_webhook",
    ),
    path(
        "api/webhooks/tamara/",
        views.tamara_webhook,
        name="tamara_webhook",
    ),
]
