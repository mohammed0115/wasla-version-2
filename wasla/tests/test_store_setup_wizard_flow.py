import pytest

from apps.tenants.models import TenantMembership, StoreProfile


@pytest.mark.django_db
def test_store_setup_wizard_steps_progress(auth_client, user):
    # Complete persona plan selection (creates tenant + membership + store profile)
    resp = auth_client.post(
        "/persona/plans/",
        {"billing_cycle": "monthly", "plan_id": ""},
        follow=False,
    )
    assert resp.status_code in (302, 303)

    membership = TenantMembership.objects.filter(user=user, role="owner", is_active=True).select_related("tenant").first()
    assert membership is not None
    tenant = membership.tenant

    # Step 1: store info
    resp = auth_client.get("/store/setup/step-1")
    assert resp.status_code in (200, 302)

    resp = auth_client.post(
        "/store/setup/step-1",
        {
            "name": "Test Store",
            "slug": tenant.slug,  # keep existing slug valid
            "currency": "SAR",
            "language": "ar",
            "primary_color": "#1F4FD8",
            "secondary_color": "#3B6EF5",
        },
        follow=False,
    )
    assert resp.status_code in (302, 303)

    profile = StoreProfile.objects.get(tenant=tenant)
    assert profile.setup_step >= 1

    # Step 2: payment
    resp = auth_client.post(
        "/store/setup/step-2",
        {
            "payment_mode": "manual",
            "provider_name": "",
            "merchant_key": "",
            "webhook_secret": "",
            "is_enabled": "on",
        },
        follow=False,
    )
    assert resp.status_code in (302, 303)

    profile.refresh_from_db()
    assert profile.setup_step >= 2

    # Step 3: shipping
    resp = auth_client.post(
        "/store/setup/step-3",
        {
            "fulfillment_mode": "pickup",
            "origin_city": "Riyadh",
            "delivery_fee_flat": "0.00",
            "free_shipping_threshold": "0.00",
            "is_enabled": "on",
        },
        follow=False,
    )
    assert resp.status_code in (302, 303)

    profile.refresh_from_db()
    assert profile.setup_step >= 3

    # Step 4: activation page should be reachable
    resp = auth_client.get("/store/setup/step-4")
    assert resp.status_code in (200, 302)
